# EQUIGRADE x LOCKXAM — CATATAN PROGRES & HANDOVER PROYEK

> **Tujuan Dokumen Ini**: Sebagai jejak rekam terpusat perkembangan sistem EquiGrade x Lockxam agar kapan pun sesi berakhir / berganti akun, tim pengembang atau AI Assistant dapat langsung memahami titik terakhir pengerjaan dan melanjutkan tahap berikutnya secara presisi.

---

## 📌 Status Terakhir: 🟡 IMPORT INTEGRITY REMEDIATION IN PROGRESS (Batch 1 & 2 Frozen, Batch 3 Remediated & Verified)

```text
[FASE 1 & 2: Database Models & Domain Services]        ──> ✅ SELESAI & LULUS UJI
[FASE 3: Academic Administration API & Contract Layer] ──> ✅ SELESAI & LULUS UJI (10/10 PASS) 🔒
[FASE 4: School Admin UI & Import Integrity Audit]     ──> 🟡 REMEDIATION IN PROGRESS (Student & Class structure FROZEN, Teacher & Subject implemented & tested)
                                                               │
                                                               ▼
[FASE 5: Teacher Exam Selection, Proctor BAU & CBT UI] ──> ⏳ PENDING UNTIL ALL IMPORTS FROZEN
```

---

## 🧭 Roadmap & Matrix Status Keseluruhan

| Modul / Domain | Backend (FastAPI) | Frontend (React TS) | Status | Keterangan |
| :--- | :---: | :---: | :---: | :--- |
| **Autentikasi & RBAC** | ✅ 100% | ✅ 100% | **Selesai** | JWT, RBAC Guard, Force Change Password, Toggle Password 👁️, Ubah Sandi Topbar untuk semua role |
| **Notifikasi & MessageBox Animasi** | ✅ 100% | ✅ 100% | **Selesai** | Spring-bounce animations, Glowing beacon, Countdown pause on hover, Tombol salin pesan error & MessageBox modal |
| **Super Admin Portal** | ✅ 100% | ✅ 100% | **Selesai** | Kelola Sekolah, Lisensi, Activation Key Generator, Domain Rules, Reset Admin Password |
| **School Admin Core** | ✅ 100% | ✅ 100% | **Selesai** | Profil Sekolah, Tahun Ajaran & Semester, Lisensi Aktif/Permanen |
| **Direktori Guru & Siswa** | ✅ 100% | ✅ 100% | **Selesai** | Bento Box, Detail Modal, Sinkron Master Mapel/Kelas, Impor Guru & Siswa disesuaikan kontrak batch atomik (Batch 1 & 3) |
| **Academic Admin API (Fase 3)** | ✅ 100% | ✅ 100% | **Selesai & Hijau** | Subject CRUD, Class CRUD, Student Enrollment, Class-Subject-Teacher, Teacher Candidate API, Exam Schedule API |
| **Guru: Bank Soal & Paket Soal**| ✅ 100% | ✅ 100% | **Selesai** | PG (2–6 opsi A–F), Essay (Rubrik AI/Manual), Pembuatan Paket, Import Bank Soal, Reorder |
| **Admin UI: Master Mapel (4.1)** | ✅ 100% | ✅ 100% | **Selesai** | `/admin/subjects`: List/Create/Edit/Delete, Impor Batch Atomik (Batch 3), Penugasan Guru Pengampu Mapel & Realtime Toggle |
| **Admin UI: Rombel Kelas (4.2)** | ✅ 100% | ✅ 100% | **Selesai** | `/admin/classes`: Year Selector, Bento Stats, Impor Rombel Kelas Batch Atomik (Batch 2), 3 Tabs |
| **Admin UI: Jadwal Ujian (4.3)** | ✅ 100% | ✅ 100% | **Selesai** | `/admin/exam-schedules`: Filter Year/Sem/Class, Auto Guru Pengampu, Assign Proctor, State Protection (DRAFT/LOCKED/ACTIVE/COMPLETED) |
| **Guru: Penugasan & Snapshot (5.1)**| ✅ API Siap | ⏳ **Target Fase 5** | **Backend Siap** | Guru memilih paket soal ➔ Membekukan `ExamSnapshot` secara *immutable* |
| **Pengawas: Proctoring & BAU (5.2)**| ✅ API Siap | ⏳ Target Fase 5 | **Backend Siap** | Dashboard Pengawas: Live Attendance, Lock/Unlock Siswa, Reset Device, Cetak Berita Acara Ujian (BAU) |
| **Siswa: CBT Exam Engine (5.3)**    | ✅ API Siap | ⏳ Target Fase 5 | **Backend Siap** | Interface CBT Siswa, Lockdown Anti-Curang, Autosave Real-time, Countdown Timer, Submit Final |
| **Penilaian AI (AI Grading 5.4)**   | ✅ API Siap | ⏳ Target Fase 5 | **Backend Siap** | Evaluasi otomatis jawaban essay via Gemini & finalisasi nilai guru |

---

## 🔒 Invarian & Arsitektur Utama yang Dijaga (Lulus Uji)

1. **`ACADEMIC-CLASS-001` (Unik per Tahun Ajaran)**:
   - Nama kelas terikat unik per Tahun Ajaran: `UNIQUE(school_id, academic_year_id, name)`.
2. **`STUDENT-ACADEMIC-001` (Single Master + History Enrollment)**:
   - Identitas siswa (`AuthAccount`) tetap satu master. Pindah kelas mengarsipkan riwayat lama sebagai `TRANSFERRED` dan membuat enrollment `ACTIVE` baru.
3. **`CLASS-TEACHER-001` (Authoritative Teacher Candidates)**:
   - Frontend tidak memfilter guru sendiri, melainkan memanggil endpoint authoritative:
     `GET /api/v1/admin/classes/{class_id}/subjects/{subject_id}/teacher-candidates`.
   - Hanya guru yang terverifikasi kompeten mengajar mapel tersebut yang muncul di daftar pilihan.
4. **`EXAM-SCHEDULE-001` (Otomatisasi Guru Pengampu)**:
   - Saat Admin membuat jadwal ujian, Guru Pengampu ditarik secara otomatis dari relasi kelas `ClassSubjectTeacher`. Admin hanya menugaskan Pengawas (*Proctor*).
5. **State Awareness Jadwal Ujian**:
   - Status `DRAFT`: Dapat diedit, proctor diubah, dan dihapus.
   - Status `SCHEDULED` / `LOCKED` / `ACTIVE` / `COMPLETED`: Dilindungi (*read-only* & terkunci, tidak dapat dihapus).
6. **`EXAM-HISTORY-001/002/003` (Snapshot Kekal & Tak Berubah)**:
   - Ujian yang berjalan menggunakan snapshot beku `ExamSnapshot` sehingga perubahan data master di masa depan tidak mempengaruhi nilai & histori masa lalu.

---

## 🛠️ Ringkasan File yang Telah Dibangun pada Fase 4

### 1. API Clients TypeScript
* [`frontend/src/api/subject.ts`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/api/subject.ts): Client Subject CRUD, list kompetensi guru, assign/unassign kompetensi.
* [`frontend/src/api/class.ts`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/api/class.ts): Client Class CRUD, Student Enrollments, Class Subjects, Class Teacher Candidates (`getTeacherCandidates`).
* [`frontend/src/api/examSchedule.ts`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/api/examSchedule.ts): Client Exam Schedule Management, Proctor Assignment.

### 2. Views & Halaman Frontend
* [`frontend/src/views/admin/SubjectsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SubjectsView.tsx):
  - Bento Box metrik mapel (Total, Aktif, Nonaktif, Total Guru).
  - Search & filter status.
  - Modal Tambah/Edit Mapel.
  - Modal Kelola Guru Kompeten dengan toggle real-time dan indikator sertifikasi.
* [`frontend/src/views/admin/ClassesView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/ClassesView.tsx):
  - Pemilih Tahun Ajaran Dinamis dengan status badge periode aktif.
  - Bento Box metrik rombel (Total Kelas, Total Siswa, Mapel, Rata-rata per Kelas).
  - Modal Detail & Struktur Kelas dengan 3 Tab:
    1. **Tab 1: Siswa Terdaftar** (Tarik Siswa dari Master dengan filter *Tanpa Kelas*, lepas siswa).
    2. **Tab 2: Mata Pelajaran** (Tambah kurikulum mapel ke rombel kelas).
    3. **Tab 3: Guru Pengampu** (Pemilihan guru pengampu dari *Authoritative Teacher Candidates*).
* [`frontend/src/views/admin/ExamSchedulesView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/ExamSchedulesView.tsx):
  - Filter bar Tahun Ajaran, Semester, dan Kelas.
  - Bento Box metrik jadwal (Total, Draft, Ujian Aktif, Selesai/Arsip).
  - Modal Buat Jadwal Ujian (Guru Pengampu otomatis ditarik dari mapel kelas).
  - Modal Penugasan Pengawas (*Proctor*).
  - Proteksi status DRAFT / LOCKED / ACTIVE / COMPLETED.

### 3. Layout & Navigasi
* [`frontend/src/components/layout/Sidebar.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/components/layout/Sidebar.tsx): Menu rapi terpisah: **Jadwal Ujian** (`/admin/exam-schedules`), **Mata Pelajaran** (`/admin/subjects`), **Manajemen Kelas** (`/admin/classes`).
* [`frontend/src/App.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/App.tsx): Routing aktif untuk ketiga halaman School Admin.
* [`frontend/src/views/admin/SchoolDashboardView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SchoolDashboardView.tsx): Quick action buttons langsung ke Jadwal Ujian, Mata Pelajaran, dan Kelas Rombel.

---

## 🧪 Quality Gate Verification

```bash
# Frontend Build Verification:
cd frontend && npm run build
✓ 1845 modules transformed.
✓ built in 1.76s (dist/assets/index.js & index.css) — 0 ERRORS

# Backend Regression & Invariant Tests:
python -m pytest tests/test_academic_domain_and_snapshot.py tests/test_academic_administration_api.py -v
====================== 10 passed in 3.63s — 100% GREEN =======================
```

---

## 🔑 Kredensial Akun Pengujian & Development

| Role | Username | Password | Keterangan |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `superadmin` | `Password123!` | Akses portal superadmin |
| **School Admin** | `admin_school` | `Password123!` | Admin SMA Negeri 1 Nusantara (`SCH_2026_01`) |
| **Guru** | `teacher1` s/d `teacher5` | `Password123!` | Guru pengampu & pembuat soal |
| **Siswa** | `student1` s/d `student10` | `Password123!` | Siswa peserta ujian CBT |

* **Backend Dev Server**: `http://127.0.0.1:8000` (FastAPI)
* **Frontend Dev Server**: `http://127.0.0.1:5173` (React Vite TS)

---

## 🎯 Langkah Selanjutnya: FASE 5 (TEACHER EXAM SELECTION, PROCTOR & CBT UI)

Tahap berikutnya:
1. **Fase 5.1 — Teacher Exam Assignment**: Menghubungkan paket soal yang dibuat guru dengan jadwal ujian yang sudah dibuat admin untuk membekukan `ExamSnapshot`.
2. **Fase 5.2 — Proctoring Workspace & BAU**: Interface pengawas untuk memantau status siswa, aksi Lock/Unlock/Reset Device, dan finalisasi Berita Acara Ujian (BAU).
3. **Fase 5.3 — Student CBT Interface**: Halaman pengerjaan ujian siswa dengan countdown timer, autosave, dan anti-cheat fullscreen lock.
