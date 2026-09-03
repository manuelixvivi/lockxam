from app.models.ai.assessment_history import AssessmentHistory
from app.services.ai.assessment_document_service import (
    AssessmentDocumentService,
    CanonicalAssessmentDocument,
)


def create_sample_history(
    version: int = 1,
    final_score: float = 8.5,
    teacher_feedback: str = "Penjelasan Hukum Dalton sudah tepat pada perbandingan massa.",
    student_answer: str = "Hukum Dalton menyatakan perbandingan massa unsur yang bergabung adalah bulat dan sederhana.",
    question_text: str = "Jelaskan Hukum Perbandingan Berganda Dalton!",
    answer_key: str = "Bila dua unsur membentuk dua senyawa atau lebih...",
    rubrics_json: list = None,
) -> AssessmentHistory:
    if rubrics_json is None:
        rubrics_json = [
            {
                "name": "Konsep Dasar",
                "points": 5,
                "description": "Menyebutkan dua unsur membentuk senyawa",
            },
            {
                "name": "Perbandingan Massa",
                "points": 5,
                "description": "Menjelaskan massa perbandingan bulat sederhana",
            },
        ]

    return AssessmentHistory(
        id=101,
        public_id="hist-uuid-001",
        school_id=1,
        academic_year_id=1,
        subject_id=10,
        subject_name="Kimia",
        class_level="XI",
        evaluation_id=501,
        exam_attempt_id=201,
        question_id=301,
        exam_teacher_id=5,
        finalized_by_teacher_id=5,
        version=version,
        is_current=True,
        question_text=question_text,
        question_type="ES",
        answer_key=answer_key,
        rubrics_json=rubrics_json,
        max_score=10.0,
        student_answer=student_answer,
        teacher_score=final_score,
        teacher_feedback=teacher_feedback,
        final_score=final_score,
        score_delta=0.0,
        is_rag_eligible=True,
        embedding_status="PENDING",
    )


# ── TEST 1: Basic Canonical Document Generation ─────────────────────────────
def test_basic_canonical_document_generation():
    hist = create_sample_history()
    doc = AssessmentDocumentService.construct_canonical_document(hist)

    assert isinstance(doc, CanonicalAssessmentDocument)
    assert doc.history_id == 101
    assert doc.version == 1
    assert doc.school_id == 1
    assert doc.subject_name == "Kimia"
    assert doc.class_level == "XI"
    assert doc.final_score == 8.5
    assert doc.max_score == 10.0

    # Verify sections exist
    assert "[Mata Pelajaran]: Kimia" in doc.canonical_text
    assert "[Jenjang Kelas]: XI" in doc.canonical_text
    assert "[Pertanyaan / Soal]:" in doc.canonical_text
    assert "[Kunci Jawaban / Konsep Kunci]:" in doc.canonical_text
    assert "[Rubrik Penilaian]:" in doc.canonical_text
    assert "[Jawaban Siswa]:" in doc.canonical_text
    assert "[Evaluasi & Koreksi Guru]:" in doc.canonical_text
    assert "[Skor Guru]: 8.5 / 10" in doc.canonical_text

    # Verify E5 prefix
    assert doc.e5_passage_text.startswith("passage: [Mata Pelajaran]: Kimia")


# ── TEST 2: Whitespace & Linebreak Normalization ──────────────────────────────
def test_whitespace_and_linebreak_normalization():
    messy_text = "  Baris 1 dengan trailing spaces.   \r\n\r\n\r\n\r\nBaris 2 setelah blank lines. \t\t \n\nBaris 3.  "
    clean = AssessmentDocumentService.clean_and_normalize_text(messy_text)

    # Must convert CRLF to LF, collapse 4 newlines to 2, strip line trailing spaces
    assert "\r" not in clean
    assert "\n\n\n" not in clean
    assert clean.startswith("Baris 1")
    assert clean.endswith("Baris 3.")


# ── TEST 3: Unicode Normalization (NFKC) ──────────────────────────────────────
def test_unicode_nfkc_normalization():
    # Full-width characters and compatibility forms
    fullwidth_text = "Ｈｕｋｕｍ　Ｄａｌｔｏｎ　２０２６"
    clean = AssessmentDocumentService.clean_and_normalize_text(fullwidth_text)
    assert clean == "Hukum Dalton 2026"


# ── TEST 4: Rubric JSON Deterministic Serialization ──────────────────────────
def test_rubric_json_deterministic_serialization():
    rubrics = [
        {"name": "Relevansi Konsep", "points": 5, "description": "Menyebutkan konsep secara utuh."},
        {"name": "Analisis Data", "points": 5, "description": "Memberikan rincian numerik."},
    ]
    formatted = AssessmentDocumentService.format_rubrics_json(rubrics)
    assert "- Relevansi Konsep (Maks: 5 poin): Menyebutkan konsep secara utuh." in formatted
    assert "- Analisis Data (Maks: 5 poin): Memberikan rincian numerik." in formatted


# ── TEST 5: LaTeX and Mathematical Notation Preservation ────────────────────
def test_latex_and_math_preservation():
    math_q = r"Hitunglah nilai dari \int_{0}^{1} x^2 \,dx dan \frac{\sqrt{a^2 + b^2}}{2}."
    math_ans = r"Hasil integral adalah \left[ \frac{x^3}{3} \right]_0^1 = \frac{1}{3}."
    hist = create_sample_history(question_text=math_q, student_answer=math_ans)
    doc = AssessmentDocumentService.construct_canonical_document(hist)

    # Ensure backslashes, fractions, square roots, and exponents are preserved intact
    assert r"\int_{0}^{1}" in doc.canonical_text
    assert r"\frac{\sqrt{a^2 + b^2}}{2}" in doc.canonical_text
    assert r"\frac{x^3}{3}" in doc.canonical_text
    assert r"\frac{1}{3}" in doc.canonical_text


# ── TEST 6: Empty Optional Teacher Feedback Handling ────────────────────────
def test_empty_optional_feedback_handling():
    hist = create_sample_history(teacher_feedback="")
    doc = AssessmentDocumentService.construct_canonical_document(hist)

    assert "[Evaluasi & Koreksi Guru]:\n(Tidak ada catatan khusus dari guru)" in doc.canonical_text


# ── TEST 7: Indonesian Educational Text Preservation ─────────────────────────
def test_indonesian_educational_text_preservation():
    indo_text = "Hukum Perbandingan Berganda menyatakan bahwa bila dua unsur dapat membentuk lebih dari satu senyawa..."
    hist = create_sample_history(student_answer=indo_text)
    doc = AssessmentDocumentService.construct_canonical_document(hist)

    assert indo_text in doc.canonical_text


# ── TEST 8: Strict PII Exclusion ─────────────────────────────────────────────
def test_strict_pii_exclusion():
    hist = create_sample_history()
    doc = AssessmentDocumentService.construct_canonical_document(hist)

    # Ensure no PII strings appear in canonical text or E5 passage text
    forbidden_tokens = ["Arselio", "student_id", "098", "10.196", "device-fingerprint", "fake_hash"]
    for token in forbidden_tokens:
        assert token not in doc.canonical_text
        assert token not in doc.e5_passage_text


# ── TEST 9: Same Input Produces Same Deterministic Hash ─────────────────────
def test_same_input_produces_identical_hash():
    hist1 = create_sample_history()
    hist2 = create_sample_history()

    doc1 = AssessmentDocumentService.construct_canonical_document(hist1)
    doc2 = AssessmentDocumentService.construct_canonical_document(hist2)

    assert doc1.content_hash == doc2.content_hash
    assert len(doc1.content_hash) == 64  # SHA-256


# ── TEST 10: Different Teacher Correction Produces Different Hash ────────────
def test_different_correction_produces_different_hash():
    hist_orig = create_sample_history(final_score=8.0, teacher_feedback="Cukup baik.")
    hist_corr = create_sample_history(
        final_score=9.5, teacher_feedback="Sangat sempurna setelah verifikasi."
    )

    doc_orig = AssessmentDocumentService.construct_canonical_document(hist_orig)
    doc_corr = AssessmentDocumentService.construct_canonical_document(hist_corr)

    assert doc_orig.content_hash != doc_corr.content_hash


# ── TEST 11: v1 and v2 Produce Independent Documents ─────────────────────────
def test_v1_and_v2_produce_independent_documents():
    hist_v1 = create_sample_history(version=1, final_score=7.0, teacher_feedback="Feedback awal.")
    hist_v2 = create_sample_history(version=2, final_score=9.0, teacher_feedback="Feedback revisi.")

    doc_v1 = AssessmentDocumentService.construct_canonical_document(hist_v1)
    doc_v2 = AssessmentDocumentService.construct_canonical_document(hist_v2)

    assert doc_v1.version == 1
    assert doc_v2.version == 2
    assert doc_v1.final_score == 7.0
    assert doc_v2.final_score == 9.0
    assert doc_v1.content_hash != doc_v2.content_hash


# ── TEST 12: E5 Query Formulation Helper ────────────────────────────────────
def test_e5_query_formulation():
    query_text = AssessmentDocumentService.construct_e5_query_text(
        subject_name="Kimia",
        class_level="XI",
        question_text="Jelaskan Hukum Dalton!",
        student_answer="Dua unsur bereaksi membentuk senyawa...",
        rubrics_json=[{"name": "Konsep", "points": 5}],
    )

    assert query_text.startswith("query: [Mata Pelajaran]: Kimia")
    assert "[Pertanyaan / Soal]:\nJelaskan Hukum Dalton!" in query_text
    assert "[Jawaban Siswa]:\nDua unsur bereaksi membentuk senyawa..." in query_text
