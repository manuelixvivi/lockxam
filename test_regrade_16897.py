from app.core.database import SessionLocal
from app.models.ai.ai_system_setting import AiSystemSetting
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.services.ai.shared.config import AiConfig
from app.services.exam.exam_service import ExamService


def test_regrade_real():
    db = SessionLocal()

    # Update AI config to a safe model like qwen/qwen2.5-7b-instruct or llama-3.1-8b-instant
    # We will just write to AiSystemSetting table
    setting = db.query(AiSystemSetting).filter(AiSystemSetting.key == "ai_provider_config").first()
    if setting:
        val = dict(setting.value_json or {})
        val["eval_model_name"] = "llama-3.1-8b-instant"
        setting.value_json = val
        db.commit()
        # Force flush cache
        AiConfig._db_cache["config"] = None

    print("Testing Regrade on Attempt 16897 (which has essay questions)...")
    try:
        ExamService.execute_ai_essay_grading_job(db, 16897, force_regrade=True)
        evals = (
            db.query(ExamAnswerEvaluation)
            .filter(ExamAnswerEvaluation.exam_attempt_id == 16897)
            .all()
        )
        for ev in evals:
            print(f"Eval ID: {ev.id}")
            print(f"Score: {ev.score}")
            print(f"Feedback: {ev.feedback}")
            print("-" * 40)
    except Exception as e:
        print(f"Error during regrade: {e}")


if __name__ == "__main__":
    test_regrade_real()
