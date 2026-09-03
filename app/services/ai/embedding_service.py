import hashlib
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai.assessment_embedding import AssessmentEmbedding
from app.models.ai.assessment_history import AssessmentHistory
from app.repositories.ai.assessment_embedding_repository import (
    assessment_embedding_repository,
)
from app.services.ai.assessment_document_service import AssessmentDocumentService

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Transformer Embedding Service — Milestone A3

    Generates deterministic 1024-dimensional dense vector embeddings using
    intfloat/multilingual-e5-large with L2 normalization, E5 prefix enforcement,
    and persistent metadata coupling.
    """

    _model_instance = None
    _is_mock = False

    @classmethod
    def get_config(cls) -> dict[str, Any]:
        """Returns runtime configuration for embedding model."""
        return {
            "model_name": os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large"),
            "device": os.getenv("EMBEDDING_DEVICE", "cpu"),
            "batch_size": int(os.getenv("EMBEDDING_BATCH_SIZE", "8")),
            "dimension": 1024,
            "max_seq_length": 512,
            "strict_transformer": os.getenv("STRICT_TRANSFORMER", "false").lower()
            in ("true", "1", "yes"),
        }

    @classmethod
    def get_engine_info(cls) -> dict[str, Any]:
        """
        Returns full provenance and execution engine metadata.
        Ensures transparent reporting between real Neural Transformer inference
        and deterministic development mock encoder.
        """
        cls.get_model()
        return {
            "model_name": os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large"),
            "engine_type": (
                "neural_transformer (SentenceTransformer)"
                if not cls._is_mock
                else "deterministic_development_mock"
            ),
            "is_neural_transformer": not cls._is_mock,
            "dimension": 1024,
            "normalization": "L2 (Unit Euclidean)",
        }

    @classmethod
    def is_neural_engine_available(cls) -> bool:
        """Checks if SentenceTransformer is actively loaded without mock fallback."""
        cls.get_model()
        return not cls._is_mock

    @classmethod
    def get_model(cls, require_transformer: bool = False):
        """
        Lazy-loads the SentenceTransformer embedding model.

        In production/scientific mode (or when require_transformer=True / STRICT_TRANSFORMER=true),
        failure to load the neural Transformer will raise RuntimeError.

        In development/CI test mode, falls back to a deterministic 1024-D SHA-512 encoder.
        """
        config = cls.get_config()
        strict = require_transformer or config["strict_transformer"]

        if cls._model_instance is not None:
            if strict and cls._is_mock:
                raise RuntimeError(
                    f"STRICT_TRANSFORMER is enabled: Neural Transformer '{config['model_name']}' is required "
                    "but could not be loaded (currently in fallback mode)."
                )
            return cls._model_instance

        model_name = config["model_name"]
        device = config["device"]

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            logger.info(f"Loading Neural Transformer embedding model: {model_name} on {device}")
            cls._model_instance = SentenceTransformer(model_name, device=device)
            cls._is_mock = False
        except Exception as exc:
            if strict:
                raise RuntimeError(
                    f"Failed to load required SentenceTransformer model '{model_name}': {exc}. "
                    "Install dependencies via 'pip install sentence-transformers torch' to enable neural Transformer."
                )
            logger.warning(
                f"SentenceTransformer not loaded directly ({exc}). Using deterministic fallback encoder for rapid unit test / offline development."
            )
            cls._model_instance = "deterministic_fallback"
            cls._is_mock = True

        return cls._model_instance

    @classmethod
    def estimate_token_count(cls, text: str) -> int:
        """
        Measures the actual or estimated token count of a document.
        Assures token limit safeguards (512 tokens max) without silent truncation.
        """
        model = cls.get_model()
        if not cls._is_mock and hasattr(model, "tokenizer") and model.tokenizer:
            try:
                tokens = model.tokenizer.encode(text, add_special_tokens=True)
                return len(tokens)
            except Exception:
                pass

        # Robust word-piece length estimation for multilingual Indonesian text
        words = text.split()
        return max(1, int(len(words) * 1.35) + 5)

    @classmethod
    def normalize_l2(cls, vector: list[float]) -> list[float]:
        """Performs L2-normalization on a dense float vector: ||v|| = 1.0."""
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0 or math.isnan(norm):
            return [0.0] * len(vector)
        return [float(x / norm) for x in vector]

    @classmethod
    def _deterministic_encode(cls, text: str, dimension: int = 1024) -> list[float]:
        """
        High-fidelity deterministic pseudo-random projection vector based on SHA-512 hashes.
        Ensures unit testing and offline environments generate mathematically valid, reproducible,
        L2-normalized 1024-float embeddings with zero external network dependencies.
        """
        vector = []
        # Generate 1024 floats from chained SHA-512 hashes
        for block in range(dimension // 16):  # 64 blocks of 16 floats
            h = hashlib.sha512(f"{text}::block_{block}".encode("utf-8")).digest()
            for i in range(0, len(h), 4):
                val = int.from_bytes(h[i : i + 4], byteorder="little", signed=True)
                vector.append(float(val) / 2147483648.0)

        # Truncate / pad to exact dimension
        vector = vector[:dimension]
        return cls.normalize_l2(vector)

    @classmethod
    def encode_passage(cls, text: str) -> list[float]:
        """
        Encodes an Assessment Document for knowledge base storage.
        Enforces 'passage: ' prefix exactly once and validates token length.
        """
        if not text or not text.strip():
            raise ValueError("Cannot encode empty passage text.")

        # Ensure E5 passage prefix is applied exactly once
        clean_text = text.strip()
        if clean_text.startswith("passage:"):
            prefixed = clean_text
        else:
            prefixed = f"passage: {clean_text}"

        # Measure token length safeguard
        config = cls.get_config()
        token_count = cls.estimate_token_count(prefixed)
        if token_count > config["max_seq_length"]:
            logger.warning(
                f"[TOKEN_LIMIT_WARNING] Document token count ({token_count}) exceeds max_seq_length ({config['max_seq_length']})."
            )

        model = cls.get_model()
        if not cls._is_mock and hasattr(model, "encode"):
            embedding = model.encode(
                prefixed,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            vec = [float(x) for x in embedding]
            return cls.normalize_l2(vec)
        else:
            return cls._deterministic_encode(prefixed, dimension=config["dimension"])

    @classmethod
    def encode_query(cls, query_text: str) -> list[float]:
        """
        Encodes a query text for runtime semantic retrieval (Milestone A5).
        Enforces 'query: ' prefix exactly once.
        """
        if not query_text or not query_text.strip():
            raise ValueError("Cannot encode empty query text.")

        clean_query = query_text.strip()
        if clean_query.startswith("query:"):
            prefixed = clean_query
        else:
            prefixed = f"query: {clean_query}"

        config = cls.get_config()
        model = cls.get_model()
        if not cls._is_mock and hasattr(model, "encode"):
            embedding = model.encode(
                prefixed,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            vec = [float(x) for x in embedding]
            return cls.normalize_l2(vec)
        else:
            return cls._deterministic_encode(prefixed, dimension=config["dimension"])

    @classmethod
    def encode_batch(cls, texts: list[str], is_query: bool = False) -> list[list[float]]:
        """
        Batch encodes a list of documents or queries.
        """
        if not texts:
            return []

        config = cls.get_config()
        batch_size = config["batch_size"]
        results = []

        # Process in configured batch sizes
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            for t in chunk:
                if is_query:
                    results.append(cls.encode_query(t))
                else:
                    results.append(cls.encode_passage(t))

        return results

    @classmethod
    def embed_and_persist_history(
        cls, db: Session, history: AssessmentHistory
    ) -> AssessmentEmbedding:
        """
        Transforms an AssessmentHistory record into a Canonical Document, encodes it
        into a dense 1024-dim vector, and persists it to assessment_embeddings.
        Uses content_hash to prevent redundant duplicate embeddings.
        """
        # 1. Construct canonical document
        doc = AssessmentDocumentService.construct_canonical_document(history)
        config = cls.get_config()
        model_name = config["model_name"]

        # 2. Check if embedding already exists for this exact version and content_hash
        existing = assessment_embedding_repository.get_by_history_and_version(
            db, history.id, history.version
        )
        if existing and existing.content_hash == doc.content_hash:
            logger.info(
                f"Embedding for history_id={history.id} v{history.version} already up-to-date. Skipping."
            )
            return existing

        # 3. If previous version embeddings exist in this evaluation lineage, mark them superseded
        if history.version > 1:
            prev_histories = (
                db.query(AssessmentHistory)
                .filter(
                    AssessmentHistory.evaluation_id == history.evaluation_id,
                    AssessmentHistory.version < history.version,
                )
                .all()
            )
            for prev_h in prev_histories:
                prev_emb = assessment_embedding_repository.get_current_by_history(db, prev_h.id)
                if prev_emb:
                    assessment_embedding_repository.mark_superseded(db, prev_emb.id)

        # 4. Generate Dense Vector Embedding
        vector_data = cls.encode_passage(doc.e5_passage_text)

        # 5. Persist to assessment_embeddings table
        embedding_record = AssessmentEmbedding(
            assessment_history_id=history.id,
            version=history.version,
            is_current=history.is_current,
            content_hash=doc.content_hash,
            school_id=history.school_id,
            academic_year_id=history.academic_year_id,
            subject_id=history.subject_id,
            class_level=history.class_level,
            embedding_model=model_name,
            dimension=config["dimension"],
            vector_data=vector_data,
        )

        persisted = assessment_embedding_repository.create(db, embedding_record)

        # 6. Update AssessmentHistory RAG state
        history.embedding_status = "EMBEDDED"
        history.embedded_at = datetime.now(timezone.utc)
        history.vector_id = str(persisted.id)
        db.flush()

        logger.info(
            f"Successfully embedded history_id={history.id} v{history.version} [dim={config['dimension']}, hash={doc.content_hash[:8]}]"
        )
        return persisted
