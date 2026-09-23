from app.core.database import SessionLocal
from app.models.ai.ai_system_setting import AiSystemSetting
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.services.ai.shared.config import AiConfig
from app.services.exam.exam_service import ExamService


def test_regrade_157():
    db = SessionLocal()

    # Configure DB to use a good model
    setting = db.query(AiSystemSetting).filter(AiSystemSetting.key == "ai_provider_config").first()
    if setting:
        val = dict(setting.value_json or {})
        val["eval_model_name"] = "llama-3.3-70b-versatile"  # Native Groq Llama 3 model
        setting.value_json = val
        db.commit()
        AiConfig._db_cache["config"] = None

    print("Executing force regrade on Attempt 157...")
    try:
        ExamService.execute_ai_essay_grading_job(db, 157, force_regrade=True)
        evals = (
            db.query(ExamAnswerEvaluation).filter(ExamAnswerEvaluation.exam_attempt_id == 157).all()
        )
        for ev in evals:
            print(f"Eval ID: {ev.id}")
            print(f"Score: {ev.score}")
            print(f"Feedback: {ev.feedback}")
            print("-" * 40)
    except Exception as e:
        print(f"Error during regrade: {e}")


if __name__ == "__main__":
    test_regrade_157()
