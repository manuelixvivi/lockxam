import json
from typing import Any, Dict, List, Optional, Union

VALIDATION_PROMPT_VERSION = "validation_v1.0"

VALIDATION_SYSTEM_PROMPT = """You are an expert pedagogical consistency validator (LLM-based Rubric Consistency Validator).
Your task is to detect potential inconsistencies, contradictions, omissions, or misalignments between:
1. The exam Question
2. The teacher-provided Answer Key
3. The teacher-provided Rubric criteria

CRITICAL ARCHITECTURAL PRINCIPLES:
1. TEACHER REMAINS THE ULTIMATE AUTHORITY: You provide advisory review signals (VALID, SUSPICIOUS, INVALID). You never automatically mutate or override teacher data.
2. CONSERVATIVE BEHAVIOR: If you are uncertain or if an answer key uses different wording/synonyms for equivalent concepts, do NOT flag as INVALID. Treat equivalent concepts as VALID, or classify as SUSPICIOUS if genuinely ambiguous.
3. CONTRADICTION & MISMATCH DETECTION: Flag as INVALID only when the answer key/rubric clearly contradicts the question, answers a completely different topic (e.g. photosynthesis for mitochondria), or presents impossible grading criteria.
4. Output strictly raw valid JSON matching the specified schema."""


def build_validation_prompt(
    question: str,
    answer_key: str,
    rubric: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    question_type: str = "essay",
    subject: str = "Umum",
    grade_level: str = "SMA",
    additional_context: Optional[str] = None,
) -> str:
    """Builds user prompt for Rubric & Answer Key validation."""
    rubric_str = (
        json.dumps(rubric, indent=2, ensure_ascii=False)
        if rubric
        else "(Tidak disertakan rubrik terpisah)"
    )

    prompt = f"""Lakukan analisis konsistensi mendalam terhadap butir soal, kunci jawaban, dan rubrik penilaian berikut:

INFORMASI BUTIR ASESMEN:
Mata Pelajaran: {subject}
Jenjang: {grade_level}
Tipe Soal: {question_type}

PERTANYAAN SOAL:
{question}

KUNCI JAWABAN GURU:
{answer_key if answer_key else "(Kunci jawaban kosong)"}

RUBRIK PENILAIAN GURU:
{rubric_str}"""

    if additional_context:
        prompt += f"\n\nKonteks Kurikulum Tambahan:\n{additional_context}"

    prompt += """

TUGAS VALIDASI ANDA:
1. Pahami maksud utama dari kalimat PERTANYAAN SOAL.
2. Analisis KUNCI JAWABAN dan RUBRIK yang diberikan guru:
   - Apakah kunci jawaban secara logis dan ilmiah menjawab pertanyaan?
   - Apakah rubrik penilaian mengukur kompetensi yang relevan dengan pertanyaan?
   - Apakah terdapat kontradiksi fatal (misal: soal bertanya fungsi mitokondria, tetapi kunci/rubrik berisi fotosintesis pada kloroplas)?
   - Apakah terdapat kriteria yang mustahil dipenuhi atau ambigu?
3. Toleransi Sinonim & Konsep Ekuivalen: Jangan menyalahkan guru hanya karena perbedaan diksi/istilah jika konsep substansialnya sama (misal: "ATP/energi" untuk mitokondria adalah VALID).
4. Tetapkan Status Validasi:
   - "VALID": Kunci dan rubrik konsisten, tepat, dan relevan dengan pertanyaan soal.
   - "SUSPICIOUS": Terdapat ketidakjelasan, ambiguitas, atau kriteria yang berpotensi membingungkan siswa; disarankan guru melakukan review.
   - "INVALID": Terdapat kontradiksi faktual nyata, topik sama sekali berbeda, atau kunci jawaban salah secara fundamental terhadap pertanyaan.

FORMAT OUTPUT (JSON MURNI TANPA MARKDOWN):
{
  "status": "VALID" | "SUSPICIOUS" | "INVALID",
  "confidence": 0.95,
  "reason": "Penjelasan komprehensif mengapa status tersebut diberikan.",
  "issues": [
    {
      "severity": "INFO" | "WARNING" | "ERROR",
      "category": "CONTRADICTION" | "MISSING_REQUIREMENT" | "IRRELEVANT_CRITERIA" | "AMBIGUITY" | "FACTUAL_INCONSISTENCY",
      "description": "Rincian temuan spesifik.",
      "suggestion": "Saran perbaikan untuk guru."
    }
  ],
  "suggested_review": true | false
}"""
    return prompt
