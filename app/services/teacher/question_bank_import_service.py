"""
Batch 4A — Question Bank Atomic Bulk Import Service.

Contract:
- FIRST PASS: validate ALL rows before any write.
- SECOND PASS: DB duplicate check (skip, not error).
- THIRD PASS (WRITE): persist new questions under savepoint.
- Subject: free-text string from user context (top-level in request).
- owner_teacher_account_id: from JWT only, never from request payload.
- class_level: free-text string, no DB lookup.
- No QuestionPackage, ExamSnapshot, ExamSchedule, ExamAttempt mutation.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.teacher.question import Question
from app.repositories.teacher.question_repository import question_repository


class QuestionBankImportService:

    @staticmethod
    def _validate_options_contiguous(options: list) -> tuple:
        if not options:
            return None, "Soal PG wajib memiliki opsi (minimal Opsi A dan Opsi B)."
        trimmed = [str(o).strip() for o in options]
        first_empty = None
        for i, opt in enumerate(trimmed):
            if not opt:
                first_empty = i
                break
        if first_empty is not None:
            for i in range(first_empty + 1, len(trimmed)):
                if trimmed[i]:
                    return None, (
                        f"Opsi tidak boleh ada gap: Opsi {chr(65 + i)} terisi "
                        f"setelah Opsi {chr(65 + first_empty)} kosong."
                    )
            cleaned = trimmed[:first_empty]
        else:
            cleaned = trimmed
        if len(cleaned) < 2:
            return None, "Soal PG wajib memiliki minimal 2 opsi (Opsi A dan Opsi B)."
        if len(cleaned) > 6:
            return None, "Soal PG maksimal 6 opsi (Opsi A sampai Opsi F)."
        return cleaned, None

    @staticmethod
    def _validate_pg(row_data: dict, row_num: int, sheet: str, errors: list) -> bool:
        content = row_data.get("content", "")
        answer_key = row_data.get("answer_key", "")
        options = row_data.get("options") or []
        rubrics = row_data.get("rubrics") or []
        ai_grading = bool(row_data.get("ai_grading", False))

        if ai_grading:
            errors.append(
                {
                    "row": row_num,
                    "field": "ai_grading",
                    "value": "true",
                    "code": "AI_GRADING_NOT_ALLOWED_FOR_PG",
                    "message": f"[{sheet}] Baris {row_num}: Soal PG tidak boleh mengaktifkan AI grading.",
                }
            )
            return False
        if rubrics:
            errors.append(
                {
                    "row": row_num,
                    "field": "rubrics",
                    "value": str(rubrics),
                    "code": "RUBRIC_NOT_ALLOWED_FOR_PG",
                    "message": f"[{sheet}] Baris {row_num}: Soal PG tidak boleh memiliki rubrik penilaian.",
                }
            )
            return False

        if not content:
            errors.append(
                {
                    "row": row_num,
                    "field": "content",
                    "value": "",
                    "code": "CONTENT_REQUIRED",
                    "message": f"[{sheet}] Baris {row_num}: Kolom Pertanyaan tidak boleh kosong.",
                }
            )
            return False
        if not answer_key:
            errors.append(
                {
                    "row": row_num,
                    "field": "answer_key",
                    "value": "",
                    "code": "ANSWER_KEY_REQUIRED",
                    "message": f"[{sheet}] Baris {row_num}: Kolom Kunci Jawaban tidak boleh kosong.",
                }
            )
            return False
        str_options = [str(o).strip() for o in options]
        cleaned, err_msg = QuestionBankImportService._validate_options_contiguous(str_options)
        if err_msg:
            errors.append(
                {
                    "row": row_num,
                    "field": "options",
                    "value": str(str_options),
                    "code": "PG_OPTIONS_INVALID",
                    "message": f"[{sheet}] Baris {row_num}: {err_msg}",
                }
            )
            return False
        if answer_key not in (cleaned or []):
            errors.append(
                {
                    "row": row_num,
                    "field": "answer_key",
                    "value": answer_key,
                    "code": "PG_ANSWER_KEY_NOT_IN_OPTIONS",
                    "message": f'[{sheet}] Baris {row_num}: Kunci Jawaban "{answer_key}" tidak cocok dengan opsi mana pun.',
                }
            )
            return False
        row_data["_cleaned_options"] = cleaned
        return True

    @staticmethod
    def _validate_is(row_data: dict, row_num: int, sheet: str, errors: list) -> bool:
        content = row_data.get("content", "")
        answer_key = row_data.get("answer_key", "")
        rubrics = row_data.get("rubrics") or []
        ai_grading = bool(row_data.get("ai_grading", False))

        if ai_grading:
            errors.append(
                {
                    "row": row_num,
                    "field": "ai_grading",
                    "value": "true",
                    "code": "AI_GRADING_NOT_ALLOWED_FOR_IS",
                    "message": f"[{sheet}] Baris {row_num}: Soal Isian Singkat tidak boleh mengaktifkan AI grading.",
                }
            )
            return False
        if rubrics:
            errors.append(
                {
                    "row": row_num,
                    "field": "rubrics",
                    "value": str(rubrics),
                    "code": "RUBRIC_NOT_ALLOWED_FOR_IS",
                    "message": f"[{sheet}] Baris {row_num}: Soal Isian Singkat tidak boleh memiliki rubrik penilaian.",
                }
            )
            return False

        if not content:
            errors.append(
                {
                    "row": row_num,
                    "field": "content",
                    "value": "",
                    "code": "CONTENT_REQUIRED",
                    "message": f"[{sheet}] Baris {row_num}: Kolom Pertanyaan tidak boleh kosong.",
                }
            )
            return False
        if not answer_key:
            errors.append(
                {
                    "row": row_num,
                    "field": "answer_key",
                    "value": "",
                    "code": "ANSWER_KEY_REQUIRED",
                    "message": f"[{sheet}] Baris {row_num}: Kolom Kunci Jawaban tidak boleh kosong.",
                }
            )
            return False
        return True

    @staticmethod
    def _validate_essay(row_data: dict, row_num: int, sheet: str, errors: list) -> bool:
        content = row_data.get("content", "")
        answer_key = row_data.get("answer_key", "")
        ai_grading = bool(row_data.get("ai_grading", False))
        rubrics = row_data.get("rubrics") or []

        if not content:
            errors.append(
                {
                    "row": row_num,
                    "field": "content",
                    "value": "",
                    "code": "CONTENT_REQUIRED",
                    "message": f"[{sheet}] Baris {row_num}: Kolom Pertanyaan tidak boleh kosong.",
                }
            )
            return False
        if not answer_key:
            errors.append(
                {
                    "row": row_num,
                    "field": "answer_key",
                    "value": "",
                    "code": "ANSWER_KEY_REQUIRED",
                    "message": f"[{sheet}] Baris {row_num}: Kolom Kunci Jawaban tidak boleh kosong.",
                }
            )
            return False

        if ai_grading:
            if rubrics:
                errors.append(
                    {
                        "row": row_num,
                        "field": "rubrics",
                        "value": str(rubrics),
                        "code": "RUBRIC_NOT_ALLOWED_FOR_AI_GRADING",
                        "message": f"[{sheet}] Baris {row_num}: Soal Essay dengan AI Grading aktif harus memiliki rubrik kosong.",
                    }
                )
                return False
            return True
        else:
            if not rubrics or len(rubrics) < 1:
                errors.append(
                    {
                        "row": row_num,
                        "field": "rubrics",
                        "value": "[]",
                        "code": "ESSAY_RUBRIC_REQUIRED",
                        "message": f"[{sheet}] Baris {row_num}: Untuk AI Grading = TIDAK, rubrik manual wajib diisi minimal 1 kriteria.",
                    }
                )
                return False
            if len(rubrics) > 5:
                errors.append(
                    {
                        "row": row_num,
                        "field": "rubrics",
                        "value": f"length={len(rubrics)}",
                        "code": "ESSAY_RUBRIC_LIMIT_EXCEEDED",
                        "message": f"[{sheet}] Baris {row_num}: Rubrik manual maksimal berisi 5 kriteria.",
                    }
                )
                return False

            row_valid = True
            for idx, rubric in enumerate(rubrics):
                criteria = str(rubric.get("criteria", "")).strip()
                max_score_raw = rubric.get("max_score", 0)
                if not criteria:
                    errors.append(
                        {
                            "row": row_num,
                            "field": f"rubrics[{idx}].criteria",
                            "value": "",
                            "code": "RUBRIC_CRITERIA_EMPTY",
                            "message": f"[{sheet}] Baris {row_num}: Kriteria rubrik ke-{idx + 1} tidak boleh kosong.",
                        }
                    )
                    row_valid = False
                try:
                    score_val = float(max_score_raw)
                    if score_val <= 0:
                        raise ValueError("max_score must be > 0")
                except (TypeError, ValueError):
                    errors.append(
                        {
                            "row": row_num,
                            "field": f"rubrics[{idx}].max_score",
                            "value": str(max_score_raw),
                            "code": "RUBRIC_MAX_SCORE_INVALID",
                            "message": f"[{sheet}] Baris {row_num}: Skor maksimum rubrik ke-{idx + 1} harus angka positif (> 0).",
                        }
                    )
                    row_valid = False
            return row_valid

    @staticmethod
    def import_questions_batch(
        db: Session,
        teacher_account_id: int,
        school_id: int,
        subject: str,
        rows_data: list,
    ) -> tuple:
        """
        Atomic batch import.
        Note: school_id is intentionally passed as explicit tenant context parameter,
        representing the active school bound to the authenticated user, but currently
        security and database schema relations rely on teacher_account_id directly.
        Returns: (success, created_questions, validation_errors, skipped_rows)
        """
        from app.models.teacher.enums import QuestionType

        errors: list = []
        skipped: list = []
        in_file_seen: dict = {}
        validated_rows: list = []

        for row in rows_data:
            q_type_raw = str(row.get("type", "")).strip()
            content_raw = str(row.get("content", "")).strip()
            answer_key_raw = str(row.get("answer_key", "")).strip()
            options_raw = row.get("options") or []
            rubrics_raw = row.get("rubrics") or []
            ai_grading = bool(row.get("ai_grading", False))
            class_level = (row.get("class_level") or "").strip() or None
            row_num = int(row.get("row_num", 0))
            sheet = str(row.get("sheet", ""))

            try:
                qt = QuestionType(q_type_raw)
            except ValueError:
                errors.append(
                    {
                        "row": row_num,
                        "field": "type",
                        "value": q_type_raw,
                        "code": "INVALID_QUESTION_TYPE",
                        "message": f'[{sheet}] Baris {row_num}: Tipe soal "{q_type_raw}" tidak valid. Gunakan PG, IS, atau ES.',
                    }
                )
                continue

            row_data: dict = {
                "type": q_type_raw,
                "content": content_raw,
                "answer_key": answer_key_raw,
                "options": [str(o).strip() for o in options_raw],
                "rubrics": rubrics_raw,
                "ai_grading": ai_grading,
                "class_level": class_level,
                "row_num": row_num,
                "sheet": sheet,
                "_qt": qt,
            }

            if qt == QuestionType.PG:
                if not QuestionBankImportService._validate_pg(row_data, row_num, sheet, errors):
                    continue
                row_data["_final_options"] = row_data.get("_cleaned_options", [])
                row_data["_final_rubrics"] = []
            elif qt == QuestionType.IS:
                if not QuestionBankImportService._validate_is(row_data, row_num, sheet, errors):
                    continue
                row_data["_final_options"] = None
                row_data["_final_rubrics"] = []
            elif qt == QuestionType.ES:
                if not QuestionBankImportService._validate_essay(row_data, row_num, sheet, errors):
                    continue
                row_data["_final_options"] = None
                row_data["_final_rubrics"] = rubrics_raw

            dedup_key = f"{content_raw.lower().strip()}|{q_type_raw}"
            if dedup_key in in_file_seen:
                errors.append(
                    {
                        "row": row_num,
                        "field": "content",
                        "value": content_raw[:120],
                        "code": "DUPLICATE_IN_FILE",
                        "message": f"[{sheet}] Baris {row_num}: Soal identik dengan baris {in_file_seen[dedup_key]} (tipe: {q_type_raw}). Duplikat dalam file tidak diizinkan.",
                    }
                )
                continue

            in_file_seen[dedup_key] = row_num
            validated_rows.append(row_data)

        if errors:
            return False, [], errors, []

        new_rows: list = []
        for row_data in validated_rows:
            content_norm = row_data["content"].lower().strip()
            q_type_str = row_data["type"]
            row_num = row_data["row_num"]
            sheet = row_data["sheet"]
            existing = question_repository.find_by_owner_content_type(
                db, teacher_account_id, content_norm, q_type_str
            )
            if existing:
                skipped.append(
                    {
                        "row": row_num,
                        "sheet": sheet,
                        "content": row_data["content"][:120],
                        "reason": f"Soal sudah ada di bank soal Anda (ID #{existing.id}). Dilewati.",
                    }
                )
            else:
                new_rows.append(row_data)

        if not new_rows:
            return True, [], [], skipped

        try:
            savepoint = db.begin_nested()
            created: list = []
            for row_data in new_rows:
                q = Question(
                    owner_teacher_account_id=teacher_account_id,
                    type=row_data["_qt"],
                    content=row_data["content"],
                    options=row_data["_final_options"],
                    answer_key=row_data["answer_key"],
                    rubrics=row_data["_final_rubrics"],
                    subject=subject,
                    class_level=row_data.get("class_level"),
                    ai_grading=row_data.get("ai_grading", False),
                )
                db.add(q)
                created.append(q)
            db.flush()
            savepoint.commit()
            return True, created, [], skipped
        except Exception as exc:
            try:
                savepoint.rollback()
            except Exception:
                pass
            db.rollback()
            raise exc
