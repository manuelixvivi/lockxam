from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QualityGateResult:
    is_eligible: bool
    quality_score: float
    quality_status: str  # 'ELIGIBLE', 'NEEDS_REVIEW', 'REJECTED'
    rejection_reasons: List[str] = field(default_factory=list)
    quality_breakdown: Dict[str, float] = field(default_factory=dict)


class QualityGateService:
    """
    Milestone A8: Training Data Quality Gate Engine.
    Filters raw AssessmentHistory records to ensure only pedagogically substantive,
    valid, and non-trivial assessment records enter fine-tuning datasets.
    """

    TRIVIAL_FEEDBACK_TOKENS = {
        "bagus",
        "sip",
        "ok",
        "oke",
        "salah",
        "benar",
        "baik",
        "mantap",
        "sudah",
        "ya",
        "tidak",
        "kurang",
        "good",
        "pass",
    }

    @classmethod
    def evaluate_quality(
        cls,
        student_answer: str,
        teacher_feedback: Optional[str],
        teacher_score: float,
        max_score: float = 10.0,
        rubrics: Optional[List[Dict[str, Any]]] = None,
    ) -> QualityGateResult:
        rejection_reasons: List[str] = []

        # 1. Score Boundary Verification
        score_valid = 0.0 <= float(teacher_score) <= float(max_score)
        if not score_valid:
            rejection_reasons.append("SCORE_OUT_OF_BOUNDS")
        s_score = 1.0 if score_valid else 0.0

        # 2. Student Answer Length & Substance
        raw_ans = (student_answer or "").strip()
        ans_words = len(raw_ans.split())
        if ans_words == 0:
            rejection_reasons.append("EMPTY_STUDENT_ANSWER")
            s_answer = 0.0
        elif ans_words < 3:
            rejection_reasons.append("STUDENT_ANSWER_TOO_SHORT")
            s_answer = 0.3
        else:
            s_answer = min(1.0, ans_words / 15.0)

        # 3. Teacher Feedback Substantiveness Check
        raw_fb = (teacher_feedback or "").strip()
        fb_words = len(raw_fb.split())

        if fb_words == 0:
            rejection_reasons.append("FEEDBACK_EMPTY")
            s_feedback = 0.1
        elif fb_words <= 2 and raw_fb.lower().strip(" .!?:;") in cls.TRIVIAL_FEEDBACK_TOKENS:
            rejection_reasons.append("FEEDBACK_TRIVIAL")
            s_feedback = 0.3
        elif fb_words < 6:
            s_feedback = 0.6
        elif fb_words < 12:
            s_feedback = 0.85
        else:
            # Thorough, constructive pedagogical feedback
            s_feedback = 1.0

        # 4. Rubric Structural Validity Check
        valid_rubric = False
        if isinstance(rubrics, list) and len(rubrics) > 0:
            has_valid_items = all(
                isinstance(r, dict)
                and bool(
                    r.get("text")
                    or r.get("criterion_text")
                    or r.get("criterion")
                    or r.get("description")
                )
                and float(r.get("weight", 1)) > 0
                for r in rubrics
            )
            if has_valid_items:
                valid_rubric = True

        if not valid_rubric:
            rejection_reasons.append("MISSING_OR_EMPTY_RUBRIC")
            s_rubric = 0.2
        else:
            s_rubric = 1.0

        # 5. Composite Quality Score Calculation (Weighted)
        # Weights: 25% score integrity, 30% student substance, 35% feedback pedagogic value, 10% rubric
        quality_score = 0.25 * s_score + 0.30 * s_answer + 0.35 * s_feedback + 0.10 * s_rubric
        quality_score = round(max(0.0, min(1.0, quality_score)), 2)

        # 6. Status Determination
        if quality_score >= 0.70 and len(rejection_reasons) == 0:
            status = "ELIGIBLE"
            is_eligible = True
        elif quality_score >= 0.40:
            status = "NEEDS_REVIEW"
            is_eligible = False
        else:
            status = "REJECTED"
            is_eligible = False

        return QualityGateResult(
            is_eligible=is_eligible,
            quality_score=quality_score,
            quality_status=status,
            rejection_reasons=rejection_reasons,
            quality_breakdown={
                "score_validity": s_score,
                "answer_substance": round(s_answer, 2),
                "feedback_quality": round(s_feedback, 2),
                "rubric_completeness": round(s_rubric, 2),
            },
        )
