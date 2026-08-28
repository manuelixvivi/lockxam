# Laporan Remediasi Fitur Impor Massal Guru & Mata Pelajaran (Batch 3)

Laporan ini mendokumentasikan hasil audit, perubahan arsitektur, dan pengujian integrasi untuk fitur impor massal Guru (Teacher) dan Mata Pelajaran (Subject) guna memenuhi standar **Import Contract v1.0**.

---

## 1. Sebelum Perbaikan (Current Before State)
Sebelumnya, sistem impor frontend pada berkas [`SubjectsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SubjectsView.tsx) dan [`TeachersView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/TeachersView.tsx) melakukan pembacaan Excel baris demi baris dan memicu request API `createSubject` / `createTeacher` untuk setiap baris di dalam perulangan `for`.
- **Masalah utama**: Partial import (sebagian data berhasil tersimpan, sebagian gagal karena kesalahan di tengah file), hilangnya integritas transaksional, overhead request API ganda, serta tidak adanya validasi batch yang menyeluruh di backend.

---

## 2. Arsitektur Batch Mata Pelajaran (Subject Batch Implementation)
- **Endpoint**: `POST /api/v1/admin/subjects/import` ([`admin_subject.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/api/admin_subject.py))
- **Payload**:
  ```json
  {
    "subjects": [
      {
        "code": "MAT-10",
        "name": "Matematika Kelas 10",
        "description": "Deskripsi opsional",
        "row_num": 2
      }
    ]
  }
  ```
- **Karakteristik**: Mata pelajaran diperlakukan sebagai **master data murni** dan tidak memuat dependensi `academic_year_id` atau relasi rombel.

---

## 3. Arsitektur Batch Guru (Teacher Batch Implementation)
- **Endpoint**: `POST /api/v1/admin/teachers/import` ([`school_staff.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/api/school_staff.py))
- **Payload**:
  ```json
  {
    "teachers": [
      {
        "name": "Dr. Budiman",
        "nip": "198008122005011003",
        "teacher_code": "BUDIMAN",
        "gender": "L",
        "registered_year": 2024,
        "row_num": 2
      }
    ]
  }
  ```

---

## 4. Aturan Validasi (Validation Rules)

### Validasi Mata Pelajaran (Subject Validation)
1. **Structural**: Memastikan `code` (Kode Mapel) dan `name` (Nama Mapel) terisi.
2. **Normalisasi**: Kode mapel di-trim dari spasi dan dikonversi otomatis menjadi huruf besar (`uppercase`).
3. **Duplicate-in-file**: Pengecekan keunikan kode mapel di dalam file XLSX.
4. **Duplicate-database**: Pencarian kode mapel yang sama pada database untuk sekolah aktif (`school_id`).
5. **Tenant Isolation**: Memastikan pembuatan record `Subject` terikat dengan `school_id` admin yang terautentikasi (berasal dari JWT token).

### Validasi Guru (Teacher Validation)
1. **Structural**: Memvalidasi kolom wajib `name`, `gender` (L atau P), dan `nip`.
2. **Normalisasi**: NIP dibersihkan dari spasi/karakter non-digit dan dibatasi panjangnya antara 4 hingga 20 karakter. Username dibuat otomatis dengan pola `{nip}@guru.{domain_sekolah}`.
3. **Duplicate-in-file**: Memeriksa ganda untuk `nip` dan `teacher_code` dalam file Excel.
4. **Duplicate-database**: Memeriksa apakah `username` (NIP) atau `teacher_code` sudah terpakai oleh guru lain di database.
5. **Tenant Isolation**: `school_id` diverifikasi secara authoritative dari context pengguna yang masuk.

---

## 5. Atomicity & Rollback (Atomik 100%)
Pola transaksi batch mengikuti prinsip **Semua atau Tidak Sama Sekali (All-or-Nothing)**:
- **First-Pass Validation**: Semua baris di-parsing dan diperiksa. Jika ada minimal 1 kesalahan validasi di baris manapun, backend langsung menolak seluruh data dengan mengembalikan status code **422 Unprocessable Entity** beserta rincian baris dan kolom yang bermasalah. Tidak ada data yang ditulis ke database.
- **Nested Savepoints**: Eksekusi penyimpanan dibungkus menggunakan nested transaction (`db.begin_nested()`). Jika terjadi kesalahan integritas tak terduga (misalnya *race condition* unik DB), savepoint di-rollback (`savepoint.rollback()`) dan transaksi dibatalkan bersih tanpa menyisakan baris parsial di database.

---

## 6. Pola Kepemilikan Transaksi (Transaction Ownership)
Mengikuti arsitektur reference implementation (Batch 2):
- **Service Layer**: Mengelola validasi, inisiasi nested savepoint (`db.begin_nested()`), flush ke database, dan penanganan exception DB.
- **Activity Log**: Pencatatan riwayat aktivitas (`ActivityService.log_activity`) diproses di level router.
- **Router Final Commit**: Commit akhir (`db.commit()`) dipegang sepenuhnya oleh router setelah seluruh persistensi dan penulisan log aktivitas berhasil dilakukan tanpa error.

---

## 7. Batasan Repositori (Repository Boundary)
Semua interaksi basis data pada service layer patuh pada arsitektur repositori:
- Tidak ada panggilan query mentah `db.query()` atau direct ORM lookups di service.
- Seluruh pengambilan data memanfaatkan metode yang terdefinisi pada repositori kelas (`subject_repository`, `auth_repository`, dll.).

---

## 8. Migrasi Frontend (Frontend Migration)
- Loop pemanggilan API per-baris pada [`SubjectsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SubjectsView.tsx) dan [`TeachersView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/TeachersView.tsx) telah **dihapus sepenuhnya**.
- Frontend kini mem-parsing berkas XLSX, melakukan pengecekan format awal, dan mengirimkan seluruh baris data dalam **satu request batch**.
- Jika backend mengembalikan status error 422, UI menampilkan pesan penolakan batch atomik: **"Import dibatalkan. Terdapat [N] kesalahan."** dan menampilkan daftar detail baris yang salah.

---

## 9. Proteksi Kepemilikan Relasi (TeacherSubject & Class Relationships Protection)
- **Subject Import**: Murni membuat entitas `Subject` saja. Tidak membuat relasi otomatis ke `ClassSubject`, `TeacherSubject`, atau `ClassSubjectTeacher`.
- **Teacher Import**: Murni mendaftarkan profil dan kredensial login guru (`AuthAccount`). **Tidak mendaftarkan guru secara otomatis ke kompetensi mata pelajaran (`TeacherSubject`)**. Kompetensi mengajar tetap terpisah secara tegas sebagai alur kerja eksplisit administrator.

---

## 10. Hasil Pengujian Integrasi (Batch 3)

Pengujian integrasi ditulis dalam [`test_teacher_subject_import.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/tests/test_teacher_subject_import.py) dan mencakup **20 test cases** yang lulus **100%**:

```text
tests\test_teacher_subject_import.py ....................                [100%]
======================= 20 passed, 25 warnings in 9.44s =======================
```

Skenario pengujian yang terverifikasi:
### A. Pengujian Impor Mata Pelajaran (Subject - 10 Test Cases)
1. `test_import_subjects_valid_batch` ── Sukses mengimpor file batch.
2. `test_import_subjects_missing_code` ── Menolak jika ada baris tanpa kode mapel.
3. `test_import_subjects_missing_name` ── Menolak jika nama mapel kosong.
4. `test_import_subjects_duplicate_code_in_file` ── Menolak jika ada kode ganda di file.
5. `test_import_subjects_duplicate_database` ── Menolak jika kode mapel menabrak DB sekolah aktif.
6. `test_import_subjects_cross_tenant_protection` ── Isolasi tenant aman (sekolah lain boleh memiliki kode mapel yang sama).
7. `test_import_subjects_mixed_valid_invalid` ── Transaksi atomik: 1 baris salah menggagalkan seluruh batch.
8. `test_import_subjects_db_failure_rollback` ── Rollback transaksi ketika terjadi kegagalan database.
9. `test_import_subjects_atomic_100_rows` ── **CRITICAL ATOMIC TEST**: 99 valid + 1 invalid = 0 baris Subject tersimpan di DB.
10. Proteksi relasi ── Memastikan tidak ada data `ClassSubject` atau `TeacherSubject` yang terbuat secara implisit.

### B. Pengujian Impor Guru (Teacher - 10 Test Cases)
11. `test_import_teachers_valid_batch` ── Sukses mengimpor batch guru.
12. `test_import_teachers_missing_required_identity` ── Menolak jika nama, NIP, atau gender kosong.
13. `test_import_teachers_duplicate_username_in_file` ── Menolak jika NIP ganda di file.
14. `test_import_teachers_duplicate_teacher_code_in_file` ── Menolak jika kode guru ganda di file.
15. `test_import_teachers_duplicate_database_username` ── Menolak jika NIP/username sudah terpakai di DB sekolah.
16. `test_import_teachers_duplicate_nip_or_code` ── Menolak jika kode guru menabrak DB sekolah.
17. `test_import_teachers_cross_tenant_protection` ── Memastikan NIP/username terisolasi per domain sekolah.
18. `test_import_teachers_mixed_valid_invalid` ── Transaksi atomik: 1 guru salah menggagalkan seluruh batch guru.
19. `test_import_teachers_db_failure_rollback` ── Rollback total saat terjadi kegagalan database.
20. `test_import_teachers_atomic_100_rows` ── **CRITICAL ATOMIC TEST**: 99 valid + 1 invalid = 0 baris Guru tersimpan di DB.

---

## 11. Hasil Regresi (Full Regression Results)
Eksekusi rangkaian pengujian unit/integrasi di tingkat backend dan frontend build:
- **Backend Test Suite**: **121 passed** ([`pytest`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/tests))
  ```text
  ================= 121 passed, 99 warnings in 74.71s (0:01:14) =================
  ```
- **Frontend Type & Build**: **Build Pass (0 errors)** (`tsc -b && vite build` di [`frontend/`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend))

---

## 12. Batasan Tersisa (Remaining Limitations)
- Format tanggal/tahun terdaftar masih menggunakan pembulatan integer sederhana (misalnya `2024.0` dibulatkan ke `2024`).
- Validasi data excel masih bergantung pada format parser frontend yang menyaring sheet utama. Sheet sekunder diabaikan.
