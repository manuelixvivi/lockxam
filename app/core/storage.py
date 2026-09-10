"""EquiGrade Cloud & Persistent Object Storage Service (Vercel / S3 / Local).

Provides unified storage abstraction for teacher uploads (question images, diagrams, attachments).
Supports:
- Local filesystem storage (development/standard Docker servers)
- Cloud Object Storage (S3 / Cloudflare R2 / MinIO)
- Serverless-resilient Data URLs (ephemeral Vercel fallback)
"""

import base64
import mimetypes
import os
import uuid
from typing import Dict, Optional

from app.core.environment import is_production_environment, is_serverless_environment


class StorageService:
    @staticmethod
    def get_backend() -> str:
        """Returns the active storage backend."""
        is_production = is_production_environment()

        explicit = os.getenv("STORAGE_BACKEND", "").lower().strip()
        if explicit:
            if explicit == "s3":
                bucket = os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET_NAME")
                if not bucket and is_production:
                    raise RuntimeError(
                        "Production/Vercel deployment requires AWS_S3_BUCKET or S3_BUCKET_NAME when STORAGE_BACKEND=s3."
                    )
            elif is_production and explicit != "s3":
                raise RuntimeError(
                    f"Production/Vercel requires S3-compatible object storage (STORAGE_BACKEND=s3), got '{explicit}'."
                )
            return explicit

        if os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET_NAME"):
            return "s3"

        if is_production:
            raise RuntimeError(
                "Production/Vercel deployment requires S3-compatible object storage. "
                "Please configure STORAGE_BACKEND=s3 along with AWS_S3_BUCKET / S3_BUCKET_NAME."
            )

        return "local"

    @staticmethod
    def validate_image_bytes(content: bytes, ext: str) -> None:
        """Enforces magic byte checking to prevent polyglot / script injection attacks."""
        if not content or len(content) < 8:
            raise ValueError("File is empty or corrupted.")

        # Check standard image magic bytes
        if ext in (".jpg", ".jpeg"):
            if not content.startswith(b"\xff\xd8\xff"):
                raise ValueError("Invalid JPEG image signature.")
        elif ext == ".png":
            if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Invalid PNG image signature.")
        elif ext == ".webp":
            if not (content.startswith(b"RIFF") and b"WEBP" in content[:16]):
                raise ValueError("Invalid WEBP image signature.")
        elif ext == ".gif":
            if not (content.startswith(b"GIF87a") or content.startswith(b"GIF89a")):
                raise ValueError("Invalid GIF image signature.")
        else:
            raise ValueError(f"Format gambar '{ext}' tidak diizinkan.")

    @classmethod
    def save_file(
        cls,
        content: bytes,
        filename: str,
        content_type: Optional[str] = None,
        folder: str = "questions",
    ) -> Dict[str, str]:
        """Save file content and return URL and filename identifier."""
        backend = cls.get_backend()
        ext = os.path.splitext(filename)[1].lower()

        cls.validate_image_bytes(content, ext)

        if not content_type:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        unique_name = f"{folder}_{uuid.uuid4().hex}{ext}"

        if backend == "s3":
            # Cloud S3 / Cloudflare R2 Storage
            bucket = os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET_NAME")
            if not bucket:
                raise RuntimeError("Cloud Storage Error: S3_BUCKET_NAME is not configured.")

            endpoint = os.getenv("S3_ENDPOINT_URL")
            public_domain = os.getenv("S3_PUBLIC_DOMAIN")

            try:
                import boto3  # Optional boto3 import for S3

                s3_client = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    region_name=os.getenv("AWS_REGION", "us-east-1"),
                )
                key = f"uploads/{folder}/{unique_name}"
                s3_client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType=content_type,
                )
                if public_domain:
                    url = f"https://{public_domain}/{key}"
                else:
                    url = f"https://{bucket}.s3.amazonaws.com/{key}"
                return {"url": url, "filename": unique_name, "backend": "s3"}
            except Exception as s3_err:
                raise RuntimeError(f"Cloud S3 Object Storage Error: {s3_err}")

        if backend == "data_url":
            # Serverless fallback data URL for ephemeral testing
            b64_data = base64.b64encode(content).decode("utf-8")
            url = f"data:{content_type};base64,{b64_data}"
            return {"url": url, "filename": unique_name, "backend": "data_url"}

        # Default: Local filesystem
        target_dir = os.path.join("uploads", folder)
        try:
            os.makedirs(target_dir, exist_ok=True)
            file_path = os.path.join(target_dir, unique_name)
            with open(file_path, "wb") as f:
                f.write(content)
            url = f"/uploads/{folder}/{unique_name}"
            return {"url": url, "filename": unique_name, "backend": "local"}
        except Exception as local_err:
            raise RuntimeError(f"Local Storage Error: {local_err}")


storage_service = StorageService()
