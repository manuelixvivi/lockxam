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
    "Dokumen ini berisi penjelasan lengkap mengenai alur kerja Artificial Intelligence (AI) pada sistem Equigrade x Lockxam, dengan penjabaran titik pemanggilan (triggers) model, proses embedding, inferensi LLM, serta pendekatan sistematis tanpa Fine-Tuning statis.\n"
)

# BAB I
doc.add_heading("BAB I: PENERIMAAN REQUEST & STRUKTUR INPUT (SCHEMA)", level=1)
doc.add_paragraph(
    "Tahap pertama terjadi saat aplikasi guru atau siswa memicu endpoint API Grading di backend. Sistem tidak langsung memanggil LLM."
)
doc.add_paragraph(
    "Backend FastAPI menyusun semua data mentah ke dalam sebuah struktur Data Class (Pydantic Schema) bernama GradingEvaluateRequest untuk melakukan sanitasi data. Tujuan utama tahap ini adalah mengisolasi data (Multi-Tenant) agar evaluasi antarsekolah tidak bercampur."
)
add_code_block(
    doc,
    """class GradingEvaluateRequest(BaseModel):
    # Core Exam Data
    question: str = Field(None, description="Teks pertanyaan ujian")
    student_answer: str = Field(..., description="Jawaban mentah dari siswa")
    # ... Parameter validasi lainnya ...
""",
)

# BAB II
doc.add_heading("BAB II: PEMANGGILAN EMBEDDING & VECTOR SEARCH (RAG)", level=1)
doc.add_paragraph(
    'Tahap ini HANYA dipanggil jika fitur RAG (Retrieval-Augmented Generation) atau "Pencarian Historis" diaktifkan oleh sistem/guru.'
)
doc.add_heading("2.1 Proses Embedding (Vektorisasi)", level=2)
doc.add_paragraph(
    "Sebelum mencari jawaban serupa, teks jawaban siswa dikirim (dilempar) ke Model Embedding (misalnya text-embedding-3-small). Model ini mengubah teks bahasa manusia menjadi deretan angka (Matriks Vektor) berdimensi tinggi."
)
doc.add_heading("2.2 Vector Search (Pencarian Kemiripan)", level=2)
doc.add_paragraph(
    "Setelah diubah menjadi angka, backend memanggil database vektor untuk mengukur jarak (Cosine Similarity) antara jawaban siswa saat ini dengan jawaban historis siswa lain di masa lalu."
)
add_code_block(
    doc,
    """if request.rag_enabled:
    # 1. Pemanggilan Embedding & Database Vektor terjadi di sini
    rag_cases = vector_search_service.search_similar_answers(
        student_answer=request.student_answer
    )
    rag_context = _format_rag_context(rag_cases)
""",
)

# BAB III
doc.add_heading("BAB III: PROMPT ENGINEERING & PEMANGGILAN LLM (INFERENSI)", level=1)
doc.add_heading("3.1 Pemanggilan Model LLM", level=2)
doc.add_paragraph(
    "Setelah konteks sejarah (RAG) dan rubrik penilaian siap, backend menggabungkannya menjadi satu Prompt Instruksi raksasa. Barulah pada titik ini sistem melakukan panggilan API (API Call) ke server Large Language Model (misal GPT-OSS 120B atau model LLaMA via Groq)."
)
doc.add_paragraph(
    "LLM bertugas melakukan inferensi semantik (memahami teks dan memberikan skor pencapaian) lalu mengembalikan output dalam format JSON murni."
)

doc.add_heading("3.2 Catatan Mengenai Fine-Tuning", level=2)
doc.add_paragraph(
    "Equigrade x Lockxam menggunakan pendekatan In-Context Learning (RAG + Prompt Engineering) yang sangat kuat, sehingga TIDAK menggunakan Fine-Tuning model statis secara berkala."
)
doc.add_paragraph("Alasan tidak menggunakan Fine-Tuning:")
p_ft = doc.add_paragraph()
p_ft.add_run("1. Skalabilitas Multi-Mata Pelajaran: ").bold = True
p_ft.add_run(
    'Fine-Tuning akan membuat AI bias ke satu mata pelajaran tertentu. Dengan RAG, AI bertindak layaknya "kertas kosong yang cerdas" yang bisa langsung menilai Fisika, Sejarah, atau Matematika murni berdasarkan Rubrik yang diberikan saat itu juga (Zero-Shot Adaptability).\n'
)
p_ft.add_run("2. Keamanan Data: ").bold = True
p_ft.add_run(
    "Fine-Tuning dapat menghafal data sekolah tertentu. Dengan RAG, data historis tetap berada di database dan hanya dipanggil secara ketat sesuai tenant (school_id)."
)


# BAB IV
doc.add_heading("BAB IV: VALIDASI MATEMATIKA DETERMINISTIK (POST-PROCESSING)", level=1)
doc.add_paragraph(
    "Tahap ini dipanggil SETELAH sistem menerima balasan JSON dari LLM. Backend Equigrade tidak menelan mentah-mentah hasil LLM. Sistem melakukan komputasi deterministik (Post-Processing) secara lokal di server untuk memastikan kualitas jawaban."
)

doc.add_heading("4.1 Rumus Perhitungan Skor Skala (Rubric Scaling)", level=2)
p_rumus1 = doc.add_paragraph("Skor Akhir = (Total Persentase Achieved / 100) x Skor Maksimal")
p_sim1 = doc.add_paragraph()
p_sim1.add_run("Simulasi: ").bold = True
p_sim1.add_run(
    "Soal skor maksimal 8.0 poin. LLM memberi kriteria C1 (100%) dan C2 (50%). Rata-rata 75%. Maka Skor Akhir = (75 / 100) x 8.0 = 6.0 Poin."
)

doc.add_heading("4.2 Rumus Cakupan Konsep (Concept Coverage)", level=2)
p_rumus2 = doc.add_paragraph(
    "Concept Coverage = (Jumlah Kata Kunci Ditemukan / Total Kata Kunci Diwajibkan) x 100%"
)
p_sim2 = doc.add_paragraph()
p_sim2.add_run("Simulasi: ").bold = True
p_sim2.add_run(
    'Kata wajib ["Air", "Menopang", "Mineral"] (3 kata). Siswa menjawab "Menyerap air" (1 kata cocok). Coverage = (1 / 3) x 100% = 33%.'
)

doc.add_heading("4.3 Rumus Kemiripan Semantik (Jaccard Similarity)", level=2)
p_rumus3 = doc.add_paragraph(
    "Jaccard Similarity = (Jumlah Kata Beririsan / Jumlah Total Kata Unik Gabungan) x 100%"
)
p_sim3 = doc.add_paragraph()
p_sim3.add_run("Simulasi: ").bold = True
p_sim3.add_run(
    'Sistem membuang stopwords ("dan"). Kunci: {menyerap, air, menopang} (3 kata). Siswa: {menyerap, air} (2 kata). Irisan: 2. Gabungan Total: 3. Similarity = (2 / 3) x 100% = 67%.'
)


# BAB V
doc.add_heading("BAB V: PENENTUAN CONFIDENCE & KEPUTUSAN OUTPUT", level=1)
doc.add_paragraph(
    "Tahap terakhir yang dipanggil sebelum mengirimkan response ke aplikasi Guru adalah penentuan Confidence Level. Sistem memodifikasi JSON hasil LLM dengan label keamanan."
)

add_code_block(
    doc,
    """@model_validator(mode="before")
@classmethod
def populate_root_confidence(cls, data: Any) -> Any:
    conf_val = float(data.get("confidence", 0.85))
    if conf_val >= 0.90: data["confidence_level"] = "HIGH"
    elif conf_val >= 0.75: data["confidence_level"] = "MEDIUM"
    else: data["confidence_level"] = "LOW"
""",
)
doc.add_paragraph(
    "Output akhirnya menampilkan Status Review (Auto Accept / Needs Review) beserta Feedback Pedagogis sebelum disimpan secara permanen ke Database (PostgreSQL)."
)

file_path = "C:/Users/irul2/Desktop/Laporan_Arsitektur_Alur_AI_Equigrade.docx"
doc.save(file_path)
print(f"Saved to {file_path}")
