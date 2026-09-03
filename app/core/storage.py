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


class StorageService:
    @staticmethod
    def get_backend() -> str:
        """Returns the active storage backend."""
        explicit = os.getenv("STORAGE_BACKEND", "").lower().strip()
        if explicit:
            return explicit
        if os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET_NAME"):
            return "s3"
        if os.getenv("VERCEL") or os.getenv("SERVERLESS"):
            return "data_url"
        return "local"

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
        if not content_type:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        unique_name = f"{folder}_{uuid.uuid4().hex}{ext}"

        if backend == "s3":
            # Cloud S3 / Cloudflare R2 Storage
            bucket = os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET_NAME")
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
                    ACL="public-read",
                )
                if public_domain:
                    url = f"https://{public_domain}/{key}"
                else:
                    url = f"https://{bucket}.s3.amazonaws.com/{key}"
                return {"url": url, "filename": unique_name, "backend": "s3"}
            except Exception as s3_err:
                print(f"S3 upload error, falling back to data_url: {s3_err}")
                backend = "data_url"

        if backend == "data_url":
            # Serverless persistent data URL (100% resilient across lambda cold starts)
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
        except Exception:
            # If filesystem is read-only (like Vercel production), fallback to data_url
            b64_data = base64.b64encode(content).decode("utf-8")
            url = f"data:{content_type};base64,{b64_data}"
            return {"url": url, "filename": unique_name, "backend": "data_url"}


storage_service = StorageService()
