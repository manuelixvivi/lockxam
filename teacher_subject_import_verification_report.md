# Verification & Completion Audit: Teacher & Subject Bulk Import (Batch 3)

Laporan audit ini dibuat berdasarkan analisis langsung terhadap kode sumber aktual dan hasil eksekusi rangkaian pengujian unit/integrasi pada fitur impor massal **Mata Pelajaran (Subject)** dan **Staf Pengajar (Teacher)**.

---

## 1. Actual Current Implementation (Analisis Jalur Aliran Data)

Jalur aliran data untuk kedua importir telah ditelusuri dari ujung ke ujung:

### Aliran Impor Mata Pelajaran (Subject Import)
1. **Frontend Parser**: File XLSX dibaca di [`SubjectsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SubjectsView.tsx#L770-L780) menggunakan helper `readXlsxFile`. Objek data dipetakan ke dalam array payload tunggal dengan tambahan informasi `row_num`.
2. **API Request**: Payload dikirimkan dalam **satu request tunggal** melalui `subjectApi.importSubjects` ([`subject.ts`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/api/subject.ts#L85-L95)) menuju endpoint backend.
3. **Router**: Endpoint `POST /api/v1/admin/subjects/import` di [`admin_subject.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/api/admin_subject.py) menerima payload bertipe `SubjectImportRequest`, memvalidasi school_id dari token otentikasi JWT (`current_user`), dan memanggil service layer.
4. **Service**: `SubjectService.import_subjects_xlsx` di [`subject_service.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/services/academic/subject_service.py) menjalankan dua tahap pemrosesan (First-Pass Validation & Second-Pass Persistence).
5. **Repository**: Akses basis data diisolasi melalui `subject_repository` ([`subject_repository.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/repositories/academic/subject_repository.py)) untuk pengecekan kode eksis maupun pembuatan record baru.
6. **Database**: Penyimpanan data dibungkus dalam savepoint nested transaction (`db.begin_nested()`). Jika sukses, data ditulis ke tabel `subjects`.

### Aliran Impor Guru (Teacher Import)
1. **Frontend Parser**: File XLSX dibaca di [`TeachersView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/TeachersView.tsx#L846-L865) dan dipetakan ke payload tunggal yang menyertakan NIP, Nama, Jenis Kelamin, Kode Guru, Tahun Terdaftar, dan `row_num`.
2. **API Request**: Dikirim dalam **satu request** menggunakan `teacherApi.importTeachers` ([`teacher.ts`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/api/teacher.ts#L74-L85)).
3. **Router**: Diterima oleh `POST /api/v1/admin/teachers/import` di [`school_staff.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/api/school_staff.py).
4. **Service**: Diproses oleh `SchoolStaffService.import_teachers_xlsx` di [`staff_service.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/services/school/staff_service.py).
5. **Repository**: Memanfaatkan helper dari `auth_repository` untuk validasi keunikan username dan kode guru secara berstruktur.
6. **Database**: Eksekusi persistensi dibungkus di dalam nested savepoint. Data disimpan ke tabel `auth_accounts` dengan `role` otomatis diset ke `TEACHER`.

---

## 2. Subject Import Status: 🟢 CONFORMANT

Hasil verifikasi kepatuhan terhadap invariants:
1. **Batch-based & Single Request**: 🟢 **CONFORMANT**. Seluruh baris dikirim dalam satu array payload `subjects` dalam satu request HTTP POST.
2. **First-Pass Validation**: 🟢 **CONFORMANT**. Seluruh baris divalidasi penuh di memori backend sebelum memulai manipulasi data.
3. **Duplicate in File**: 🟢 **CONFORMANT**. Duplicate checking menggunakan set `seen_codes` melacak entri ganda dalam file Excel dan mengembalikan error `DUPLICATE_SUBJECT_CODE_IN_FILE`.
4. **Duplicate in Database**: 🟢 **CONFORMANT**. Kode mata pelajaran dicek di lingkup sekolah via repository dan mengembalikan error `DUPLICATE_SUBJECT_CODE_IN_DB`.
5. **School Ownership & Auth Context**: 🟢 **CONFORMANT**. `school_id` diverifikasi ketat dari JWT context, tidak dibaca dari input Excel.
6. **Atomicity & Rollback**: 🟢 **CONFORMANT**. Database transaction savepoint menjamin tidak ada partial persistence bila ditemukan baris yang tidak valid.
7. **Pure Master Data Invariant**: 🟢 **CONFORMANT**. Tidak ada dependensi ke `academic_year_id`. Impor tidak melakukan auto-create terhadap `ClassSubject` maupun sertifikasi kompetensi `TeacherSubject`.

---

## 3. Teacher Import Status: 🟢 CONFORMANT

Hasil verifikasi kepatuhan terhadap invariants:
1. **Batch-based & Single Request**: 🟢 **CONFORMANT**. Seluruh data diunggah dalam satu request array `teachers`.
2. **First-Pass Validation**: 🟢 **CONFORMANT**. Validasi struktural (nama, NIP, gender) dan semantik selesai diproses sebelum menulis data apa pun.
3. **Duplicate Username (NIP) & Code**: 🟢 **CONFORMANT**.
   - Keunikan NIP dideteksi ganda di file (`DUPLICATE_NIP_IN_FILE`) dan di database (`DUPLICATE_USERNAME_IN_DB`).
   - Keunikan kode guru diperiksa di file (`DUPLICATE_TEACHER_CODE_IN_FILE`) dan di DB (`DUPLICATE_TEACHER_CODE_IN_DB`).
4. **Tenant Isolation**: 🟢 **CONFORMANT**. NIP diisolasi menggunakan domain sekolah (`username = {nip}@guru.{domain}`) agar tidak terjadi tabrakan antar-sekolah (tenant).
5. **Atomicity & Rollback**: 🟢 **CONFORMANT**. Jika salah satu baris guru invalid, seluruh batch di-rollback dan tidak ada baris yang masuk ke database.
6. **Teacher Competency Boundary (CRITICAL)**: 🟢 **CONFORMANT**. Impor guru **sama sekali tidak menyentuh** tabel kompetensi `TeacherSubject` maupun array `subjects_taught` di model `AuthAccount` (yang merupakan proyeksi read-only). Kompetensi guru tetap menjadi alur kerja manual admin yang eksplisit.

---

## 4. Frontend Status: 🟢 CONFORMANT

- **SubjectsView.tsx**: 🟢 **CONFORMANT**. Tidak ada perulangan panggilan API mutation per baris di frontend. Fungsi `onImportXlsx` memetakan baris dan memanggil endpoint impor batch secara langsung.
- **TeachersView.tsx**: 🟢 **CONFORMANT**. Daur impor row loop per-baris telah dihapus sepenuhnya dan digantikan oleh panggilan impor batch tunggal.
- **ImportExportBar.tsx**: 🟢 **CONFORMANT**. Komponen ini tidak lagi bertindak sebagai koordinator mutasi database per-baris untuk modul Guru dan Mata Pelajaran. Perannya dipertahankan murni sebagai komponen visual atau programmatic export.

---

## 5. Repository Status: 🟢 CONFORMANT

Pemeriksaan service layer ([`subject_service.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/services/academic/subject_service.py) & [`staff_service.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/services/school/staff_service.py)) mengonfirmasi:
- **No direct database queries**: 🟢 **CONFORMANT**. Tidak ada pemanggilan langsung `db.query(...)`, `select(...)` atau manipulasi ORM mentah di dalam service impor. Semua operasi pembacaan dan penulisan mendelegasikan tugas ke repository boundary (`subject_repository`, `auth_repository`).

---

## 6. Transaction Status: 🟢 CONFORMANT

- **Commit & Savepoint Ownership**: 🟢 **CONFORMANT**. Router memegang kendali commit transaksi utama (`db.commit()`), sementara service layer mengelola flush dan nested transactions (`db.begin_nested()`).
- **Safely Masked Internal Error**: 🟢 **CONFORMANT**. Semua exception level database ditangkap dengan aman di service layer, di-rollback, dan dikonversi menjadi pesan error standar yang aman (HTTP 500 dengan deskripsi kesalahan internal terproteksi).

---

## 7. Test Coverage: 🟢 CONFORMANT (20/20 PASSED)

Rangkaian pengujian unit integrasi menyeluruh di [`test_teacher_subject_import.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/tests/test_teacher_subject_import.py) melaporkan hasil sukses **100% (20 passed, 0 failed)**:

```text
tests\test_teacher_subject_import.py ....................                [100%]
======================= 20 passed, 25 warnings in 9.44s =======================
```

Skenario pengujian yang terverifikasi meliputi:
- **Subject Import Suite**:
  - `test_import_subjects_valid_batch` (Impor batch valid + verifikasi tidak ada ClassSubject/TeacherSubject)
  - `test_import_subjects_missing_code` (Gagal jika kode kosong)
  - `test_import_subjects_missing_name` (Gagal jika nama kosong)
  - `test_import_subjects_duplicate_code_in_file` (Duplikasi kode di file XLSX)
  - `test_import_subjects_duplicate_database` (Duplikasi kode di database)
  - `test_import_subjects_cross_tenant_protection` (Validasi isolasi sekolah)
  - `test_import_subjects_mixed_valid_invalid` (Rollback transaksi data campuran)
  - `test_import_subjects_db_failure_rollback` (Rollback kesalahan persistensi)
  - `test_import_subjects_atomic_100_rows` (Atomic check 100 rows: 99 valid + 1 invalid = 0 persisted)

- **Teacher Import Suite**:
  - `test_import_teachers_valid_batch` (Impor batch guru valid)
  - `test_import_teachers_missing_required_identity` (Validasi NIP/Nama/Gender wajib)
  - `test_import_teachers_duplicate_username_in_file` (NIP ganda di file)
  - `test_import_teachers_duplicate_teacher_code_in_file` (Kode guru ganda di file)
  - `test_import_teachers_duplicate_database_username` (NIP/username ganda di database)
  - `test_import_teachers_duplicate_nip_or_code` (Kode guru ganda di database)
  - `test_import_teachers_cross_tenant_protection` (Isolasi guru antar tenant)
  - `test_import_teachers_mixed_valid_invalid` (Rollback campuran guru invalid)
  - `test_import_teachers_db_failure_rollback` (Rollback crash DB)
  - `test_import_teachers_no_teacher_subject_created` (Menjamin tabel kompetensi tidak terbuat otomatis)
  - `test_import_teachers_atomic_100_rows` (Atomic check 100 rows: 99 valid + 1 invalid = 0 persisted)

---

## 8. Ringkasan Status

| Area Audit | Status Keputusan | Temuan & Catatan |
| :--- | :--- | :--- |
| **Subject Bulk Import** | 🟢 **CONFORMANT** | Telah atomik, isolasi tenant aman, master data murni. |
| **Teacher Bulk Import** | 🟢 **CONFORMANT** | Keunikan NIP/username/code terjamin, tidak ada auto-create kompetensi. |
| **Frontend Implementation** | 🟢 **CONFORMANT** | Pengiriman array tunggal batch, loop mutasi per-row dibersihkan. |
| **Repository Boundaries** | 🟢 **CONFORMANT** | Terjaga penuh tanpa ada `db.query()` mentah di service. |
| **Transactional Rollback** | 🟢 **CONFORMANT** | nested savepoint diimplementasikan dengan penanganan error. |
| **Integration Test Suite** | 🟢 **CONFORMANT** | 20 pengujian lulus 100%. |

**Berkas yang Diremediasi & Diverifikasi:**
1. [`app/services/academic/subject_service.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/services/academic/subject_service.py)
2. [`app/services/school/staff_service.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/services/school/staff_service.py)
3. [`app/api/admin_subject.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/api/admin_subject.py)
4. [`app/api/school_staff.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/api/school_staff.py)
5. [`frontend/src/views/admin/SubjectsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SubjectsView.tsx)
6. [`frontend/src/views/admin/TeachersView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/TeachersView.tsx)
7. [`tests/test_teacher_subject_import.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/tests/test_teacher_subject_import.py)
