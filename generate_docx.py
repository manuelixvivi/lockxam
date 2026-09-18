import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = docx.Document()

# Title
title = doc.add_heading("Rumus & Alur Perhitungan Backend AI (Equigrade x Lockxam)", 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph(
    "Sistem penilaian (grading) backend AI pada Equigrade x Lockxam bekerja menggunakan kombinasi analisis linguistik deterministik dan klasifikasi Large Language Model (LLM). Berikut adalah rincian rumus perhitungan dan alur proses yang berjalan di dalam modul grading_service.py."
)

# Section 1
doc.add_heading("1. Pembobotan Berdasarkan Rubrik Penilaian (Rubric Calculation)", level=2)
p1 = doc.add_paragraph(
    "Saat guru menginput rubrik ke sebuah pertanyaan (misalnya C1: Kebenaran Fakta [50%], C2: Tata Bahasa [50%]), AI akan menganalisis kecocokan jawaban siswa pada masing-masing rubrik secara terpisah.\n"
)
p1.add_run("Proses: ").bold = True
p1.add_run(
    "LLM akan menetapkan persentase ketercapaian (achieved: 0% - 100%) untuk setiap kriteria rubrik.\n"
)
p1.add_run("Rumus Nilai Skala (Score): ").bold = True
p1.add_run("(Persentase Total Pencapaian / 100) x Skor Maksimal Soal\n")
p1.add_run("Contoh: ").bold = True
p1.add_run(
    "Jika capaian gabungannya adalah 80% dan nilai maksimal soal itu adalah 10 poin, maka siswa otomatis mendapatkan 8.0 poin."
)

# Section 2
doc.add_heading("2. Algoritma Cakupan Konsep (Concept Coverage)", level=2)
p2 = doc.add_paragraph(
    "AI secara deterministik menghitung kata kunci wajib (mandatory concepts) yang dicari guru pada jawaban siswa.\n"
)
p2.add_run("Rumus: ").bold = True
p2.add_run("(Jumlah Kata Kunci Yang Ditemukan / Total Kata Kunci yang Diwajibkan) x 100%\n")
p2.add_run("Cara Kerja: ").bold = True
p2.add_run(
    'Jika soal memiliki 3 konsep wajib: ["Mitokondria", "ATP", "Respirasi"], namun jawaban siswa hanya memuat "Mitokondria" dan "Respirasi" saja, maka skor pemerataan konsepnya adalah: (2 / 3) * 100% = 67%.'
)

# Section 3
doc.add_heading("3. Perhitungan Kemiripan Jawaban (Jaccard Similarity)", level=2)
p3 = doc.add_paragraph(
    "Untuk soal bertipe jawaban singkat (short answer), backend menggunakan algoritma semantik Jaccard Index.\n"
)
p3.add_run("Cara Kerja: ").bold = True
p3.add_run(
    'Sistem otomatis membuang stopwords bahasa Indonesia (seperti: "dan", "atau", "yang", "untuk", "adalah") dari jawaban siswa maupun kunci jawaban, lalu mengukur jumlah kata yang saling beririsan.\n'
)
p3.add_run("Rumus: ").bold = True
p3.add_run("(Jumlah Kata Beririsan / Jumlah Total Kata Unik Gabungan) x 100%\n")
p3.add_run("Contoh: ").bold = True
p3.add_run(
    'Kunci: "Ibukota Indonesia adalah Jakarta" -> diekstrak menjadi [ibukota, indonesia, jakarta]\nJawaban: "Ibukota Jakarta" -> diekstrak menjadi [ibukota, jakarta]\nIrisan: 2 kata. Total Kata Unik: 3 kata. Skor Jaccard = (2 / 3) * 100 = 67%.'
)

# Section 4
doc.add_heading("4. Retrieval-Augmented Grading (RAG) & Konsistensi", level=2)
p4 = doc.add_paragraph()
p4.add_run("Sistem menggunakan perhitungan ")
p4.add_run("Cosine Similarity").bold = True
p4.add_run(
    " lewat Vector Search Service. Jawaban siswa diubah menjadi vektor (embedding). Sistem akan mencari jawaban-jawaban historis siswa lain di masa lalu di database.\n"
)
p4.add_run(
    "Jika AI pernah mengoreksi jawaban historis yang sangat mirip (Cosine Similarity > Threshold) dan memberikannya skor tinggi, AI secara sistematis dipandu (lewat konteks RAG) untuk memberikan skor yang konsisten, demi menjaga objektivitas dan standar penilaian guru."
)

# Section 5
doc.add_heading("5. Penentuan Rasio Keyakinan AI (Confidence Level)", level=2)
p5 = doc.add_paragraph(
    "Setiap nilai yang keluar dari AI selalu disertai tingkat keyakinan yang mengklasifikasikan apakah nilai tersebut butuh ditinjau secara manual oleh guru:\n"
)
p5.add_run("- HIGH (Confidence ≥ 90%): ").bold = True
p5.add_run("Sangat kuat, nilai bisa masuk buku nilai tanpa pemeriksaan guru (Auto Accept).\n")
p5.add_run("- MEDIUM (75% ≤ Confidence < 90%): ").bold = True
p5.add_run(
    "Masuk akal, namun direkomendasikan untuk diperiksa ulang jika guru ragu (Needs Review).\n"
)
p5.add_run("- LOW (Confidence < 75%): ").bold = True
p5.add_run(
    "Terdapat banyak kontradiksi silang. Sistem mewajibkan Manual Review Required (Guru harus menyetujuinya secara spesifik).\n\n"
)
p5.add_run("Semua proses ini selalu diakhiri dengan pembuatan ")
p5.add_run("Academic Rationale").bold = True
p5.add_run(
    " — yaitu penjelasan pedagogis berbentuk teks yang menerangkan mengapa AI melakukan pengurangan atau penambahan skor tersebut, sehingga nilainya bisa dipertanggungjawabkan kepada siswa."
)

file_path = "C:/Users/irul2/Desktop/Rumus_Perhitungan_AI_Equigrade.docx"
doc.save(file_path)
print(f"Saved to {file_path}")
