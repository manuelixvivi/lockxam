# Laporan Remediasi Impor Massal Mata Pelajaran (Batch 3A)

Laporan ini mendokumentasikan hasil remedi dan verifikasi untuk fitur impor massal **Mata Pelajaran (Subject)** sesuai dengan standar **Import Contract v1.0**.

---

## 1. File yang Diubah (Files Changed)
1. Backend Service: [`app/services/academic/subject_service.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/services/academic/subject_service.py)
2. Backend API Router: [`app/api/admin_subject.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/api/admin_subject.py)
3. Backend Pydantic Schemas: [`app/schemas/academic/admin_academic.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/schemas/academic/admin_academic.py)
4. Frontend API Client: [`frontend/src/api/subject.ts`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/api/subject.ts)
5. Frontend View: [`frontend/src/views/admin/SubjectsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SubjectsView.tsx)
6. Integration Test Suite: [`tests/test_teacher_subject_import.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/tests/test_teacher_subject_import.py)

---

## 2. Endpoint Batch Baru (New Batch Endpoint)
- **Path**: `POST /api/v1/admin/subjects/import`
- **Request Contract (`SubjectImportRequest`)**:
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
- **Response Contract (`ImportResponse[SubjectResponse]`)**:
  - Berhasil: mengembalikan status `"success"`, `imported_count`, dan data mata pelajaran.
  - Gagal Validasi: mengembalikan status `"error"`, `imported_count: 0`, dan daftar kesalahan baris (`errors`).

---

## 3. Aturan Validasi (Validation Rules)
Setiap baris data divalidasi penuh di memori sebelum manipulasi database dilakukan:
1. **Wajib Isi**: Kolom `code` (Kode Mapel) dan `name` (Nama Mapel) wajib diisi.
2. **Normalisasi**: Kode dibersihkan dari spasi (trim) dan dikonversi menjadi huruf kapital (`uppercase`). Deskripsi di-trim dari spasi.
3. **Duplikasi di File Excel**: Kode mapel tidak boleh ganda di dalam file Excel yang sama.
4. **Duplikasi di Database**: Kode mapel tidak boleh menabrak kode mapel lain yang sudah ada pada database sekolah aktif (`school_id`).
5. **Tenant Isolation**: Nilai `school_id` diambil langsung dari token otentikasi JWT admin yang masuk (`current_user`), sehingga mencegah tabrakan data antar-tenant.

---

## 4. Transaksional & Atomisitas (Transaction Behavior)
Prinsip transaksional yang diterapkan adalah **Semua atau Tidak Sama Sekali (All-or-Nothing)**:
- **First-Pass Validation**: Validasi memori dijalankan untuk seluruh baris data. Jika terdapat minimal satu baris yang salah (misalnya nama kosong atau kode duplikat), seluruh batch ditolak dengan status **422 Unprocessable Entity**. Tidak ada data yang ditulis ke database.
- **Savepoint & Rollback**: Proses persistensi dibungkus di dalam nested transaction (`db.begin_nested()`). Jika terjadi kesalahan basis data (misalnya error integritas unik), savepoint dan transaksi utama di-rollback (`savepoint.rollback()`, `db.rollback()`), sehingga menjamin database kembali ke status awal bersih tanpa ada baris parsial.
- **Router Final Commit**: Commit akhir (`db.commit()`) dilakukan di tingkat router API setelah pencatatan aktivitas sukses tanpa ada eksepsi.

---

## 5. Kepemilikan Data (Data Ownership Invariant)
Mata pelajaran diperlakukan sebagai **master data murni**. Proses impor mata pelajaran:
- **TIDAK** membuat data Kelas (`Class`) secara otomatis.
- **TIDAK** membuat data Tahun Ajaran (`AcademicYear`) secara otomatis.
- **TIDAK** mengaitkan pelajaran ke rombel kelas (`ClassSubject` / `ClassSubjectTeacher`).
- **TIDAK** membuat relasi pengampu guru (`TeacherSubject`).

---

## 6. Migrasi Frontend (Frontend Behavior)
- **Tunggal Request**: Pengegalan loop per-baris pada `SubjectsView.tsx` telah digantikan oleh satu panggilan batch ke endpoint `/api/v1/admin/subjects/import` lewat helper `subjectApi.importSubjects`.
- **Hasil Tampilan UX**:
  - Gagal: Jika backend mengembalikan 422, UI menampilkan notifikasi: `"Import dibatalkan. Terdapat [N] kesalahan."` dan mendaftar error baris yang spesifik.
  - Sukses: Menampilkan `"100 data berhasil diimpor."` jika semua data sukses tersimpan.

---

## 7. Hasil Pengujian Integrasi (Test Results)

Rangkaian pengujian integrasi ditulis pada [`test_teacher_subject_import.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/tests/test_teacher_subject_import.py) dan lulus **100% (20 passed)**:

### Skenario Uji Mapel Terverifikasi:
1. `test_import_subjects_valid_batch` ── Impor batch valid sukses dan memastikan tidak ada `ClassSubject` / `TeacherSubject` terbuat otomatis.
2. `test_import_subjects_missing_code` ── Gagal impor jika kode mapel kosong.
3. `test_import_subjects_missing_name` ── Gagal impor jika nama mapel kosong.
4. `test_import_subjects_duplicate_code_in_file` ── Menolak berkas Excel dengan kode mapel duplikat.
5. `test_import_subjects_duplicate_database` ── Menolak jika kode menabrak database sekolah.
6. `test_import_subjects_cross_tenant_protection` ── Memverifikasi isolasi tenant sekolah yang ketat.
7. `test_import_subjects_mixed_valid_invalid` ── Menjamin penolakan total jika ada 1 baris yang salah (atomik).
8. `test_import_subjects_db_failure_rollback` ── Rollback transaksi jika terjadi crash database.
9. `test_import_subjects_atomic_100_rows` ── **CRITICAL ATOMIC TEST**: 99 valid + 1 invalid = 0 data mapel tersimpan di database.

---

## 8. Hasil Uji Regresi & Build (Regression & Build Results)
- **FastAPI Backend Tests**: **124 passed, 0 failures**
- **Vite TS Frontend Build**: **SUCCESS (0 errors)** (`tsc -b && vite build`)
