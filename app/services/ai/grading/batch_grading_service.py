import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from app.models.academic.enums import ExamScheduleStatus, GradingRunStatus
from app.models.academic.exam_schedule import ExamSchedule
from app.models.academic.grading_run import GradingRun
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.models.exam.enums import ExamAttemptStatus, GradingSource, GradingStatus
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.exam_session import ExamSession
from app.models.exam.student_answer import StudentAnswer
from app.repositories.exam.evaluation_repository import evaluation_repository
from app.repositories.exam.snapshot_repository import snapshot_repository
from app.services.ai.grading.batch_grading_prompt import (
    BATCH_GRADING_PROMPT_VERSION,
    BATCH_GRADING_SYSTEM_PROMPT,
    build_batch_grading_prompt,
)
from app.services.ai.grading.batch_grading_schema import (
    BatchGradingQuestionRequest,
    BatchGradingQuestionResponse,
    BatchStudentGradingResult,
    BatchSubmissionItem,
)
from app.services.ai.grading.grading_service import GradingService
from app.services.ai.shared.config import AiConfig
from app.services.ai.shared.llm_client import LlmClient

logger = logging.getLogger(__name__)


class BatchGradingService:
    """
    Production Post-Exam Batch Essay Grading Engine.
    Responsibilities:
      - Groups all student essay answers by question_id across an entire exam schedule.
      - Performs RAG retrieval ONCE per question/batch, sharing exemplar context across answers.
      - Chunks student submissions into configurable batches (e.g. 25-50) for token efficiency.
      - Enforces strict independent student scoring (no cross-ranking).
      - Tracks execution with unique GradingRun UUIDs (grading_run_id) for safe exam extend/reopen.
      - Validates complete student coverage with targeted automatic retries for omitted IDs.
    """

    @classmethod
    def grade_question_batch(
        cls, payload: BatchGradingQuestionRequest, db: Optional[Session] = None
    ) -> BatchGradingQuestionResponse:
        """
        Evaluates a batch of student answers for a single question using GPT-OSS 120B.
        RAG retrieval is performed ONCE for the entire question.
        """
        start_time = time.time()
        submissions = payload.submissions or []
        rubrics = payload.rubric or [
            {
                "ku_id": "C1",
                "text": "Kesesuaian dan ketepatan jawaban terhadap kunci jawaban resmi",
                "weight": 100.0,
            }
        ]
        max_score = float(payload.max_score or 10.0)

        if not submissions:
            return BatchGradingQuestionResponse(
                question_id=payload.question_id,
                status="success",
                total_submissions=0,
                total_evaluated=0,
                results=[],
                model=AiConfig.EVAL_MODEL_NAME,
                prompt_version=BATCH_GRADING_PROMPT_VERSION,
                rag_enabled=False,
                latency_ms=0.0,
            )

        # -------------------------------------------------------------
        # 1. RAG Context Retrieval (Performed ONCE for the Question)
        # -------------------------------------------------------------
        rag_enabled = GradingService.is_rag_enabled(payload.rag_enabled)
        rag_context_str = ""
        retrieved_cases: List[Dict[str, Any]] = []

        if (
            rag_enabled
            and db is not None
            and payload.school_id is not None
            and payload.subject_id is not None
            and payload.academic_year_id is not None
        ):
            try:
                from app.services.ai.rag_context_service import RagContextService

                rag_payload = RagContextService.assemble_rag_context(
                    db=db,
                    school_id=payload.school_id,
                    subject_id=payload.subject_id,
                    academic_year_id=payload.academic_year_id,
                    subject_name=payload.subject or "Umum",
                    class_level=payload.class_level,
                    question_text=payload.question_text,
                    answer_key=payload.answer_key,
                    rubrics_json=rubrics,
                    max_score=max_score,
                    student_answer=payload.answer_key,  # Anchor on teacher key for question-level retrieval
                )
                rag_context_str = rag_payload.formatted_context_block
                retrieved_cases = [
                    {
                        "case_id": c.assessment_history_id,
                        "similarity": round(c.similarity_score, 4),
                    }
                    for c in rag_payload.reference_cases
                ]
            except Exception as e:
                logger.warning(f"Batch RAG retrieval failed, proceeding non-RAG: {e}")
                rag_context_str = ""

        # -------------------------------------------------------------
        # 2. Chunk Submissions & Execute LLM Inferences
        # -------------------------------------------------------------
        chunk_size = max(1, min(payload.batch_size or AiConfig.BATCH_GRADING_SIZE, 100))
        all_results: Dict[str, BatchStudentGradingResult] = {}
        missing_student_ids: List[Union[int, str]] = []

        # Handle empty student answers deterministically without calling LLM
        valid_submissions: List[BatchSubmissionItem] = []
        for sub in submissions:
            ans_clean = (sub.student_answer or "").strip()
            if not ans_clean:
                all_results[str(sub.student_id)] = BatchStudentGradingResult(
                    student_id=sub.student_id,
                    attempt_id=sub.attempt_id,
                    score=0.0,
                    final_score=0.0,
                    feedback="Jawaban siswa kosong. Tidak ada poin yang dapat dinilai.",
                    rubric_scores=[
                        {
                            "ku_id": r.get("ku_id", f"C{i+1}"),
                            "text": r.get("text", ""),
                            "weight": r.get("weight", 0),
                            "achieved": 0.0,
                        }
                        for i, r in enumerate(rubrics)
                    ],
                    status="success",
                    quality_indicator=1.0,
                )
            else:
                valid_submissions.append(sub)

        for chunk_idx in range(0, len(valid_submissions), chunk_size):
            chunk = valid_submissions[chunk_idx : chunk_idx + chunk_size]
            prompt = build_batch_grading_prompt(
                question_text=payload.question_text,
                answer_key=payload.answer_key,
                rubrics=rubrics,
                submissions=chunk,
                education_level=payload.grade_level or "SMA",
                education_class=payload.education_class or "Kelas 11",
                rag_context=rag_context_str,
            )

            try:
                llm_res = LlmClient.call_chat_completion(
                    system_prompt=BATCH_GRADING_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    model=AiConfig.EVAL_MODEL_NAME,
                    temperature=0.2,
                )
                data = llm_res.get("data", {})
                raw_results = data.get("results", [])

                returned_map: Dict[str, Dict[str, Any]] = {}
                if isinstance(raw_results, list):
                    for item in raw_results:
                        if isinstance(item, dict):
                            s_id = str(item.get("student_id", "")).strip()
                            if s_id:
                                returned_map[s_id] = item

                # Process results and detect any missing students
                for sub in chunk:
                    sub_id_str = str(sub.student_id).strip()
                    res_item = returned_map.get(sub_id_str)

                    if not res_item:
                        missing_student_ids.append(sub.student_id)
                        # Mark as pending evaluation
                        all_results[sub_id_str] = BatchStudentGradingResult(
                            student_id=sub.student_id,
                            attempt_id=sub.attempt_id,
                            score=0.0,
                            final_score=0.0,
                            feedback="Memerlukan penilaian ulang (omitted by batch LLM).",
                            rubric_scores=[],
                            status="error",
                            quality_indicator=0.0,
                        )
                        continue

                    # Calculate score strictly from rubric weights
                    achieved_map: Dict[str, float] = {}
                    for r_entry in res_item.get("rubric_scores", []):
                        if isinstance(r_entry, dict):
                            k_id = str(r_entry.get("ku_id", "")).strip()
                            try:
                                achieved_map[k_id] = float(r_entry.get("achieved", 0))
                            except (ValueError, TypeError):
                                achieved_map[k_id] = 0.0

                    computed_rubrics: List[Dict[str, Any]] = []
                    missing_crit = 0
                    for i, r in enumerate(rubrics):
                        k_id = str(r.get("ku_id", f"C{i+1}")).strip()
                        w = float(r.get("weight", 100.0 / max(1, len(rubrics))))
                        achieved = achieved_map.get(k_id)

                        if achieved is None:
                            for candidate in [f"C{i+1}", f"ku_{i+1}", str(i + 1), str(i)]:
                                if candidate in achieved_map:
                                    achieved = achieved_map[candidate]
                                    break

                        if achieved is None:
                            achieved = 0.0
                            missing_crit += 1

                        computed_rubrics.append(
                            {
                                "ku_id": k_id,
                                "text": r.get("text") or r.get("criterion_text", ""),
                                "weight": w,
                                "achieved": max(0.0, min(100.0, achieved)),
                            }
                        )

                    total_w = sum(c["weight"] for c in computed_rubrics) or 100.0
                    pct = sum(c["achieved"] * c["weight"] for c in computed_rubrics) / total_w
                    pct = round(max(0.0, min(100.0, pct)), 2)
                    scaled = round((pct / 100.0) * max_score, 2)
                    quality = 1.0 - (missing_crit / max(1, len(rubrics)))

                    all_results[sub_id_str] = BatchStudentGradingResult(
                        student_id=sub.student_id,
                        attempt_id=sub.attempt_id,
                        score=scaled,
                        final_score=pct,
                        feedback=res_item.get("feedback", "Penilaian esai selesai."),
                        rubric_scores=computed_rubrics,
                        status="success",
                        quality_indicator=round(quality, 2),
                    )

            except Exception as batch_err:
                logger.error(f"Error grading chunk for question {payload.question_id}: {batch_err}")
                for sub in chunk:
                    sub_id_str = str(sub.student_id).strip()
                    if sub_id_str not in all_results:
                        missing_student_ids.append(sub.student_id)
                        all_results[sub_id_str] = BatchStudentGradingResult(
                            student_id=sub.student_id,
                            attempt_id=sub.attempt_id,
                            score=0.0,
                            final_score=0.0,
                            feedback=f"Gagal mengevaluasi batch: {batch_err}",
                            rubric_scores=[],
                            status="error",
                            quality_indicator=0.0,
                        )

        # -------------------------------------------------------------
        # 3. Targeted Single-Pass Retry for Any Missing Students
        # -------------------------------------------------------------
        if missing_student_ids:
            logger.warning(
                f"Missing {len(missing_student_ids)} students in batch response for question {payload.question_id}. Initiating targeted retry..."
            )
            for m_id in missing_student_ids:
                sub_target = next((s for s in submissions if str(s.student_id) == str(m_id)), None)
                if sub_target and sub_target.student_answer.strip():
                    try:
                        from app.services.ai.grading.grading_schema import GradingEvaluateRequest

                        single_req = GradingEvaluateRequest(
                            question=payload.question_text,
                            answer_key=payload.answer_key,
                            student_answer=sub_target.student_answer,
                            rubrics=rubrics,
                            max_score=max_score,
                            grade_level=payload.grade_level,
                            education_class=payload.education_class,
                            rag_context=rag_context_str,
                            rag_enabled=rag_enabled,
                        )
                        single_res = GradingService.evaluate(single_req)
                        all_results[str(m_id)] = BatchStudentGradingResult(
                            student_id=sub_target.student_id,
                            attempt_id=sub_target.attempt_id,
                            score=single_res.score,
                            final_score=single_res.final_score,
                            feedback=single_res.feedback,
                            rubric_scores=single_res.rubric_scores,
                            status="success",
                            quality_indicator=1.0,
                        )
                    except Exception as retry_err:
                        logger.error(f"Single retry failed for student {m_id}: {retry_err}")

        # Assemble final ordered results matching input submissions order
        ordered_results = [
            all_results.get(str(sub.student_id))
            for sub in submissions
            if str(sub.student_id) in all_results
        ]
        successful_evals = sum(1 for r in ordered_results if r and r.status == "success")
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return BatchGradingQuestionResponse(
            question_id=payload.question_id,
            status="success" if successful_evals == len(submissions) else "partial",
            total_submissions=len(submissions),
            total_evaluated=successful_evals,
            missing_students=[
                s.student_id
                for s in submissions
                if all_results.get(str(s.student_id), {}).status != "success"
            ],
            results=[r for r in ordered_results if r is not None],
            model=AiConfig.EVAL_MODEL_NAME,
            prompt_version=BATCH_GRADING_PROMPT_VERSION,
            rag_enabled=rag_enabled,
            retrieved_cases=retrieved_cases,
            latency_ms=elapsed_ms,
        )

    # ─────────────────────────────────────────────────────────────
    # Post-Exam Batch Grading Workflow (Triggered upon LOCKED Exam)
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def start_post_exam_grading(
        cls,
        db: Session,
        schedule_id: int,
        rag_enabled: Optional[bool] = None,
        batch_size: int = 50,
    ) -> GradingRun:
        """
        Initiates a post-exam batch grading job for a locked exam schedule.
        Creates a persistent GradingRun record with a unique UUID.
        """
        schedule = db.query(ExamSchedule).filter(ExamSchedule.id == schedule_id).first()
        if not schedule:
            raise ValueError(f"ExamSchedule {schedule_id} not found.")

        # Invariant: Exam must be LOCKED or TIME_ENDED
        if schedule.status not in (
            ExamScheduleStatus.LOCKED.value,
            ExamScheduleStatus.TIME_ENDED.value,
            ExamScheduleStatus.COMPLETED.value,
        ):
            raise ValueError(
                f"Cannot start grading for exam in '{schedule.status}' status. Exam must be LOCKED."
            )

        # Transition schedule to LOCKED if not already
        if schedule.status != ExamScheduleStatus.LOCKED.value:
            schedule.status = ExamScheduleStatus.LOCKED.value
            db.commit()

        # Cancel any previous in-flight grading runs for this schedule
        prev_runs = (
            db.query(GradingRun)
            .filter(
                GradingRun.exam_schedule_id == schedule_id,
                GradingRun.status.in_(
                    [GradingRunStatus.QUEUED.value, GradingRunStatus.PROCESSING.value]
                ),
            )
            .all()
        )
        for pr in prev_runs:
            pr.status = GradingRunStatus.CANCELLED.value
            pr.cancelled_at = datetime.now(timezone.utc)
        db.commit()

        # Create new authoritative GradingRun
        run = GradingRun(
            id=uuid.uuid4(),
            exam_schedule_id=schedule_id,
            status=GradingRunStatus.PROCESSING.value,
            model_used=AiConfig.EVAL_MODEL_NAME,
            prompt_version=BATCH_GRADING_PROMPT_VERSION,
            rag_enabled=GradingService.is_rag_enabled(rag_enabled),
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Execute Post-Exam Grading Pipeline
        try:
            cls.execute_post_exam_batch_pipeline(
                db=db,
                schedule=schedule,
                grading_run=run,
                rag_enabled=rag_enabled,
                batch_size=batch_size,
            )
        except Exception as e:
            logger.error(f"Post-exam grading pipeline failed: {e}")
            run.status = GradingRunStatus.FAILED.value
            run.error_message = str(e)
            db.commit()

        return run

    @classmethod
    def execute_post_exam_batch_pipeline(
        cls,
        db: Session,
        schedule: ExamSchedule,
        grading_run: GradingRun,
        rag_enabled: Optional[bool] = None,
        batch_size: int = 50,
    ) -> None:
        """
        Gathers all student submissions for essay questions, groups by question_id,
        and executes batch grading question-by-question with cancellation safety.
        """
        # 1. Retrieve all exam sessions and attempts
        sessions = db.query(ExamSession).filter(ExamSession.schedule_id == schedule.id).all()
        if not sessions:
            grading_run.status = GradingRunStatus.COMPLETED.value
            grading_run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        session_ids = [s.id for s in sessions]
        attempts = db.query(ExamAttempt).filter(ExamAttempt.exam_session_id.in_(session_ids)).all()
        if not attempts:
            grading_run.status = GradingRunStatus.COMPLETED.value
            grading_run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # 2. Retrieve Snapshot Questions
        snapshot = snapshot_repository.get_by_session(db, sessions[0].id)
        if not snapshot or not snapshot.questions_json:
            grading_run.status = GradingRunStatus.FAILED.value
            grading_run.error_message = "No snapshot questions found for exam session."
            db.commit()
            return

        grading_run.exam_snapshot_id = snapshot.id

        # Filter for Essay Questions
        essay_questions = [q for q in snapshot.questions_json if q.get("type") == "ES"]
        if not essay_questions:
            # PG only exam - mark completed
            grading_run.status = GradingRunStatus.COMPLETED.value
            grading_run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # 3. Group Student Submissions by question_id
        attempt_map = {a.id: a for a in attempts}
        answers_by_question: Dict[int, List[BatchSubmissionItem]] = {
            q.get("id") or q.get("question_id"): [] for q in essay_questions
        }

        all_answers = (
            db.query(StudentAnswer)
            .filter(StudentAnswer.exam_attempt_id.in_([a.id for a in attempts]))
            .all()
        )

        for ans in all_answers:
            if ans.question_id in answers_by_question:
                attempt = attempt_map.get(ans.exam_attempt_id)
                student_id = attempt.student_id if attempt else ans.exam_attempt_id
                answers_by_question[ans.question_id].append(
                    BatchSubmissionItem(
                        student_id=student_id,
                        student_answer=ans.text_answer or "",
                        attempt_id=ans.exam_attempt_id,
                    )
                )

        total_subs = sum(len(items) for items in answers_by_question.values())
        grading_run.total_questions = len(essay_questions)
        grading_run.total_submissions = total_subs
        grading_run.total_batches = sum(
            max(1, (len(items) + batch_size - 1) // batch_size)
            for items in answers_by_question.values()
        )
        db.commit()

        # 4. Iterate Questions and Process Batches
        processed_batches_count = 0
        failed_batches_count = 0

        for q_dict in essay_questions:
            q_id = q_dict.get("id") or q_dict.get("question_id")
            subs = answers_by_question.get(q_id, [])
            if not subs:
                continue

            # Cancellation Check: Has the run been cancelled (e.g. by admin reopen)?
            db.refresh(grading_run)
            if grading_run.status == GradingRunStatus.CANCELLED.value:
                logger.info(f"GradingRun {grading_run.id} was cancelled. Halting batch execution.")
                return

            req = BatchGradingQuestionRequest(
                question_id=q_id,
                question_text=q_dict.get("content", ""),
                answer_key=q_dict.get("answer_key", ""),
                rubric=q_dict.get("rubrics", []),
                concepts=q_dict.get("concepts", []),
                max_score=float(q_dict.get("max_score", 10.0)),
                subject=q_dict.get("subject") or "Umum",
                school_id=schedule.school_id,
                subject_id=schedule.subject_id,
                academic_year_id=schedule.academic_year_id,
                rag_enabled=rag_enabled,
                batch_size=batch_size,
                submissions=subs,
            )

            batch_res = cls.grade_question_batch(req, db=db)

            # Atomic Persistence per Question Batch with Run Active Verification
            db.refresh(grading_run)
            if grading_run.status == GradingRunStatus.CANCELLED.value:
                logger.info(f"GradingRun {grading_run.id} cancelled before commit. Rollback.")
                return

            for res_item in batch_res.results:
                if res_item.attempt_id:
                    # CRITICAL INTEGRITY CHECK: Only persist evaluations when grading actually succeeded.
                    # Never persist failed/missing evaluations as score 0.0 AI_DRAFT!
                    if res_item.status != "success":
                        continue

                    eval_rec = evaluation_repository.get_by_attempt_and_question_with_lock(
                        db, res_item.attempt_id, q_id
                    )
                    if eval_rec:
                        if eval_rec.grading_status != GradingStatus.FINALIZED:
                            eval_rec.score = res_item.score
                            eval_rec.feedback = res_item.feedback
                            eval_rec.grading_status = GradingStatus.AI_DRAFT
                            eval_rec.grading_source = GradingSource.AI
                            eval_rec.grading_version = (eval_rec.grading_version or 0) + 1
                            eval_rec.last_evaluated_at = datetime.now(timezone.utc)
                    else:
                        new_eval = ExamAnswerEvaluation(
                            exam_attempt_id=res_item.attempt_id,
                            question_id=q_id,
                            score=res_item.score,
                            max_score=float(q_dict.get("max_score", 10.0)),
                            feedback=res_item.feedback,
                            grading_status=GradingStatus.AI_DRAFT,
                            grading_source=GradingSource.AI,
                            grading_version=1,
                            last_evaluated_at=datetime.now(timezone.utc),
                        )
                        evaluation_repository.create(db, new_eval)

            if batch_res.status == "success":
                processed_batches_count += 1
            else:
                failed_batches_count += 1

            grading_run.processed_batches = processed_batches_count
            grading_run.failed_batches = failed_batches_count
            db.commit()

        # 5. Finalize Attempts Scores and Transition Schedule with Completeness Guard
        all_attempts_graded = True
        for att in attempts:
            evals = evaluation_repository.get_all_by_attempt(db, att.id)
            has_pending = any(
                e.grading_status in [GradingStatus.AI_PENDING, "AI_PENDING"] for e in evals
            )
            if not has_pending and evals:
                total_score = sum(float(e.score) for e in evals)
                total_max = sum(float(e.max_score or 10.0) for e in evals)
                att.final_score = (
                    round((total_score / total_max * 100.0), 2) if total_max > 0 else 0.0
                )
                att.status = ExamAttemptStatus.GRADED
                att.updated_at = datetime.now(timezone.utc)
            else:
                # Partial / Incomplete grading: Keep attempt in GRADING status
                att.status = ExamAttemptStatus.GRADING
                all_attempts_graded = False

        if failed_batches_count == 0 and all_attempts_graded:
            grading_run.status = GradingRunStatus.COMPLETED.value
            schedule.status = ExamScheduleStatus.COMPLETED.value
        else:
            grading_run.status = GradingRunStatus.PARTIAL.value

        grading_run.completed_at = datetime.now(timezone.utc)
        db.commit()

    @classmethod
    def cancel_grading_run(cls, db: Session, grading_run_id: uuid.UUID) -> bool:
        """Cancels an ongoing or queued grading run (e.g. upon exam reopen)."""
        run = db.query(GradingRun).filter(GradingRun.id == grading_run_id).first()
        if run and run.status in [
            GradingRunStatus.QUEUED.value,
            GradingRunStatus.PROCESSING.value,
        ]:
            run.status = GradingRunStatus.CANCELLED.value
            run.cancelled_at = datetime.now(timezone.utc)
            db.commit()
            return True
        return False
