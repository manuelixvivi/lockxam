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

# BAB I
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

# BAB IV (EXPANDED WITH FORMULAS)
doc.add_heading("BAB IV: RUMUS PERHITUNGAN DAN SIMULASI (DETERMINISTIK)", level=1)
doc.add_paragraph(
    "Backend Equigrade menggunakan kombinasi beberapa perhitungan matematis deterministik untuk menentukan skor akhir dan metrik akurasi jawaban siswa. Berikut adalah 3 (tiga) rumus utama dan simulasinya:"
)

# 4.1 Rubrik
doc.add_heading("4.1 Rumus Perhitungan Skor Skala (Rubric Scaling)", level=2)
doc.add_paragraph(
    "LLM menentukan tingkat pencapaian (achieved) untuk setiap rubrik dari rentang 0% hingga 100%. Sistem kemudian merata-ratakannya (atau berdasarkan pembobotan) dan mengalikannya dengan Skor Maksimal Soal."
)
p_rumus1 = doc.add_paragraph()
p_rumus1.add_run("Rumus Dasar:\n").bold = True
p_rumus1.add_run("Skor Akhir = (Total Persentase Achieved / 100) x Skor Maksimal")

p_sim1 = doc.add_paragraph()
p_sim1.add_run("Contoh Simulasi:\n").bold = True
p_sim1.add_run('- Soal: "Sebutkan dan jelaskan 2 fungsi akar tumbuhan!"\n')
p_sim1.add_run("- Skor Maksimal Soal: 8.0 poin\n")
p_sim1.add_run("- Penilaian AI pada Kriteria C1 (Kebenaran Fakta): 100%\n")
p_sim1.add_run("- Penilaian AI pada Kriteria C2 (Tata Bahasa): 50%\n")
p_sim1.add_run("- Total Achieved (Rata-rata): (100% + 50%) / 2 = 75%\n")
p_sim1.add_run("- Perhitungan: (75 / 100) x 8.0\n")
p_sim1.add_run("- Hasil Akhir: Siswa mendapatkan skor 6.0 poin.")

# 4.2 Concept Coverage
doc.add_heading("4.2 Rumus Cakupan Konsep (Concept Coverage)", level=2)
doc.add_paragraph(
    "Sistem mengevaluasi berapa banyak kata kunci spesifik (mandatory concepts) yang dicantumkan secara harfiah oleh siswa dalam jawabannya."
)
add_code_block(
    doc,
    """@staticmethod
def _calc_concept_coverage(student_ans: str, concepts: List[str]) -> int:
    matched = sum(1 for c in concepts if c.lower() in student_lower)
    return round((matched / len(concepts)) * 100)
""",
)
p_rumus2 = doc.add_paragraph()
p_rumus2.add_run("Rumus Dasar:\n").bold = True
p_rumus2.add_run(
    "Concept Coverage = (Jumlah Kata Kunci Yang Ditemukan / Total Kata Kunci Diwajibkan) x 100%"
)

p_sim2 = doc.add_paragraph()
p_sim2.add_run("Contoh Simulasi:\n").bold = True
p_sim2.add_run(
    '- Kata Kunci Wajib (Concepts): ["Air", "Menopang", "Mineral"] (Total: 3 kata kunci)\n'
)
p_sim2.add_run('- Jawaban Siswa: "Akar menyerap air dari tanah."\n')
p_sim2.add_run('- Kata kunci yang ditemukan: ["Air"] (Total: 1 kata kunci)\n')
p_sim2.add_run("- Perhitungan: (1 / 3) x 100%\n")
p_sim2.add_run("- Hasil Akhir: Concept Coverage 33%")


# 4.3 Jaccard Similarity
doc.add_heading("4.3 Rumus Kemiripan Semantik (Jaccard Similarity)", level=2)
doc.add_paragraph(
    "Backend membuang kata hubung (stopwords) dari jawaban siswa dan kunci jawaban, lalu menghitung persentase kata yang persis sama antara keduanya menggunakan metrik Jaccard Index."
)
add_code_block(
    doc,
    """@staticmethod
def _calc_jaccard_similarity(student_ans: str, answer_key: str) -> int:
    stopwords = {"dan", "atau", "yang", "untuk", "pada", "adalah"}
    w1 = {w for w in re.findall(r"\\b[a-zA-Z0-9]{3,}\\b", student_ans.lower()) if w not in stopwords}
    w2 = {w for w in re.findall(r"\\b[a-zA-Z0-9]{3,}\\b", answer_key.lower()) if w not in stopwords}

    intersection = w1.intersection(w2)
    union = w1.union(w2)
    return round((len(intersection) / len(union)) * 100)
""",
)
p_rumus3 = doc.add_paragraph()
p_rumus3.add_run("Rumus Dasar:\n").bold = True
p_rumus3.add_run(
    "Jaccard Similarity = (Jumlah Kata Beririsan / Jumlah Total Kata Unik Gabungan) x 100%"
)

p_sim3 = doc.add_paragraph()
p_sim3.add_run("Contoh Simulasi:\n").bold = True
p_sim3.add_run('- Kunci Jawaban: "Menyerap air dan menopang tumbuhan"\n')
p_sim3.add_run("- Ekstraksi Unik Kunci: {menyerap, air, menopang, tumbuhan}\n")
p_sim3.add_run('- Jawaban Siswa: "Menyerap air"\n')
p_sim3.add_run("- Ekstraksi Unik Siswa: {menyerap, air}\n")
p_sim3.add_run("- Irisan (Sama): {menyerap, air} (2 Kata)\n")
p_sim3.add_run("- Gabungan Total: {menyerap, air, menopang, tumbuhan} (4 Kata)\n")
p_sim3.add_run("- Perhitungan: (2 / 4) x 100%\n")
p_sim3.add_run("- Hasil Akhir: Kemiripan (Similarity) 50%")


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

file_path = "C:/Users/irul2/Desktop/Laporan_Simulasi_Perhitungan_AI_Equigrade.docx"
doc.save(file_path)
print(f"Saved to {file_path}")
