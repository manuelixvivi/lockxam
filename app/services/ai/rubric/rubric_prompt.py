RUBRIC_PROMPT_VERSION = "rubric_v2.0"

RUBRIC_SYSTEM_PROMPT = """You are a professional educational rubric architect (GPT-OSS 120B Machine-Readable Rubric Architect).
Your sole purpose is to analyze exam questions, answer keys, and pedagogical context to produce precise, machine-readable assessment rubrics.

CRITICAL ARCHITECTURAL BOUNDARIES:
1. You ONLY generate rubrics, learning outcomes, key concepts, and cognitive classifications.
2. You do NOT evaluate student answers.
3. You do NOT compute student scores.
4. You do NOT generate student grading feedback.
5. You output strictly raw valid JSON without markdown formatting or conversational filler."""


def build_rubric_prompt(
    question: str,
    answer_key: str,
    question_type: str = "essay",
    subject: str = "Umum",
    grade_level: str = "SMA",
    education_class: str = "Kelas 11",
    additional_context: str = None,
) -> str:
    """Constructs the prompt for AI Rubric Generation."""
    prompt = f"""Tugasmu adalah menganalisis pertanyaan soal dan kunci jawaban berikut, lalu menghasilkan Machine-Readable Assessment Rubric dalam format JSON murni.

INFORMASI SOAL:
Mata Pelajaran: {subject}
Jenjang Target: {grade_level} ({education_class})
Tipe Input: {question_type}
Pertanyaan:
{question}

Kunci Jawaban Guru:
{answer_key}"""

    if additional_context:
        prompt += f"\n\nKonteks Kurikulum Tambahan:\n{additional_context}"

    prompt += """

PETUNJUK UTAMA:
1. Tentukan TIPE SOAL: "ENUMERASI" (jika meminta menyebutkan/mendaftarkan poin secara eksplisit) atau "PROSEDURAL" (jika esai penjelasan/deskripsi/analisis).
2. Tentukan level kognitif Bloom (C1-C6) dan tingkat kompleksitas soal (0-100).
3. DILARANG MENGULANG TEKS RUBRIK YANG SAMA. Setiap kriteria harus unik.
4. ALIGNMENT KE PERTANYAAN: Buat 1 hingga 4 kriteria rubrik yang BENAR-BENAR diminta oleh kalimat pertanyaan. Jika pertanyaan hanya meminta 1 hal utama, buat 1 RUBRIK DENGAN BOBOT 100%. Total bobot seluruh kriteria WAJIB tepat 100.
5. Setiap kriteria rubrik wajib menyertakan atribut:
   - "ku_id": ID unik ("C1", "C2", dst)
   - "text": Pernyataan Learning Outcome (ringkas, 6-15 kata)
   - "weight": Persentase bobot (angka 0-100, total = 100)
   - "bloom_level": Level kognitif Bloom ("C1"-"C6")
   - "required_concepts": Daftar kata/frasa kunci wajib (array of strings)
   - "acceptable_variations": Daftar sinonim atau variasi kata yang diterima (array of strings)
   - "partial_credit_rules": Aturan pembobotan sebagian (array of { "condition": str, "score": float })

FORMAT OUTPUT (JSON MURNI TANPA MARKDOWN):
{
  "question_type": "PROSEDURAL",
  "bloom_level": "C3",
  "complexity_score": 60,
  "concepts": ["konsep_1", "konsep_2"],
  "rubric": [
    {
      "ku_id": "C1",
      "text": "Menjelaskan konsep utama secara lengkap dan tepat",
      "weight": 100,
      "bloom_level": "C3",
      "required_concepts": ["kata_kunci_1", "kata_kunci_2"],
      "acceptable_variations": ["sinonim_1", "sinonim_2"],
      "partial_credit_rules": [
        {"condition": "Menjelaskan konsep utama tanpa rincian pendukung", "score": 50}
      ]
    }
  ]
}"""
    return prompt
