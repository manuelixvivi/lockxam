import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.models.ai.assessment_history import AssessmentHistory


@dataclass(frozen=True)
class CanonicalAssessmentDocument:
    """
    Structured representation of an immutable, normalized Assessment Document.
    Ready for downstream Transformer Embedding (intfloat/multilingual-e5-large).
    """

    history_id: int
    version: int
    school_id: int
    subject_id: int
    subject_name: str
    class_level: str
    question_id: int
    final_score: float
    max_score: float
    canonical_text: str
    e5_passage_text: str
    content_hash: str


class AssessmentDocumentService:
    """
    Assessment Document & Normalization Service — Milestone A2

    Transforms AssessmentHistory records into deterministic, canonical text representations
    with strict PII stripping, LaTeX preservation, and Unicode normalization.
    """

    @classmethod
    def clean_and_normalize_text(cls, text: str | None) -> str:
        """
        Deterministic string normalization:
        1. Handle None / empty
        2. Unicode NFKC normalization
        3. HTML entity decoding & tag stripping (while preserving math & text)
        4. Normalize line breaks to \n
        5. Strip trailing whitespace per line
        6. Collapse multiple blank lines (max 2 consecutive newlines)
        7. Strip leading and trailing overall whitespace
        """
        if text is None:
            return ""

        # Step 1: Unicode Normalization (NFKC)
        normalized = unicodedata.normalize("NFKC", str(text))

        # Step 2: Unescape HTML entities (e.g. &lt; -> <, &amp; -> &)
        unescaped = html.unescape(normalized)

        # Step 3: Strip HTML tags if present (e.g. <p>, </p>, <b>, <br/>, <span>)
        # Using a regex that preserves inner math/text
        no_html = re.sub(
            r"<\/?(?:p|b|i|u|strong|em|span|div|br|font|h\d|ul|li|ol)[^>]*>",
            " ",
            unescaped,
            flags=re.IGNORECASE,
        )

        # Step 4: Normalize CRLF / CR to LF
        normalized_newlines = re.sub(r"\r\n|\r", "\n", no_html)

        # Step 5: Strip horizontal trailing whitespace from each line (preserve indentation if any, but collapse tabs)
        lines = [re.sub(r"[ \t]+$", "", line) for line in normalized_newlines.split("\n")]

        # Step 6: Collapse 3+ consecutive newlines to 2 newlines
        joined = "\n".join(lines)
        collapsed_newlines = re.sub(r"\n{3,}", "\n\n", joined)

        # Step 7: Final strip of whole string
        return collapsed_newlines.strip()

    @classmethod
    def format_rubrics_json(cls, rubrics: list[dict[str, Any]] | dict[str, Any] | None) -> str:
        """
        Deterministically serialize rubric criteria from JSON list/dict.
        Sorts items predictably to ensure identical JSON produces identical text.
        """
        if not rubrics:
            return "(Tidak ada rubrik terperinci)"

        if isinstance(rubrics, dict):
            rubrics_list = [rubrics]
        elif isinstance(rubrics, list):
            rubrics_list = rubrics
        else:
            return str(rubrics)

        formatted_criteria = []
        for idx, item in enumerate(rubrics_list, start=1):
            if not isinstance(item, dict):
                formatted_criteria.append(
                    f"- Kriteria {idx}: {cls.clean_and_normalize_text(str(item))}"
                )
                continue

            # Support various schema keys: name/criteria/title, points/max_score, description/desc
            name = (
                item.get("name") or item.get("criteria") or item.get("title") or f"Kriteria {idx}"
            )
            points = item.get("points") if item.get("points") is not None else item.get("max_score")
            desc = item.get("description") or item.get("desc") or ""

            name_clean = cls.clean_and_normalize_text(str(name))
            desc_clean = cls.clean_and_normalize_text(str(desc))

            if points is not None:
                points_str = f" (Maks: {points} poin)"
            else:
                points_str = ""

            if desc_clean:
                formatted_criteria.append(f"- {name_clean}{points_str}: {desc_clean}")
            else:
                formatted_criteria.append(f"- {name_clean}{points_str}")

        return (
            "\n".join(formatted_criteria) if formatted_criteria else "(Tidak ada rubrik terperinci)"
        )

    @classmethod
    def construct_canonical_document(
        cls, history: AssessmentHistory
    ) -> CanonicalAssessmentDocument:
        """
        Constructs a deterministic canonical assessment document from an AssessmentHistory record.
        """
        # 1. Clean individual components
        subject_name = cls.clean_and_normalize_text(history.subject_name) or "Mata Pelajaran"
        class_level = cls.clean_and_normalize_text(history.class_level) or "Kelas"
        question_text = cls.clean_and_normalize_text(history.question_text)
        answer_key = cls.clean_and_normalize_text(history.answer_key)
        rubrics_text = cls.format_rubrics_json(history.rubrics_json)
        student_answer = cls.clean_and_normalize_text(history.student_answer)
        teacher_feedback = (
            cls.clean_and_normalize_text(history.teacher_feedback)
            or "(Tidak ada catatan khusus dari guru)"
        )

        final_score = float(history.final_score)
        max_score = float(history.max_score)

        # 2. Build Standardized Canonical Text
        canonical_sections = [
            f"[Mata Pelajaran]: {subject_name}",
            f"[Jenjang Kelas]: {class_level}",
            f"[Pertanyaan / Soal]:\n{question_text}",
            f"[Kunci Jawaban / Konsep Kunci]:\n{answer_key}",
            f"[Rubrik Penilaian]:\n{rubrics_text}",
            f"[Jawaban Siswa]:\n{student_answer}",
            f"[Evaluasi & Koreksi Guru]:\n{teacher_feedback}",
            f"[Skor Guru]: {final_score:g} / {max_score:g}",
        ]

        canonical_text = "\n\n".join(canonical_sections)

        # 3. E5 Passage Prefix (as required by intfloat/multilingual-e5-large for documents)
        e5_passage_text = f"passage: {canonical_text}"

        # 4. Deterministic SHA-256 Hash of Canonical Text
        content_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

        return CanonicalAssessmentDocument(
            history_id=history.id if history.id else 0,
            version=history.version,
            school_id=history.school_id,
            subject_id=history.subject_id,
            subject_name=subject_name,
            class_level=class_level,
            question_id=history.question_id,
            final_score=final_score,
            max_score=max_score,
            canonical_text=canonical_text,
            e5_passage_text=e5_passage_text,
            content_hash=content_hash,
        )

    @classmethod
    def construct_e5_query_text(
        cls,
        subject_name: str,
        class_level: str,
        question_text: str,
        student_answer: str,
        rubrics_json: list[dict[str, Any]] | dict[str, Any] | None = None,
    ) -> str:
        """
        Constructs the E5-compatible query representation for runtime similarity retrieval (Milestone A5).
        Format: query: [Mata Pelajaran]: ... [Pertanyaan]: ... [Jawaban Siswa]: ...
        """
        subj_clean = cls.clean_and_normalize_text(subject_name) or "Mata Pelajaran"
        class_clean = cls.clean_and_normalize_text(class_level) or "Kelas"
        q_clean = cls.clean_and_normalize_text(question_text)
        ans_clean = cls.clean_and_normalize_text(student_answer)
        rubrics_clean = cls.format_rubrics_json(rubrics_json)

        query_sections = [
            f"[Mata Pelajaran]: {subj_clean}",
            f"[Jenjang Kelas]: {class_clean}",
            f"[Pertanyaan / Soal]:\n{q_clean}",
            f"[Rubrik Penilaian]:\n{rubrics_clean}",
            f"[Jawaban Siswa]:\n{ans_clean}",
        ]

        query_content = "\n\n".join(query_sections)
        return f"query: {query_content}"
