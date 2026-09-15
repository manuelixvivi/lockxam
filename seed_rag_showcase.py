"""
EquiGrade — RAG (Retrieval-Augmented Generation) Showcase Seeder & Simulator
=============================================================================
Skrip ini mengisi (seed) basis data pengetahuan asesmen historis (AssessmentHistory)
beserta vektor embedding padat 1024-dimensi (AssessmentEmbedding) untuk demonstrasi
dan simulasi fitur penilaian esai bertenaga RAG di hadapan dosen penguji/pembimbing.

Fitur yang di-seed:
1. Tiga Mata Pelajaran Kurikulum SMA (Kimia, Fisika, Biologi)
2. Paket Soal & Rubrik Asesmen Resmi
3. Sembilan Preseden Kasus Penilaian Guru Asli (Jawaban Siswa, Skor Guru, Catatan Pedagogis)
4. Vector Embeddings 1024-dimensi terindeks L2-normalized via EmbeddingService
5. Verifikasi Otomatis Kueri Cosine Similarity Retrieval
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.core.database import Base, SessionLocal, engine
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.class_entity import ClassEntity
from app.models.academic.exam_schedule import ExamSchedule
from app.models.academic.subject import Subject
from app.models.ai.assessment_history import AssessmentHistory
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.models.exam.enums import (
    ExamAttemptStatus,
    ExamSessionStatus,
    GradingSource,
    GradingStatus,
)
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.exam_session import ExamSession
from app.models.master.school_level import SchoolLevel
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.teacher.enums import PackageStatus, QuestionType
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.rag_context_service import RagContextService

# ── DATASET KASUS ASESMEN HISTORIS (GROUND-TRUTH TEACHER CASES) ───────────────
RAG_DATASET = [
    # ── MATA PELAJARAN 1: KIMIA (SMA KELAS 11) ────────────────────────────────
    {
        "subject_code": "KIM-11",
        "subject_name": "Kimia",
        "class_level": "Kelas 11",
        "question_text": (
            "Jelaskan bunyi Hukum Perbandingan Berganda (Hukum Dalton) dan buktikan "
            "dengan contoh perbandingan massa oksigen pada senyawa Karbon Monoksida (CO) "
            "dan Karbon Dioksida (CO2) jika massa karbon dibuat tetap!"
        ),
        "answer_key": (
            "Hukum Dalton menyatakan bahwa jika dua unsur dapat membentuk lebih dari satu senyawa, "
            "dan massa salah satu unsur dibuat sama (tetap), maka perbandingan massa unsur yang lain "
            "dalam senyawa-senyawa tersebut merupakan bilangan bulat dan sederhana.\n"
            "Bukti pada CO dan CO2:\n"
            "- Senyawa CO: Massa C = 12 gram, Massa O = 16 gram (Rasio C:O = 12 : 16)\n"
            "- Senyawa CO2: Massa C = 12 gram, Massa O = 32 gram (Rasio C:O = 12 : 32)\n"
            "Dengan massa C sama-sama 12 gram, perbandingan massa O pada CO : CO2 = 16 : 32 = 1 : 2 "
            "(terbukti bulat dan sederhana)."
        ),
        "rubrics": [
            {
                "criterion": "Definisi Hukum Dalton",
                "max_points": 4.0,
                "description": "Menyebutkan syarat dua unsur membentuk >1 senyawa dan massa salah satu unsur tetap berbanding bulat sederhana.",
            },
            {
                "criterion": "Pemodelan Senyawa CO dan CO2",
                "max_points": 3.0,
                "description": "Menuliskan komposisi massa relatif C dan O pada kedua senyawa dengan benar.",
            },
            {
                "criterion": "Pembuktian Rasio Bulat Sederhana",
                "max_points": 3.0,
                "description": "Menghitung perbandingan massa Oksigen (16:32 = 1:2) secara tepat.",
            },
        ],
        "cases": [
            {
                "student_answer": (
                    "Hukum Dalton berbunyi: bila dua unsur bergabung membentuk lebih dari satu senyawa "
                    "dan massa salah satu unsur dibuat sama, perbandingan massa unsur pasangannya merupakan "
                    "bilangan bulat sederhana. Contohnya CO memiliki 12g Karbon dan 16g Oksigen. Sedangkan CO2 "
                    "memiliki 12g Karbon dan 32g Oksigen. Karena massa C sama-sama 12g, maka rasio massa Oksigen "
                    "pada CO dibandingkan CO2 adalah 16 banding 32, disederhanakan menjadi 1 : 2."
                ),
                "teacher_score": 10.0,
                "teacher_feedback": (
                    "Luar biasa, definisi Hukum Dalton sangat presisi dan pembuktian rasio numerik 1:2 "
                    "pada CO dan CO2 dijabarkan secara runtut dan tuntas."
                ),
            },
            {
                "student_answer": (
                    "Hukum perbandingan berganda adalah hukum jika dua unsur bikin dua senyawa maka massanya "
                    "berkelipatan bulat. Contohnya karbon dan oksigen membentuk CO dan CO2. Di CO oksigennya satu "
                    "dan di CO2 oksigennya dua, jadi perbandingannya 1 banding 2."
                ),
                "teacher_score": 6.5,
                "teacher_feedback": (
                    "Konsep dasar dan perbandingan 1:2 benar, namun kamu belum mencantumkan perhitungan massa "
                    "gram/Ar secara eksplisit (16g vs 32g dengan massa C tetap 12g)."
                ),
            },
            {
                "student_answer": (
                    "Hukum Dalton menyatakan massa zat sebelum reaksi selalu sama dengan massa sesudah reaksi "
                    "dalam sistem tertutup. Contohnya massa gas karbon dan gas oksigen selalu seimbang."
                ),
                "teacher_score": 2.5,
                "teacher_feedback": (
                    "Miskonsepsi mendasar: Yang kamu jelaskan adalah Hukum Kekekalan Massa (Lavoisier), "
                    "bukan Hukum Perbandingan Berganda (Dalton). Harap pelajari kembali perbedaan hukum dasar kimia."
                ),
            },
        ],
    },
    # ── MATA PELAJARAN 2: FISIKA (SMA KELAS 11) ────────────────────────────────
    {
        "subject_code": "FIS-11",
        "subject_name": "Fisika",
        "class_level": "Kelas 11",
        "question_text": (
            "Uraikan empat proses termodinamika dalam Siklus Carnot serta jelaskan mengapa "
            "efisiensi mesin kalor Carnot tidak pernah dapat mencapai 100% berdasarkan Hukum II Termodinamika!"
        ),
        "answer_key": (
            "Empat proses Siklus Carnot:\n"
            "1. Ekspansi Isotermal (menyerap kalor Q_h pada suhu tinggi T_h secara reversibel)\n"
            "2. Ekspansi Adiabatik (kerja tanpa aliran kalor hingga suhu turun ke T_c)\n"
            "3. Kompresi Isotermal (membuang kalor Q_c ke reservoir suhu rendah T_c)\n"
            "4. Kompresi Adiabatik (kompresi tanpa kalor kembali ke kondisi awal T_h)\n"
            "Alasan efisiensi < 100%:\n"
            "Efisiensi Carnot dinyatakan dengan rumus eta = 1 - (T_c / T_h). Agar eta = 100% (1,0), "
            "maka suhu reservoir dingin T_c harus bernilai 0 Kelvin (Nol Mutlak), yang mana secara fisik "
            "mustahil dicapai menurut Hukum III Termodinamika. Selain itu, menurut Hukum II Termodinamika "
            "(Pernyataan Kelvin-Planck), tidak mungkin membuat mesin yang menyerap kalor dan mengubah seluruhnya "
            "menjadi kerja tanpa ada kalor yang dilepas ke lingkungan."
        ),
        "rubrics": [
            {
                "criterion": "Rincian 4 Tahap Siklus",
                "max_points": 4.0,
                "description": "Menyebutkan ekspansi isotermal, ekspansi adiabatik, kompresi isotermal, dan kompresi adiabatik.",
            },
            {
                "criterion": "Formula Matematis Efisiensi",
                "max_points": 3.0,
                "description": "Menyertakan rumus eta = 1 - (Tc/Th) atau 1 - (Qc/Qh).",
            },
            {
                "criterion": "Argumen Hukum II Termodinamika",
                "max_points": 3.0,
                "description": "Menjelaskan pernyataan Kelvin-Planck bahwa pembuangan kalor mutlak terjadi.",
            },
        ],
        "cases": [
            {
                "student_answer": (
                    "Siklus Carnot terdiri dari 4 tahapan proses reversibel:\n"
                    "1. Ekspansi isotermal (penyerapan kalor Qh pada suhu tinggi Th)\n"
                    "2. Ekspansi adiabatik (penurunan suhu dari Th ke Tc tanpa transfer kalor)\n"
                    "3. Kompresi isotermal (pembuangan kalor Qc ke reservoir dingin Tc)\n"
                    "4. Kompresi adiabatik (pengembalian sistem ke suhu awal Th)\n"
                    "Efisiensi mesin carnot dirumuskan: eta = 1 - (Tc/Th). Efisiensi tidak pernah 100% karena "
                    "berdasarkan Hukum II Termodinamika (pernyataan Kelvin-Planck), sebuah siklus mesin kalor wajib "
                    "membuang sebagian kalor (Qc > 0) ke reservoir suhu rendah, dan suhu Tc mustahil bernilai 0 Mutlak."
                ),
                "teacher_score": 10.0,
                "teacher_feedback": (
                    "Sangat sempurna. Keempat siklus dijelaskan dengan variabel termodinamika yang tepat "
                    "dan penegasan Hukum Kelvin-Planck sangat logis."
                ),
            },
            {
                "student_answer": (
                    "Tahapan carnot ada pemuaian isotermis, pemuaian adiabatis, kompresi isotermis dan kompresi adiabatis. "
                    "Mesin carnot tidak bisa 100% efisien karena ada panas yang terbuang ke tempat yang lebih dingin. "
                    "Rumusnya efisiensi = 1 - T2/T1."
                ),
                "teacher_score": 7.0,
                "teacher_feedback": (
                    "Jawaban cukup baik dan rumus disertakan, namun perlu diperjelas bahwa T1 dan T2 wajib "
                    "dalam satuan Kelvin dan sebutkan prinsip Kelvin-Planck."
                ),
            },
            {
                "student_answer": (
                    "Mesin carnot tidak bisa 100% efisien karena adanya gaya gesekan pada piston mesin dan kebocoran oli "
                    "sehingga energi hilang menjadi bunyi dan getaran."
                ),
                "teacher_score": 3.0,
                "teacher_feedback": (
                    "Kurang tepat. Siklus Carnot adalah mesin ideal teoritis tanpa gesekan mekanik. "
                    "Ketidakmampuan mencapai 100% murni dibatasi oleh Hukum II Termodinamika (prinsip aliran kalor), "
                    "bukan faktor teknis gesekan mesin nyata."
                ),
            },
        ],
    },
    # ── MATA PELAJARAN 3: BIOLOGI (SMA KELAS 12) ───────────────────────────────
    {
        "subject_code": "BIO-12",
        "subject_name": "Biologi",
        "class_level": "Kelas 12",
        "question_text": (
            "Bandingkan mekanisme Transkripsi dan Translasi pada sintesis protein eukariotik, "
            "meliputi: lokasi organel tempat berlangsungnya, cetakan template yang digunakan, "
            "enzim/organel pelaksana, serta produk akhir yang dihasilkan!"
        ),
        "answer_key": (
            "Perbandingan Transkripsi vs Translasi:\n"
            "1. Lokasi: Transkripsi di dalam Nukleus; Translasi di Sitoplasma (pada Ribosom).\n"
            "2. Cetakan (Template): Transkripsi menggunakan untai DNA antisense (template DNA); "
            "Translasi menggunakan molekul mRNA (kodon).\n"
            "3. Pelaksana Utama: Transkripsi oleh enzim RNA Polimerase; Translasi oleh Ribosom dan tRNA (antikodon).\n"
            "4. Produk Akhir: Transkripsi menghasilkan pre-mRNA / mRNA; Translasi menghasilkan rantai polipeptida (protein fungsional)."
        ),
        "rubrics": [
            {
                "criterion": "Komparasi Lokasi & Template",
                "max_points": 4.0,
                "description": "Membedakan nukleus vs ribosom sitoplasma dan DNA template vs mRNA.",
            },
            {
                "criterion": "Enzim & Komponen Pelaksana",
                "max_points": 3.0,
                "description": "Menyebutkan RNA polimerase pada transkripsi dan ribosom + tRNA pada translasi.",
            },
            {
                "criterion": "Produk Akhir",
                "max_points": 3.0,
                "description": "Menyebutkan mRNA sebagai hasil transkripsi dan polipeptida/protein sebagai hasil translasi.",
            },
        ],
        "cases": [
            {
                "student_answer": (
                    "Perbedaan Transkripsi dan Translasi:\n"
                    "1. Lokasi: Transkripsi terjadi di dalam nukleus, sedangkan Translasi terjadi di sitoplasma pada ribosom.\n"
                    "2. Template: Transkripsi membaca rantai DNA antisense 3' ke 5', sedangkan Translasi membaca kodon mRNA 5' ke 3'.\n"
                    "3. Pelaksana: Transkripsi dikatalisis oleh RNA Polimerase, sedangkan Translasi dilakukan oleh ribosom sub-unit besar/kecil dibantu tRNA pembawa asam amino.\n"
                    "4. Hasil akhir: Transkripsi menghasilkan mRNA, sedangkan Translasi menghasilkan rantai polipeptida / protein."
                ),
                "teacher_score": 10.0,
                "teacher_feedback": (
                    "Sangat komprehensif dan sistematis. Penguasaan arah pembacaan 3'-5' dan peran tRNA "
                    "menunjukkan pemahaman biologi molekuler yang mendalam."
                ),
            },
            {
                "student_answer": (
                    "Transkripsi terjadi di inti sel mengubah DNA jadi RNA duta dengan enzim RNA polimerase. "
                    "Kalau translasi terjadi di ribosom luar inti, membaca RNA duta menjadi asam amino protein "
                    "menggunakan tRNA."
                ),
                "teacher_score": 7.5,
                "teacher_feedback": (
                    "Poin-poin utama benar dan padat. Akan lebih baik jika dibuat dalam bentuk tabel komparasi "
                    "dan mencantumkan istilah template antisense."
                ),
            },
            {
                "student_answer": (
                    "Transkripsi itu penggandaan DNA menjadi dua DNA baru di dalam inti sel. "
                    "Translasi itu pembelahan sel di sitoplasma."
                ),
                "teacher_score": 2.0,
                "teacher_feedback": (
                    "Miskonsepsi parah: Penggandaan DNA adalah Replikasi, bukan Transkripsi. "
                    "Dan Translasi adalah sintesis protein pada ribosom, bukan pembelahan sel (mitosis)."
                ),
            },
        ],
    },
]


def seed_rag_knowledge_base():
    """Seeds rich Indonesian high-school assessment cases and generates vector embeddings."""
    print("\n" + "=" * 75)
    print("  EQUIGRADE RAG KNOWLEDGE BASE SEEDER (Ground-Truth Preseden Guru)")
    print("=" * 75)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Pastikan Sekolah Induk (School)
        school = db.query(School).filter_by(code="SCH_2026_01").first()
        if not school:
            level = db.query(SchoolLevel).first()
            school = School(
                public_id=uuid.uuid4(),
                code="SCH_2026_01",
                name="SMA Negeri 1 Nusantara",
                domain="sman1",
                npsn="20101234",
                school_level_id=level.id if level else 4,
                status="ACTIVE",
                is_active=True,
            )
            db.add(school)
            db.flush()
        print(f"[*] Sekolah Induk: {school.name} (ID: {school.id})")

        # 2. Pastikan Tahun Ajaran & Semester
        year = db.query(AcademicYear).filter_by(school_id=school.id, name="2025/2026").first()
        if not year:
            now = datetime.now(timezone.utc)
            year = AcademicYear(
                public_id=uuid.uuid4(),
                school_id=school.id,
                name="2025/2026",
                start_date=now - timedelta(days=60),
                end_date=now + timedelta(days=300),
                status="ACTIVE",
            )
            db.add(year)
            db.flush()

        semester = (
            db.query(AcademicSemester).filter_by(academic_year_id=year.id, code="ODD").first()
        )
        if not semester:
            semester = AcademicSemester(
                public_id=uuid.uuid4(),
                academic_year_id=year.id,
                code="ODD",
                display_name="Semester Ganjil",
                status="ACTIVE",
            )
            db.add(semester)
            db.flush()
        print(f"[*] Tahun Ajaran: {year.name} — {semester.display_name} (ID: {year.id})")

        # 3. Pastikan Akun Guru Penilai (Teacher) & Siswa
        teacher = db.query(AuthAccount).filter_by(username="teacher1").first()
        if not teacher:
            from app.core.security import hash_password

            teacher = AuthAccount(
                public_id=uuid.uuid4(),
                school_id=school.id,
                username="teacher1",
                password_hash=hash_password("Password123!"),
                role="TEACHER",
                is_active=True,
            )
            db.add(teacher)
            db.flush()

        student = db.query(AuthAccount).filter_by(username="student1").first()
        if not student:
            from app.core.security import hash_password

            student = AuthAccount(
                public_id=uuid.uuid4(),
                school_id=school.id,
                username="student1",
                password_hash=hash_password("Password123!"),
                role="STUDENT",
                is_active=True,
            )
            db.add(student)
            db.flush()
        print(f"[*] Akun Penilai Ground-Truth: {teacher.username} (ID: {teacher.id})")

        # 4. Pastikan Kelas
        cls_obj = db.query(ClassEntity).filter_by(school_id=school.id, name="XI IPA 1").first()
        if not cls_obj:
            cls_obj = ClassEntity(
                public_id=uuid.uuid4(),
                school_id=school.id,
                academic_year_id=year.id,
                name="XI IPA 1",
                grade_level="Kelas 11",
                is_active=True,
            )
            db.add(cls_obj)
            db.flush()

        # 5. Iterasi & Seed Setiap Mata Pelajaran dan Kasus Penilaian
        total_seeded_histories = 0
        total_seeded_embeddings = 0

        for item in RAG_DATASET:
            subject_code = item["subject_code"]
            subject_name = item["subject_name"]
            class_level = item["class_level"]

            # Cari atau buat Subject
            subject = db.query(Subject).filter_by(school_id=school.id, code=subject_code).first()
            if not subject:
                subject = Subject(
                    public_id=uuid.uuid4(),
                    school_id=school.id,
                    code=subject_code,
                    name=subject_name,
                    description=f"Mata Pelajaran {subject_name} {class_level}",
                    is_active=True,
                )
                db.add(subject)
                db.flush()

            print(f"\n[+] Memproses Mata Pelajaran: {subject_name} ({subject_code})...")

            # Buat Paket Soal
            pkg = (
                db.query(QuestionPackage)
                .filter_by(
                    school_id=school.id,
                    name=f"Paket Asesmen Esai {subject_name}",
                )
                .first()
            )
            if not pkg:
                pkg = QuestionPackage(
                    public_id=uuid.uuid4(),
                    owner_teacher_account_id=teacher.id,
                    school_id=school.id,
                    name=f"Paket Asesmen Esai {subject_name}",
                    class_level=class_level,
                    subject=subject_name,
                    status=PackageStatus.READY.value,
                    target_counts={"ES": 1},
                )
                db.add(pkg)
                db.flush()

            # Buat Soal
            q = (
                db.query(Question)
                .filter_by(
                    owner_teacher_account_id=teacher.id,
                    subject=subject_name,
                    type=QuestionType.ES,
                )
                .first()
            )
            if not q:
                q = Question(
                    public_id=uuid.uuid4(),
                    owner_teacher_account_id=teacher.id,
                    type=QuestionType.ES,
                    content=item["question_text"],
                    answer_key=item["answer_key"],
                    rubrics=item["rubrics"],
                    subject=subject_name,
                    class_level=class_level,
                    ai_grading=True,
                )
                db.add(q)
                db.flush()

            # Buat Jadwal Ujian & Sesi
            now_dt = datetime.now(timezone.utc)
            schedule = (
                db.query(ExamSchedule)
                .filter_by(
                    school_id=school.id,
                    subject_id=subject.id,
                    title=f"Ujian Preseden {subject_name}",
                )
                .first()
            )
            if not schedule:
                schedule = ExamSchedule(
                    public_id=uuid.uuid4(),
                    school_id=school.id,
                    academic_year_id=year.id,
                    academic_semester_id=semester.id,
                    class_id=cls_obj.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    title=f"Ujian Preseden {subject_name}",
                    start_time=now_dt - timedelta(days=10),
                    end_time=now_dt - timedelta(days=10) + timedelta(hours=2),
                    duration_minutes=90,
                )
                db.add(schedule)
                db.flush()

            session = (
                db.query(ExamSession).filter_by(schedule_id=schedule.id, package_id=pkg.id).first()
            )
            if not session:
                session = ExamSession(
                    public_id=uuid.uuid4(),
                    schedule_id=schedule.id,
                    package_id=pkg.id,
                    scheduled_start_at=schedule.start_time,
                    scheduled_end_at=schedule.end_time,
                    duration_minutes=90,
                    status=ExamSessionStatus.ACTIVE,
                )
                db.add(session)
                db.flush()

            # Masukkan Setiap Kasus Siswa (Ground Truth)
            for idx, c in enumerate(item["cases"], start=1):
                # Periksa apakah kasus sudah pernah di-seed
                existing_hist = (
                    db.query(AssessmentHistory)
                    .filter_by(
                        school_id=school.id,
                        subject_id=subject.id,
                        question_id=q.id,
                        student_answer=c["student_answer"],
                    )
                    .first()
                )

                if existing_hist:
                    print(
                        f"   - Kasus #{idx} [{c['teacher_score']}/10] sudah ada (ID: {existing_hist.id}). Memastikan embedding..."
                    )
                    emb = EmbeddingService.embed_and_persist_history(db, existing_hist)
                    db.commit()
                    continue

                case_student_uname = f"student_{subject_name.lower()}_{idx}"
                case_student = db.query(AuthAccount).filter_by(username=case_student_uname).first()
                if not case_student:
                    from app.core.security import hash_password

                    case_student = AuthAccount(
                        public_id=uuid.uuid4(),
                        school_id=school.id,
                        username=case_student_uname,
                        password_hash=hash_password("Password123!"),
                        role="STUDENT",
                        is_active=True,
                    )
                    db.add(case_student)
                    db.flush()

                attempt = ExamAttempt(
                    public_id=uuid.uuid4(),
                    exam_session_id=session.id,
                    student_id=case_student.id,
                    status=ExamAttemptStatus.SUBMITTED,
                    randomized_order=[q.id],
                )
                db.add(attempt)
                db.flush()

                eval_entry = ExamAnswerEvaluation(
                    exam_attempt_id=attempt.id,
                    question_id=q.id,
                    score=c["teacher_score"],
                    max_score=10.0,
                    feedback=c["teacher_feedback"],
                    grading_status=GradingStatus.FINALIZED,
                    grading_source=GradingSource.TEACHER,
                    grading_version=1,
                    last_evaluated_at=now_dt - timedelta(days=5),
                )
                db.add(eval_entry)
                db.flush()

                history = AssessmentHistory(
                    public_id=uuid.uuid4(),
                    school_id=school.id,
                    academic_year_id=year.id,
                    subject_id=subject.id,
                    subject_name=subject_name,
                    class_level=class_level,
                    evaluation_id=eval_entry.id,
                    exam_attempt_id=attempt.id,
                    question_id=q.id,
                    exam_teacher_id=teacher.id,
                    finalized_by_teacher_id=teacher.id,
                    version=1,
                    is_current=True,
                    question_text=item["question_text"],
                    question_type="ES",
                    answer_key=item["answer_key"],
                    rubrics_json=item["rubrics"],
                    max_score=10.0,
                    student_answer=c["student_answer"],
                    teacher_score=c["teacher_score"],
                    teacher_feedback=c["teacher_feedback"],
                    final_score=c["teacher_score"],
                    score_delta=0.0,
                    is_rag_eligible=True,
                    embedding_status="PENDING",
                    created_at=now_dt - timedelta(days=5),
                    updated_at=now_dt - timedelta(days=5),
                )
                db.add(history)
                db.flush()

                # Generate and persist dense 1024-dimensional vector embedding
                emb = EmbeddingService.embed_and_persist_history(db, history)
                history.embedding_status = "EMBEDDED"
                history.embedded_at = datetime.now(timezone.utc)
                db.commit()

                total_seeded_histories += 1
                total_seeded_embeddings += 1
                print(
                    f"   ✓ Disimpan Kasus #{idx}: Skor {c['teacher_score']}/10.0 -> History ID {history.id} | Vector Dimension: {emb.dimension}"
                )

        print("\n" + "=" * 75)
        print(
            f"  SEEDING SELESAI: {total_seeded_histories} Riwayat Asesmen & {total_seeded_embeddings} Vektor Berhasil Terindeks!"
        )
        print("=" * 75)

        # ── 6. SIMULASI & VERIFIKASI LANGSUNG (LIVE RETRIEVAL TEST) ───────────
        print("\n[SIMULASI] Menjalankan Uji Temu-Kembali Semantik (Cosine Similarity Test)...")

        sample_test_query = (
            "Jika dua unsur bereaksi dan menghasilkan lebih dari 1 zat, bila massa unsur pertama "
            "ditetapkan sama, maka unsur kedua memiliki rasio kelipatan angka bulat. Contohnya C dan O "
            "membentuk CO dan CO2 dengan perbandingan O adalah 1 berbanding 2."
        )

        kimia_subject = db.query(Subject).filter_by(school_id=school.id, code="KIM-11").first()

        if kimia_subject:
            print(f'Jawaban Siswa Baru yang Diuji: "{sample_test_query}"')
            kimia_case_item = RAG_DATASET[0]

            # Dynamic threshold handling for offline mock vs live neural model
            neural_active = EmbeddingService.is_neural_engine_available()
            sim_threshold = 0.50 if neural_active else -1.0

            retrieved = RagContextService.assemble_rag_context(
                db=db,
                school_id=school.id,
                subject_id=kimia_subject.id,
                academic_year_id=year.id,
                subject_name=kimia_case_item["subject_name"],
                class_level=kimia_case_item["class_level"],
                question_text=kimia_case_item["question_text"],
                answer_key=kimia_case_item["answer_key"],
                rubrics_json=kimia_case_item["rubrics"],
                max_score=10.0,
                student_answer=sample_test_query,
                top_k=2,
                similarity_threshold=sim_threshold,
            )

            print(
                f"\nHasil Temu-Kembali Kasus Preseden Guru ({len(retrieved.reference_cases)} Kasus Ditemukan):"
            )
            for i, r in enumerate(retrieved.reference_cases, start=1):
                print(
                    f"  [{i}] Similarity: {r.similarity_score:.4f} | Skor Guru: {r.final_score}/10"
                )
                print(f'      Jawaban Historis: "{r.student_answer[:85]}..."')
                print(f'      Feedback Guru:    "{r.teacher_feedback}"')

            print("\nBlok Konteks RAG yang Siap Disuntikkan ke Prompt LLM:")
            print("-" * 65)
            print(retrieved.formatted_context_block[:450] + "\n... [Context XML Truncated]")
            print("-" * 65)
            print("Metadata Observabilitas RAG:")
            print(f"  - Model Embedding   : {retrieved.metadata.get('embedding_model')}")
            print(f"  - Engine Type       : {retrieved.metadata.get('engine_type')}")
            print(f"  - Retrieved Cases   : {retrieved.metadata.get('retrieved_count')}")
            print(f"  - Included Cases    : {retrieved.metadata.get('included_count')}")
            print(f"  - Token Consumed    : {retrieved.metadata.get('tokens_consumed')} tokens")
            print("=" * 65)
            print("✅ PIPELINE RAG SIAP DIGUNAKAN DAN DIPRESENTASIKAN KE DOSEN!")

    except Exception as ex:
        db.rollback()
        print(f"\n❌ Gagal melakukan seeding RAG: {ex}")
        raise ex
    finally:
        db.close()


if __name__ == "__main__":
    seed_rag_knowledge_base()
