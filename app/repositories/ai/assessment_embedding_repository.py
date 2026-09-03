from sqlalchemy.orm import Session

from app.models.ai.assessment_embedding import AssessmentEmbedding
from app.models.ai.assessment_history import AssessmentHistory


class AssessmentEmbeddingRepository:
    """
    Repository for AssessmentEmbedding persistence and retrieval.
    Encapsulates all vector metadata operations, version management, and RAG candidate querying.
    """

    def create(self, db: Session, embedding: AssessmentEmbedding) -> AssessmentEmbedding:
        db.add(embedding)
        db.flush()
        return embedding

    def get_by_id(self, db: Session, embedding_id: int) -> AssessmentEmbedding | None:
        return db.query(AssessmentEmbedding).filter(AssessmentEmbedding.id == embedding_id).first()

    def get_current_by_history(
        self, db: Session, assessment_history_id: int
    ) -> AssessmentEmbedding | None:
        return (
            db.query(AssessmentEmbedding)
            .filter(
                AssessmentEmbedding.assessment_history_id == assessment_history_id,
                AssessmentEmbedding.is_current.is_(True),
            )
            .first()
        )

    def get_by_history_and_version(
        self, db: Session, assessment_history_id: int, version: int
    ) -> AssessmentEmbedding | None:
        return (
            db.query(AssessmentEmbedding)
            .filter(
                AssessmentEmbedding.assessment_history_id == assessment_history_id,
                AssessmentEmbedding.version == version,
            )
            .first()
        )

    def get_by_content_hash(
        self, db: Session, content_hash: str, model_name: str
    ) -> AssessmentEmbedding | None:
        return (
            db.query(AssessmentEmbedding)
            .filter(
                AssessmentEmbedding.content_hash == content_hash,
                AssessmentEmbedding.embedding_model == model_name,
                AssessmentEmbedding.is_current.is_(True),
            )
            .first()
        )

    def mark_superseded(self, db: Session, embedding_id: int) -> None:
        record = (
            db.query(AssessmentEmbedding).filter(AssessmentEmbedding.id == embedding_id).first()
        )
        if record:
            record.is_current = False
            db.flush()

    def get_active_by_tenant_and_subject(
        self, db: Session, school_id: int, subject_id: int | None = None
    ) -> list[AssessmentEmbedding]:
        query = db.query(AssessmentEmbedding).filter(
            AssessmentEmbedding.school_id == school_id,
            AssessmentEmbedding.is_current.is_(True),
        )
        if subject_id is not None:
            query = query.filter(AssessmentEmbedding.subject_id == subject_id)
        return query.all()

    def get_rag_candidates(
        self,
        db: Session,
        school_id: int,
        subject_id: int,
        academic_year_id: int,
        class_level: str | None = None,
    ) -> list[tuple[AssessmentEmbedding, AssessmentHistory]]:
        """
        Retrieves active, RAG-eligible assessment embeddings paired with their assessment history.

        CRITICAL SECURITY INVARIANT:
        SQL WHERE pre-filters school_id, subject_id, academic_year_id, and is_current/is_rag_eligible.
        Foreign school vectors are NEVER fetched into application memory.
        """
        query = (
            db.query(AssessmentEmbedding, AssessmentHistory)
            .join(
                AssessmentHistory,
                AssessmentEmbedding.assessment_history_id == AssessmentHistory.id,
            )
            .filter(
                AssessmentEmbedding.school_id == school_id,
                AssessmentEmbedding.subject_id == subject_id,
                AssessmentEmbedding.academic_year_id == academic_year_id,
                AssessmentEmbedding.is_current.is_(True),
                AssessmentHistory.is_current.is_(True),
                AssessmentHistory.is_rag_eligible.is_(True),
            )
        )

        if class_level:
            query = query.filter(AssessmentEmbedding.class_level == class_level)

        return query.all()


assessment_embedding_repository = AssessmentEmbeddingRepository()
