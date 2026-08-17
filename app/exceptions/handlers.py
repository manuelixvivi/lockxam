from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.exceptions.base import AcademicValidationException, AppException, LicenseExpiredException
from app.logging.logger import logger


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request, exc: IntegrityError):
        error_msg = str(exc.orig) if exc.orig else str(exc)
        logger.error(f"Database IntegrityError: {error_msg}")

        # Parse unique key violations to inform the user exactly what is conflicting
        if "unique constraint" in error_msg.lower() or "duplicate key" in error_msg.lower():
            if "schools_npsn" in error_msg:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "NPSN sudah terdaftar di sistem. Gunakan NPSN lain."},
                )
            if "schools_domain" in error_msg:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Domain sudah digunakan sekolah lain. Gunakan domain lain."},
                )
            if "schools_code" in error_msg:
                return JSONResponse(
                    status_code=400, content={"detail": "Kode Sekolah sudah terdaftar di sistem."}
                )
            if "student_answers" in error_msg or "uq_attempt_question" in error_msg:
                return JSONResponse(
                    status_code=400, content={"detail": "Jawaban untuk soal ini sudah tersimpan."}
                )

            # Regex fallback to extract conflicting column and value
            import re

            match = re.search(r"Key \((.*?)\)=\((.*?)\) already exists", error_msg)
            if match:
                field, val = match.groups()
                field_translate = {
                    "npsn": "NPSN",
                    "domain": "Domain",
                    "code": "Kode Sekolah",
                    "username": "Username/Email",
                    "email": "Email",
                }
                field_name = field_translate.get(field.lower(), field)
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Data bentrok: Nilai '{val}' pada kolom {field_name} sudah terdaftar di sistem."
                    },
                )

            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Data yang Anda masukkan bentrok dengan data yang sudah ada di sistem."
                },
            )

        return JSONResponse(
            status_code=500, content={"detail": "Terjadi kesalahan integritas data pada server."}
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request, exc: AppException):
        logger.warning(f"AppException handled: {exc.message} (status_code={exc.status_code})")
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(LicenseExpiredException)
    async def license_expired_handler(request, exc: LicenseExpiredException):
        logger.warning(f"LicenseExpiredException handled: {exc.message}")
        return JSONResponse(
            status_code=403, content={"error": {"code": "LICENSE_EXPIRED", "message": exc.message}}
        )

    @app.exception_handler(AcademicValidationException)
    async def academic_validation_handler(request, exc: AcademicValidationException):
        logger.warning(f"AcademicValidationException handled: {exc.message}")
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "ACADEMIC_CLOSING_CHECKLIST_FAILED",
                    "message": exc.message,
                    "infractions": exc.errors,
                }
            },
        )
