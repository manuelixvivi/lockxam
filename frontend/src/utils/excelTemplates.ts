import { downloadXlsxTemplate } from "./xlsx";

/**
 * Standardized Template Generators for All System Menus
 */

// 1. Template Import Siswa
export function downloadStudentTemplate(): void {
  downloadXlsxTemplate(
    ["Nama Lengkap", "NIS", "NISN", "Jenis Kelamin (L/P)", "Kelas", "Tahun Terdaftar"],
    [
      {
        "Nama Lengkap": "Ahmad Fauzi",
        "NIS": "1001",
        "NISN": "0051234567",
        "Jenis Kelamin (L/P)": "L",
        "Kelas": "X IPA 1",
        "Tahun Terdaftar": "2026",
      },
      {
        "Nama Lengkap": "Siti Nurhaliza",
        "NIS": "1002",
        "NISN": "0051234568",
        "Jenis Kelamin (L/P)": "P",
        "Kelas": "X IPA 1",
        "Tahun Terdaftar": "2026",
      },
      {
        "Nama Lengkap": "Budi Santoso",
        "NIS": "1003",
        "NISN": "0051234569",
        "Jenis Kelamin (L/P)": "L",
        "Kelas": "X IPS 2",
        "Tahun Terdaftar": "2026",
      },
    ],
    "Template_Import_Siswa_Equigrade"
  );
}

// 2. Template Import Guru
export function downloadTeacherTemplate(): void {
  downloadXlsxTemplate(
    ["Nama Lengkap", "NIP", "Kode Guru", "Jenis Kelamin (L/P)", "Tahun Terdaftar"],
    [
      {
        "Nama Lengkap": "Dr. Herman Wijaya, M.Pd",
        "NIP": "198501152010011001",
        "Kode Guru": "G-KIM01",
        "Jenis Kelamin (L/P)": "L",
        "Tahun Terdaftar": "2024",
      },
      {
        "Nama Lengkap": "Siti Rahmawati, S.Si",
        "NIP": "199003202015022002",
        "Kode Guru": "G-BIO02",
        "Jenis Kelamin (L/P)": "P",
        "Tahun Terdaftar": "2025",
      },
    ],
    "Template_Import_Guru_Equigrade"
  );
}

// 3. Template Import Kelas
export function downloadClassTemplate(): void {
  downloadXlsxTemplate(
    ["Nama Kelas", "Tingkat (10/11/12)", "Kapasitas"],
    [
      {
        "Nama Kelas": "X IPA 1",
        "Tingkat (10/11/12)": "10",
        "Kapasitas": "36",
      },
      {
        "Nama Kelas": "XI IPS 2",
        "Tingkat (10/11/12)": "11",
        "Kapasitas": "36",
      },
      {
        "Nama Kelas": "XII MIPA 3",
        "Tingkat (10/11/12)": "12",
        "Kapasitas": "34",
      },
    ],
    "Template_Import_Kelas_Equigrade"
  );
}

// 4. Template Import Mata Pelajaran
export function downloadSubjectTemplate(): void {
  downloadXlsxTemplate(
    ["Kode Mapel", "Nama Mata Pelajaran", "Deskripsi"],
    [
      {
        "Kode Mapel": "KIM-XI",
        "Nama Mata Pelajaran": "Kimia",
        "Deskripsi": "Mata pelajaran Kimia tingkat SMA/MA",
      },
      {
        "Kode Mapel": "BIO-X",
        "Nama Mata Pelajaran": "Biologi",
        "Deskripsi": "Mata pelajaran Biologi tingkat SMA/MA",
      },
      {
        "Kode Mapel": "MAT-WAJIB",
        "Nama Mata Pelajaran": "Matematika Wajib",
        "Deskripsi": "Matematika Kurikulum Merdeka",
      },
    ],
    "Template_Import_Mapel_Equigrade"
  );
}

// 5. Template Import Bank Soal (Dengan Dukungan LaTeX)
export function downloadQuestionBankTemplate(): void {
  downloadXlsxTemplate(
    [
      "Mata Pelajaran",
      "Tingkat Kelas (X/XI/XII)",
      "Tipe Soal (PG/IS/ES)",
      "Pertanyaan (Support LaTeX)",
      "Pilihan A",
      "Pilihan B",
      "Pilihan C",
      "Pilihan D",
      "Pilihan E",
      "Kunci Jawaban",
      "Bobot Nilai",
    ],
    [
      {
        "Mata Pelajaran": "Matematika",
        "Tingkat Kelas (X/XI/XII)": "X",
        "Tipe Soal (PG/IS/ES)": "PG",
        "Pertanyaan (Support LaTeX)": "Tentukan akar dari persamaan kuadrat $x^2 - 5x + 6 = 0$!",
        "Pilihan A": "$x = 2$ atau $x = 3$",
        "Pilihan B": "$x = 1$ atau $x = 6$",
        "Pilihan C": "$x = -2$ atau $x = -3$",
        "Pilihan D": "$x = 0$ atau $x = 5$",
        "Pilihan E": "$x = 3$ atau $x = 4$",
        "Kunci Jawaban": "A",
        "Bobot Nilai": "10",
      },
      {
        "Mata Pelajaran": "Matematika",
        "Tingkat Kelas (X/XI/XII)": "XI",
        "Tipe Soal (PG/IS/ES)": "PG",
        "Pertanyaan (Support LaTeX)": "Berapakah hasil dari integral tak tentu $\\int 2x dx$?",
        "Pilihan A": "$x^2 + C$",
        "Pilihan B": "$2x^2 + C$",
        "Pilihan C": "$\\frac{1}{2}x^2 + C$",
        "Pilihan D": "$x + C$",
        "Pilihan E": "$2 + C$",
        "Kunci Jawaban": "A",
        "Bobot Nilai": "10",
      },
      {
        "Mata Pelajaran": "Kimia",
        "Tingkat Kelas (X/XI/XII)": "X",
        "Tipe Soal (PG/IS/ES)": "IS",
        "Pertanyaan (Support LaTeX)": "Sebutkan nama rumus ikatan $\\text{H}_2\\text{O}$!",
        "Pilihan A": "",
        "Pilihan B": "",
        "Pilihan C": "",
        "Pilihan D": "",
        "Pilihan E": "",
        "Kunci Jawaban": "Air",
        "Bobot Nilai": "15",
      },
      {
        "Mata Pelajaran": "Biologi",
        "Tingkat Kelas (X/XI/XII)": "XII",
        "Tipe Soal (PG/IS/ES)": "ES",
        "Pertanyaan (Support LaTeX)": "Jelaskan proses fotosintesis pada tumbuhan hijau dengan menyertakan reaksi kimianya $6\\text{CO}_2 + 6\\text{H}_2\\text{O} \\rightarrow \\text{C}_6\\text{H}_{12}\\text{O}_6 + 6\\text{O}_2$!",
        "Pilihan A": "",
        "Pilihan B": "",
        "Pilihan C": "",
        "Pilihan D": "",
        "Pilihan E": "",
        "Kunci Jawaban": "Fotosintesis membutuhkan cahaya matahari, klorofil, air, dan karbon dioksida...",
        "Bobot Nilai": "20",
      },
    ],
    "Template_Import_Soal_LaTeX_Equigrade"
  );
}

// 6. Template Import Sekolah (Superadmin)
export function downloadSchoolTemplate(): void {
  downloadXlsxTemplate(
    ["NPSN", "Nama Sekolah", "Jenjang (TK/SD/SMP/SMA/SMK)", "Domain Slug", "Alamat", "Telepon", "Email"],
    [
      {
        "NPSN": "20101234",
        "Nama Sekolah": "SMA Negeri 1 Jakarta",
        "Jenjang (TK/SD/SMP/SMA/SMK)": "SMA",
        "Domain Slug": "sman1jakarta",
        "Alamat": "Jl. Budi Utomo No. 7, Jakarta Pusat",
        "Telepon": "0213865432",
        "Email": "info@sman1jakarta.sch.id",
      },
      {
        "NPSN": "20105678",
        "Nama Sekolah": "SMK Negeri 2 Bandung",
        "Jenjang (TK/SD/SMP/SMA/SMK)": "SMK",
        "Domain Slug": "smkn2bandung",
        "Alamat": "Jl. Cihampelas No. 45, Bandung",
        "Telepon": "0224201234",
        "Email": "admin@smkn2bandung.sch.id",
      },
    ],
    "Template_Import_Sekolah_Equigrade"
  );
}

// 7. Template Import Tahun Ajaran
export function downloadAcademicYearTemplate(): void {
  downloadXlsxTemplate(
    ["Nama Tahun Ajaran (e.g. 2026/2027)", "Tanggal Mulai (YYYY-MM-DD)", "Tanggal Selesai (YYYY-MM-DD)"],
    [
      {
        "Nama Tahun Ajaran (e.g. 2026/2027)": "2026/2027",
        "Tanggal Mulai (YYYY-MM-DD)": "2026-07-15",
        "Tanggal Selesai (YYYY-MM-DD)": "2027-06-25",
      },
    ],
    "Template_Import_Tahun_Ajaran_Equigrade"
  );
}

// 8. Template Import Jadwal Ujian
export function downloadExamScheduleTemplate(): void {
  downloadXlsxTemplate(
    ["Judul Ujian", "Kelas", "Mata Pelajaran", "Waktu Mulai (YYYY-MM-DD HH:MM)", "Waktu Selesai (YYYY-MM-DD HH:MM)", "Durasi (Menit)"],
    [
      {
        "Judul Ujian": "Penilaian Akhir Semester Ganjil - Kimia",
        "Kelas": "X IPA 1",
        "Mata Pelajaran": "Kimia",
        "Waktu Mulai (YYYY-MM-DD HH:MM)": "2026-12-01 08:00",
        "Waktu Selesai (YYYY-MM-DD HH:MM)": "2026-12-01 09:30",
        "Durasi (Menit)": "90",
      },
    ],
    "Template_Import_Jadwal_Ujian_Equigrade"
  );
}
