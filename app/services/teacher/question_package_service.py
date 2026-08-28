from sqlalchemy.orm import Session

from app.exceptions import BusinessException
from app.models.teacher.enums import PackageStatus
from app.models.teacher.package_item import QuestionPackageItem
from app.models.teacher.question_package import QuestionPackage
from app.repositories.teacher.question_package_repository import question_package_repository
from app.repositories.teacher.question_repository import question_repository


class QuestionPackageService:

    @staticmethod
    def create_package(
        db: Session,
        name: str,
        class_level: str,
        target_counts: dict,
        teacher_account_id: int,
        school_id: int,
        subject: str,
    ) -> QuestionPackage:
        try:
            package = QuestionPackage(
                name=name,
                class_level=class_level,
                target_counts=target_counts,
                owner_teacher_account_id=teacher_account_id,
                school_id=school_id,
                status=PackageStatus.INCOMPLETE,
                subject=subject,
            )
            question_package_repository.create(db, package)
            db.commit()
            return package
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def add_question_to_package(
        db: Session,
        package_id: int,
        question_id: int,
        teacher_account_id: int,
        school_id: int,
        score: float = 0.0,
    ) -> QuestionPackage:
        try:
            # 1. Validasi Kepemilikan Paket Soal (Teacher & Tenant isolation)
            package = question_package_repository.get_by_id(db, package_id)
            if (
                not package
                or package.owner_teacher_account_id != teacher_account_id
                or package.school_id != school_id
            ):
                raise BusinessException(
                    "Akses ditolak: Paket soal tidak ditemukan atau bukan milik Anda.",
                    status_code=403,
                )

            # 2. Validasi Kunci Invarian Tenant & Kepemilikan Soal secara Terpadu
            # Menjamin soal dimiliki oleh guru pembuat, dan guru tersebut berada di sekolah (tenant) yang sama dengan paket
            question = question_repository.get_owned_question_in_school(
                db, question_id, teacher_account_id, school_id
            )
            if not question:
                raise BusinessException(
                    "Akses ditolak: Soal tidak ditemukan di Question Bank pribadi Anda pada sekolah ini.",
                    status_code=403,
                )

            # 3. Validasi Kelebihan Soal (Target Overflow Prevention)
            actual_counts = question_package_repository.get_with_question_count_by_type(
                db, package_id
            )
            q_type = question.type.value if hasattr(question.type, "value") else question.type
            target_limit = package.target_counts.get(q_type, 0)
            actual_count = actual_counts.get(q_type, 0)

            if actual_count >= target_limit:
                raise BusinessException(
                    f"QUESTION_TARGET_EXCEEDED: Batas jumlah soal tipe {q_type} ({target_limit} butir) sudah terpenuhi.",
                    status_code=400,
                )

            # 4. Hitung Canonical Order secara Otomatis (Domain Controlled State)
            max_order = question_package_repository.get_max_canonical_order(db, package_id)
            next_order = max_order + 1

            # 5. Insert Join Item
            item = QuestionPackageItem(
                package_id=package_id,
                question_id=question_id,
                canonical_order=next_order,
                score=score,
            )
            db.add(item)
            db.flush()

            # 6. Validasi Kelengkapan (Tepat Sama / Equal Check)
            updated_counts = question_package_repository.get_with_question_count_by_type(
                db, package_id
            )
            is_complete = True
            for q_type, target_num in package.target_counts.items():
                if updated_counts.get(q_type, 0) != target_num:
                    is_complete = False
                    break

            package.status = PackageStatus.READY if is_complete else PackageStatus.INCOMPLETE
            db.commit()
            return package
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def reorder_questions(
        db: Session, package_id: int, order_map: dict[int, int], teacher_account_id: int
    ) -> QuestionPackage:
        """Use Case Mengubah urutan soal secara aman dari tabrakan Unique Constraint."""
        try:
            package = question_package_repository.get_by_id(db, package_id)
            if not package or package.owner_teacher_account_id != teacher_account_id:
                raise BusinessException("Akses ditolak.", status_code=403)

            # Validasi Set Question ID (Mencegah pengiriman ID siluman/luar paket)
            package_question_ids = {item.question_id for item in package.items}
            requested_question_ids = set(order_map.keys())
            if requested_question_ids != package_question_ids:
                raise BusinessException(
                    "REORDER_INVALID_QUESTION_SET: Kumpulan ID soal tidak sesuai dengan isi paket.",
                    status_code=400,
                )

            # Validasi urutan (harus unik dan berurutan dari 1 s.d N)
            new_orders = list(order_map.values())
            n = len(package.items)
            if sorted(new_orders) != list(range(1, n + 1)):
                raise BusinessException(
                    "Urutan canonical tidak valid (harus berurutan dari 1 sampai N).",
                    status_code=400,
                )

            # Two-Phase Update untuk menjamin Collision-Safety di bawah unique constraint (package_id, canonical_order):
            # Phase 1: Ubah urutan item yang terpengaruh menjadi nilai negatif sementara
            for item in package.items:
                if item.question_id in order_map:
                    item.canonical_order = -order_map[item.question_id]
            db.flush()  # Paksa flush untuk menerapkan nilai negatif ke DB tanpa melanggar unique constraint

            # Phase 2: Ubah kembali nilai negatif sementara menjadi nilai positif urutan final
            for item in package.items:
                if item.question_id in order_map:
                    item.canonical_order = order_map[item.question_id]

            db.commit()
            return package
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def remove_question_from_package(
        db: Session,
        package_id: int,
        question_id: int,
        teacher_account_id: int,
        school_id: int,
    ) -> QuestionPackage:
        try:
            package = question_package_repository.get_by_id(db, package_id)
            if (
                not package
                or package.owner_teacher_account_id != teacher_account_id
                or package.school_id != school_id
            ):
                raise BusinessException(
                    "Akses ditolak: Paket soal tidak ditemukan atau bukan milik Anda.",
                    status_code=403,
                )

            item = question_package_repository.get_item(db, package_id, question_id)

            if not item:
                raise BusinessException(
                    "Soal tidak ditemukan dalam paket ini.",
                    status_code=404,
                )

            question_package_repository.delete_item(db, item)
            db.flush()

            # Re-index canonical order
            remaining_items = question_package_repository.list_items(db, package_id)

            # Phase 1: Set temporary negative order to prevent collision
            for idx, r_item in enumerate(remaining_items, start=1):
                r_item.canonical_order = -idx
            db.flush()

            # Phase 2: Set positive order
            for idx, r_item in enumerate(remaining_items, start=1):
                r_item.canonical_order = idx

            # Re-evaluate status
            updated_counts = question_package_repository.get_with_question_count_by_type(
                db, package_id
            )
            is_complete = True
            for q_type, target_num in package.target_counts.items():
                if updated_counts.get(q_type, 0) != target_num:
                    is_complete = False
                    break

            package.status = PackageStatus.READY if is_complete else PackageStatus.INCOMPLETE
            db.commit()
            return package
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def replace_question_in_package(
        db: Session,
        package_id: int,
        old_question_id: int,
        new_question_id: int,
        teacher_account_id: int,
        school_id: int,
        score: float | None = None,
    ) -> QuestionPackage:
        try:
            package = question_package_repository.get_by_id(db, package_id)
            if (
                not package
                or package.owner_teacher_account_id != teacher_account_id
                or package.school_id != school_id
            ):
                raise BusinessException(
                    "Akses ditolak: Paket soal tidak ditemukan atau bukan milik Anda.",
                    status_code=403,
                )

            old_item = question_package_repository.get_item(db, package_id, old_question_id)

            if not old_item:
                raise BusinessException(
                    "Soal lama tidak ditemukan dalam paket ini.",
                    status_code=404,
                )

            old_q = question_repository.get_by_id(db, old_question_id)
            new_q = question_repository.get_owned_question_in_school(
                db, new_question_id, teacher_account_id, school_id
            )

            if not new_q:
                raise BusinessException(
                    "Akses ditolak: Soal pengganti tidak ditemukan di Question Bank Anda pada sekolah ini.",
                    status_code=403,
                )

            old_type = old_q.type.value if hasattr(old_q.type, "value") else old_q.type
            new_type = new_q.type.value if hasattr(new_q.type, "value") else new_q.type

            if old_type != new_type:
                raise BusinessException(
                    f"Penggantian soal harus sejenis (tipe {old_type}). Soal pengganti bertipe {new_type}.",
                    status_code=400,
                )

            # Check if new question is already in package
            already_in_pkg = question_package_repository.get_item(db, package_id, new_question_id)

            if already_in_pkg:
                raise BusinessException(
                    "Soal pengganti sudah ada di dalam paket ini.",
                    status_code=400,
                )

            old_item.question_id = new_question_id
            if score is not None and score > 0:
                old_item.score = score

            # Re-evaluate status
            updated_counts = question_package_repository.get_with_question_count_by_type(
                db, package_id
            )
            is_complete = True
            for q_type, target_num in package.target_counts.items():
                if updated_counts.get(q_type, 0) != target_num:
                    is_complete = False
                    break

            package.status = PackageStatus.READY if is_complete else PackageStatus.INCOMPLETE
            db.commit()
            return package
        except Exception:
            db.rollback()
            raise
