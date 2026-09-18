import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

doc = docx.Document()


def add_code_block(doc, code_text):
    p = doc.add_paragraph()
    run = p.add_run(code_text)
    run.font.name = "Courier New"
    run.font.size = Pt(9)


# Title
title = doc.add_heading("LAPORAN DOKUMENTASI PROSES KERJA AI (EQUIGRADE X LOCKXAM)", 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph(
    "Dokumen ini berisi penjelasan lengkap mengenai alur kerja Artificial Intelligence (AI) pada sistem Equigrade x Lockxam, mulai dari penerimaan input soal hingga menghasilkan output penilaian akhir.\n"
)

# BAB I (EXPANDED)
doc.add_heading("BAB I: PENDAHULUAN & STRUKTUR INPUT (SCHEMA)", level=1)
doc.add_paragraph(
    "Tahap pertama dari proses penilaian otomatis (AI Auto-Grading) adalah validasi dan standardisasi input. Sebelum sistem berinteraksi dengan Large Language Model (LLM), backend FastAPI harus menyusun semua data mentah yang datang dari aplikasi guru/siswa ke dalam sebuah struktur Data Class (menggunakan library Pydantic) bernama GradingEvaluateRequest."
)
doc.add_paragraph(
    "Tujuan utama dari skema ini adalah memastikan bahwa AI menerima konteks yang kaya, terstandarisasi, dan yang paling penting, aman dari kebocoran data antar-sekolah (Multi-Tenant)."
)

doc.add_heading("1.1 Deklarasi Pydantic Schema", level=2)
add_code_block(
    doc,
    """class GradingEvaluateRequest(BaseModel):
    # Core Exam Data
    question: Optional[str] = Field(None, description="Teks pertanyaan ujian")
    student_answer: str = Field(..., description="Jawaban mentah dari siswa")
    answer_key: Optional[str] = Field("", description="Kunci jawaban resmi dari guru")

    # Validation & Scale Parameters
    rubric: Optional[List[Dict[str, Any]]] = Field(None, description="Kriteria rubrik penilaian")
    concepts: Optional[List[str]] = Field(default_factory=list, description="Kata kunci konsep")
    max_score: float = Field(10.0, description="Skor maksimal soal (Dynamic Scaling)")

    # Demographics & Context
    question_type: Optional[str] = Field("essay", description="Tipe soal: 'essay' atau 'short_answer'")
    education_level: Optional[str] = Field("SMA", description="Target jenjang sekolah")
    education_class: Optional[str] = Field("Kelas 11", description="Target tingkatan kelas")

    # Multi-tenant and RAG Parameters
    school_id: Optional[int] = Field(None, description="ID Tenant Sekolah (Isolasi Data)")
    subject_id: Optional[int] = Field(None, description="ID Mata Pelajaran")
    rag_enabled: Optional[bool] = Field(None, description="Togle RAG historis")
    top_k: Optional[int] = Field(None, description="Jumlah pencarian riwayat batas maksimal")
""",
)

doc.add_heading("1.2 Penjelasan Komponen Input", level=2)
doc.add_paragraph(
    "1. Core Exam Data (Data Inti Ujian): Mengumpulkan teks pertanyaan, kunci jawaban, dan teks jawaban mentah siswa. Variabel ini bersifat mutlak dan menjadi basis utama untuk analisis AI.\n"
)
doc.add_paragraph(
    "2. Validation & Scale Parameters: Terdapat max_score yang memungkinkan Dynamic Scaling. Jika soal bernilai maksimal 4 poin, AI secara fleksibel akan merumuskan penilaian skala 0-100 terlebih dahulu, kemudian mengonversinya secara proporsional ke rentang 0-4. Selain itu, terdapat array rubrics yang berisi kriteria penilaian beserta bobot masing-masing (misal: C1 Tata Bahasa 30%, C2 Konten 70%).\n"
)
doc.add_paragraph(
    "3. Demographics (Demografi Kelas): Parameter education_level dan education_class (contoh: SMA Kelas 11) digunakan untuk melakukan kalibrasi gaya bahasa AI. Feedback yang diberikan AI untuk siswa SD akan menggunakan kosakata yang jauh berbeda dan lebih sederhana dibandingkan feedback untuk siswa SMA.\n"
)
doc.add_paragraph(
    "4. Multi-Tenant Data Isolation (Isolasi Data): Kehadiran school_id menjamin bahwa jika RAG (Pencarian Historis) diaktifkan, AI HANYA akan mencari referensi penilaian dari sekolah yang bersangkutan. Ini mencegah kebocoran kunci jawaban dari Sekolah A ke siswa di Sekolah B."
)

doc.add_heading("1.3 Fallback Method (Kompatibilitas Mundur)", level=2)
doc.add_paragraph(
    "Karena aplikasi sering mengalami pembaruan (update), skema ini juga dibekali fungsi fallback untuk menjaga agar aplikasi versi lama tetap bisa melakukan grading tanpa error."
)
add_code_block(
    doc,
    """    def get_effective_rubrics(self) -> List[Dict[str, Any]]:
        if self.rubric and isinstance(self.rubric, list):
            return self.rubric
        if self.rubrics and isinstance(self.rubrics, list):
            return self.rubrics
        return []
""",
)
doc.add_paragraph(
    'Penjelasan: Fungsi di atas memastikan baik input JSON menggunakan key "rubric" (versi lama) maupun "rubrics" (versi baru) tetap akan diproses dengan aman oleh backend AI tanpa menyebabkan Internal Server Error (500).'
)


# BAB II
doc.add_heading("BAB II: RAG CONTEXT RETRIEVAL (PENCARIAN HISTORIS)", level=1)
doc.add_paragraph(
    "Jika fitur RAG (Retrieval-Augmented Generation) aktif, sistem mengubah jawaban siswa menjadi angka matriks (vector embeddings), lalu mencari jawaban siswa lain di masa lalu menggunakan algoritma Cosine Similarity."
)
add_code_block(
    doc,
    """rag_context = ""
if request.rag_enabled:
    rag_cases = vector_search_service.search_similar_answers(
        db=db,
        school_id=request.school_id,
        question_text=request.question,
        student_answer=request.student_answer,
        top_k=request.top_k
    )
    rag_context = _format_rag_context(rag_cases)
""",
)
doc.add_paragraph(
    'Penjelasan Kode:\nJika ditemukan jawaban yang tingkat kemiripannya di atas batas (threshold), data penilaian historis tersebut disuntikkan ke dalam instruksi AI sebagai "buku panduan" (rag_context). Ini memaksa AI untuk menilai secara konsisten dengan penilaian guru di masa lalu.'
)

# BAB III
doc.add_heading("BAB III: PROMPT ENGINEERING & EKSEKUSI LLM", level=1)
doc.add_paragraph(
    "Semua variabel digabungkan ke dalam sebuah System Prompt (Instruksi Sistem) yang memiliki lapisan pertahanan dari Prompt Injection dan panduan rubrik (Skala 0-100)."
)
add_code_block(
    doc,
    '''prompt = f"""Kamu adalah penilai esai yang adil dan objektif untuk jenjang {education_level}.

PERTANYAAN SOAL: {question}
KUNCI JAWABAN GURU: {answer_key}
RUBRIK PENILAIAN RESMI: {rubric_display}
JAWABAN SISWA: {student_answer}

ATURAN PENILAIAN (Achieved 0-100):
- 100: Sangat lengkap, tepat, menjelaskan seluruh poin kunci.
- 50: Benar secara garis besar tapi penjelasan dangkal.
- 0: Jawaban salah atau tidak relevan.

{rag_context_block}
FORMAT OUTPUT (JSON MURNI TANPA MARKDOWN): ..."""
''',
)
doc.add_paragraph(
    "Penjelasan Kode:\nPrompt ini kemudian dikirim ke server LLM (misalnya GPT-OSS 120B / LLaMA). Output yang diminta secara ketat harus berbentuk struktur JSON murni yang mencantumkan persentase ketercapaian per kriteria rubrik."
)

# BAB IV
doc.add_heading("BAB IV: VALIDASI MATEMATIKA DETERMINISTIK", level=1)
doc.add_paragraph(
    "Setelah LLM memberikan nilainya, backend melakukan perhitungan matematika tambahan (Post-Processing) untuk memastikan AI tidak berhalusinasi. Terdapat dua rumus utama:"
)
doc.add_heading("4.1 Concept Coverage (Cakupan Konsep)", level=2)
add_code_block(
    doc,
    """@staticmethod
def _calc_concept_coverage(student_ans: str, concepts: List[str]) -> int:
    if not concepts:
        return 100
    student_lower = student_ans.lower()
    matched = sum(1 for c in concepts if c.lower() in student_lower)
    return round((matched / len(concepts)) * 100)
""",
)
doc.add_paragraph(
    "Penjelasan: Menghitung persentase kata kunci wajib yang diketik oleh siswa (Irisan Kata Kunci / Total Kata Kunci * 100)."
)

doc.add_heading("4.2 Jaccard Similarity", level=2)
add_code_block(
    doc,
    """@staticmethod
def _calc_jaccard_similarity(student_ans: str, answer_key: str) -> int:
    stopwords = {"dan", "atau", "yang", "untuk", "pada", "adalah"}
    w1 = {w for w in re.findall(r"\\b[a-zA-Z0-9]{3,}\\b", student_ans.lower()) if w not in stopwords}
    w2 = {w for w in re.findall(r"\\b[a-zA-Z0-9]{3,}\\b", answer_key.lower()) if w not in stopwords}

    if not w1 or not w2:
        return 0
    intersection = w1.intersection(w2)
    union = w1.union(w2)
    return round((len(intersection) / len(union)) * 100)
""",
)
doc.add_paragraph(
    "Penjelasan: Menghapus kata hubung (stopwords), lalu mencari irisan semantik menggunakan rumus Jaccard (Jumlah Kata Beririsan / Jumlah Total Kata Unik Gabungan * 100)."
)

# BAB V
doc.add_heading("BAB V: PENENTUAN CONFIDENCE & KEPUTUSAN OUTPUT", level=1)
doc.add_paragraph(
    "Tahap terakhir adalah mengukur rasio keyakinan AI dan memberikan keputusan apakah nilai bisa langsung diterima (Auto Accept) atau harus diverifikasi manual oleh guru (Manual Review Required)."
)
add_code_block(
    doc,
    """@model_validator(mode="before")
@classmethod
def populate_root_confidence(cls, data: Any) -> Any:
    conf_val = float(data.get("confidence", 0.85))

    if conf_val >= 0.90:
        data["confidence_level"] = "HIGH"
    elif conf_val >= 0.75:
        data["confidence_level"] = "MEDIUM"
    else:
        data["confidence_level"] = "LOW"

    data["review_required"] = conf_val < 0.90
    return data
""",
)
doc.add_paragraph(
    "Penjelasan Kode:\nOutput akhir berupa JSON ini kemudian dikirim kembali ke Frontend Lockxam untuk ditampilkan pada dashboard penilaian guru dalam bentuk persentase, grafik gauge (speedometer), dan feedback pedagogis (Academic Rationale)."
)

file_path = "C:/Users/irul2/Desktop/Laporan_Lengkap_Proses_AI_Equigrade_Revisi.docx"
doc.save(file_path)
print(f"Saved to {file_path}")
