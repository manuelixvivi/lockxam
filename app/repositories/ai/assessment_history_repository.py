from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.ai.assessment_history import AssessmentHistory


class AssessmentHistoryRepository:
    """
    Repository for AssessmentHistory entity persistence and queries.
    Encapsulates all direct DB access for historical assessment datasets.
    """

    def create(self, db: Session, history: AssessmentHistory) -> AssessmentHistory:
        db.add(history)
        db.flush()
        return history

    def get_by_id(self, db: Session, history_id: int) -> AssessmentHistory | None:
        return db.query(AssessmentHistory).filter(AssessmentHistory.id == history_id).first()

    def get_current_by_evaluation(
        self, db: Session, evaluation_id: int
    ) -> AssessmentHistory | None:
        return (
            db.query(AssessmentHistory)
            .filter(
                AssessmentHistory.evaluation_id == evaluation_id,
                AssessmentHistory.is_current.is_(True),
            )
            .first()
        )

    def get_history_by_evaluation_and_version(
        self, db: Session, evaluation_id: int, version: int
    ) -> AssessmentHistory | None:
        return (
            db.query(AssessmentHistory)
            .filter(
                AssessmentHistory.evaluation_id == evaluation_id,
                AssessmentHistory.version == version,
            )
            .first()
        )

    def get_version_chain(self, db: Session, evaluation_id: int) -> list[AssessmentHistory]:
        return (
            db.query(AssessmentHistory)
            .filter(AssessmentHistory.evaluation_id == evaluation_id)
            .order_by(AssessmentHistory.version.asc())
            .all()
        )

    def mark_superseded(self, db: Session, history_id: int) -> None:
        record = db.query(AssessmentHistory).filter(AssessmentHistory.id == history_id).first()
        if record:
            record.is_current = False
            record.superseded_at = datetime.now(timezone.utc)
            record.embedding_status = "SUPERSEDED"
            db.flush()

    def get_rag_eligible_active(
        self, db: Session, school_id: int, limit: int = 100
    ) -> list[AssessmentHistory]:
        return (
            db.query(AssessmentHistory)
            .filter(
                AssessmentHistory.school_id == school_id,
                AssessmentHistory.is_rag_eligible.is_(True),
                AssessmentHistory.is_current.is_(True),
            )
            .limit(limit)
            .all()
        )

    def get_all_by_school(
        self, db: Session, school_id: int, subject_id: int | None = None
    ) -> list[AssessmentHistory]:
        query = db.query(AssessmentHistory).filter(AssessmentHistory.school_id == school_id)
        if subject_id is not None:
            query = query.filter(AssessmentHistory.subject_id == subject_id)
        return query.order_by(AssessmentHistory.created_at.desc()).all()


assessment_history_repository = AssessmentHistoryRepository()
