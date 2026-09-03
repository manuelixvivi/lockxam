from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.ai.training_candidate import TrainingCandidate


class TrainingCandidateRepository:
    """
    Repository for TrainingCandidate entity persistence and query operations.
    Supports filtering by quality threshold, PII status, subject, and group keys.
    """

    def create(self, db: Session, candidate: TrainingCandidate) -> TrainingCandidate:
        db.add(candidate)
        db.flush()
        return candidate

    def get_by_id(self, db: Session, candidate_id: int) -> Optional[TrainingCandidate]:
        return db.query(TrainingCandidate).filter(TrainingCandidate.id == candidate_id).first()

    def get_by_history_and_version(
        self, db: Session, history_id: int, version: int
    ) -> Optional[TrainingCandidate]:
        return (
            db.query(TrainingCandidate)
            .filter(
                TrainingCandidate.assessment_history_id == history_id,
                TrainingCandidate.history_version == version,
            )
            .first()
        )

    def get_eligible_candidates(
        self,
        db: Session,
        min_quality_score: float = 0.70,
        subject_id: Optional[int] = None,
        school_id: Optional[int] = None,
    ) -> List[TrainingCandidate]:
        query = db.query(TrainingCandidate).filter(
            TrainingCandidate.quality_status == "ELIGIBLE",
            TrainingCandidate.quality_score >= min_quality_score,
            TrainingCandidate.pii_status.in_(["CLEAN", "SANITIZED"]),
        )
        if subject_id:
            query = query.filter(TrainingCandidate.subject_id == subject_id)
        if school_id:
            query = query.filter(TrainingCandidate.school_id == school_id)

        return query.order_by(TrainingCandidate.id.asc()).all()

    def get_by_ids(self, db: Session, candidate_ids: List[int]) -> List[TrainingCandidate]:
        if not candidate_ids:
            return []
        return (
            db.query(TrainingCandidate)
            .filter(TrainingCandidate.id.in_(candidate_ids))
            .order_by(TrainingCandidate.id.asc())
            .all()
        )


training_candidate_repository = TrainingCandidateRepository()
