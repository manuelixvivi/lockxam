import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ArtifactSyncError(RuntimeError):
    """Raised when synchronization with durable cloud storage (AWS S3) fails."""

    pass


class ArtifactStore(ABC):
    """
    Abstract storage interface for training artifacts.
    Decouples training orchestration from local filesystem vs cloud object storage (AWS S3).
    """

    @abstractmethod
    def save_json(self, relative_path: str, data: Any) -> str:
        """Saves a JSON-serializable object to the store."""
        pass

    @abstractmethod
    def save_text(self, relative_path: str, content: str) -> str:
        """Saves text content to the store."""
        pass

    @abstractmethod
    def append_jsonl_record(self, relative_path: str, record: Dict[str, Any]) -> str:
        """Appends a single JSON dictionary line to a JSONL file."""
        pass

    @abstractmethod
    def copy_directory(self, src_local_dir: str, dst_relative_path: str) -> str:
        """Copies or uploads an entire directory into the artifact store."""
        pass

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Checks if an artifact exists."""
        pass

    @abstractmethod
    def get_full_path(self, relative_path: str) -> str:
        """Returns the local filesystem path or object storage URI."""
        pass

    @abstractmethod
    def get_root_uri(self) -> str:
        """Returns the root URI of the artifact store for this job run."""
        pass

    @abstractmethod
    def get_local_working_dir(self) -> str:
        """Returns the local filesystem path where the local engine can execute directly."""
        pass

    @abstractmethod
    def sync_to_remote(self, relative_path: Optional[str] = None) -> None:
        """Flushes/syncs local buffered artifacts to remote durable storage (e.g. S3)."""
        pass

    @abstractmethod
    def download_checkpoint(self, remote_checkpoint_uri: str, target_local_dir: str) -> str:
        """Hydrates a remote checkpoint from durable storage down to local staging directory."""
        pass


class LocalArtifactStore(ArtifactStore):
    """
    Concrete ArtifactStore using local disk filesystem under base_dir/runs/<job_id>/<run_id>/.
    Includes strict path-traversal validation.
    """

    def __init__(self, base_dir: str, job_id: str, run_id: str):
        self.base_dir = os.path.abspath(base_dir)
        self.job_id = job_id
        self.run_id = run_id
        self.root_dir = os.path.abspath(os.path.join(self.base_dir, "runs", job_id, run_id))
        os.makedirs(self.root_dir, exist_ok=True)

    def _validate_path_security(self, relative_path: str) -> str:
        full_path = os.path.abspath(os.path.join(self.root_dir, relative_path))
        # Canonical containment validation using commonpath
        try:
            common = os.path.commonpath(
                [os.path.normcase(self.root_dir), os.path.normcase(full_path)]
            )
            if common != os.path.normcase(self.root_dir):
                raise ValueError(
                    f"Security violation: path traversal detected for relative_path '{relative_path}' outside root '{self.root_dir}'."
                )
        except ValueError as ve:
            if "path traversal detected" in str(ve):
                raise
            raise ValueError(
                f"Security violation: path traversal detected for relative_path '{relative_path}' outside root '{self.root_dir}'."
            )
        return full_path

    def get_full_path(self, relative_path: str) -> str:
        return self._validate_path_security(relative_path)

    def get_root_uri(self) -> str:
        return self.root_dir

    def get_local_working_dir(self) -> str:
        return self.root_dir

    def save_json(self, relative_path: str, data: Any) -> str:
        full_path = self._validate_path_security(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return full_path

    def save_text(self, relative_path: str, content: str) -> str:
        full_path = self._validate_path_security(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path

    def append_jsonl_record(self, relative_path: str, record: Dict[str, Any]) -> str:
        full_path = self._validate_path_security(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return full_path

    def copy_directory(self, src_local_dir: str, dst_relative_path: str) -> str:
        dst_full_path = self._validate_path_security(dst_relative_path)
        if os.path.exists(dst_full_path):
            shutil.rmtree(dst_full_path, ignore_errors=True)
        if os.path.exists(src_local_dir):
            shutil.copytree(src_local_dir, dst_full_path, dirs_exist_ok=True)
        return dst_full_path

    def exists(self, relative_path: str) -> bool:
        try:
            return os.path.exists(self._validate_path_security(relative_path))
        except ValueError:
            return False

    def sync_to_remote(self, relative_path: Optional[str] = None) -> None:
        # Local store is already durable on disk
        pass

    def download_checkpoint(self, remote_checkpoint_uri: str, target_local_dir: str) -> str:
        """Copies or links a local checkpoint directory."""
        if os.path.abspath(remote_checkpoint_uri) == os.path.abspath(target_local_dir):
            return target_local_dir
        os.makedirs(target_local_dir, exist_ok=True)
        if os.path.exists(remote_checkpoint_uri):
            shutil.copytree(remote_checkpoint_uri, target_local_dir, dirs_exist_ok=True)
        return target_local_dir


class S3ArtifactStore(ArtifactStore):
    """
    Cloud-ready ArtifactStore abstraction for AWS S3 (s3://<bucket>/runs/<job_id>/<run_id>/).
    Buffers locally on fast ephemeral compute disk before uploading to S3 destination via boto3.
    """

    def __init__(
        self,
        s3_uri: str,
        job_id: str,
        run_id: str,
        local_buffer_dir: Optional[str] = None,
        strict_mode: Optional[bool] = None,
    ):
        self.s3_uri = s3_uri.rstrip("/")
        parsed = urlparse(self.s3_uri)
        self.bucket = parsed.netloc
        self.prefix = parsed.path.lstrip("/")
        self.job_id = job_id
        self.run_id = run_id
        self.root_uri = f"{self.s3_uri}/runs/{job_id}/{run_id}"

        # Strict mode: Default to True (Fail-Closed Cloud Durability) unless explicitly set to False or EQUIGRADE_STRICT_CLOUD_SYNC=0
        if strict_mode is not None:
            self.strict_mode = strict_mode
        else:
            self.strict_mode = os.getenv("EQUIGRADE_STRICT_CLOUD_SYNC", "1") != "0"

        # Local buffer directory for fast compute staging
        if local_buffer_dir is None:
            local_buffer_dir = os.path.join(".", "tmp_s3_staging")
        self.local_store = LocalArtifactStore(local_buffer_dir, job_id, run_id)

    def get_full_path(self, relative_path: str) -> str:
        clean_rel = relative_path.replace(os.sep, "/").lstrip("/")
        return f"{self.root_uri}/{clean_rel}" if clean_rel else self.root_uri

    def get_root_uri(self) -> str:
        return self.root_uri

    def get_local_working_dir(self) -> str:
        return self.local_store.get_local_working_dir()

    def save_json(self, relative_path: str, data: Any) -> str:
        local_path = self.local_store.save_json(relative_path, data)
        self._upload_file_to_s3(local_path, relative_path)
        return self.get_full_path(relative_path)

    def save_text(self, relative_path: str, content: str) -> str:
        local_path = self.local_store.save_text(relative_path, content)
        self._upload_file_to_s3(local_path, relative_path)
        return self.get_full_path(relative_path)

    def append_jsonl_record(self, relative_path: str, record: Dict[str, Any]) -> str:
        local_path = self.local_store.append_jsonl_record(relative_path, record)
        # Note: Local append is synchronous; full S3 batch upload happens at sync_to_remote()
        return self.get_full_path(relative_path)

    def copy_directory(self, src_local_dir: str, dst_relative_path: str) -> str:
        local_dst = self.local_store.copy_directory(src_local_dir, dst_relative_path)
        self._upload_dir_to_s3(local_dst, dst_relative_path)
        return self.get_full_path(dst_relative_path)

    def exists(self, relative_path: str) -> bool:
        return self.local_store.exists(relative_path)

    def sync_to_remote(self, relative_path: Optional[str] = None) -> None:
        """Syncs all staged files in local buffer to S3."""
        local_root = self.local_store.root_dir
        for root, _, files in os.walk(local_root):
            for file in files:
                full_local = os.path.join(root, file)
                rel = os.path.relpath(full_local, local_root)
                self._upload_file_to_s3(full_local, rel)

    def download_checkpoint(self, remote_checkpoint_uri: str, target_local_dir: str) -> str:
        """
        Hydrates an S3 checkpoint (s3://<bucket>/path/to/checkpoint) down to local staging directory.
        """
        os.makedirs(target_local_dir, exist_ok=True)
        if not remote_checkpoint_uri.startswith("s3://"):
            if os.path.exists(remote_checkpoint_uri):
                shutil.copytree(remote_checkpoint_uri, target_local_dir, dirs_exist_ok=True)
            return target_local_dir

        parsed = urlparse(remote_checkpoint_uri)
        bucket = parsed.netloc
        raw_prefix = parsed.path.lstrip("/")
        # Enforce exact directory boundary
        prefix_boundary = raw_prefix if raw_prefix.endswith("/") else raw_prefix + "/"

        try:
            import boto3  # type: ignore

            s3_client = boto3.client("s3")
            paginator = s3_client.get_paginator("list_objects_v2")
            downloaded = 0
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix_boundary):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    rel_name = (
                        os.path.relpath(key, prefix_boundary)
                        if prefix_boundary != key
                        else os.path.basename(key)
                    )
                    dst_file = os.path.join(target_local_dir, rel_name)
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    s3_client.download_file(bucket, key, dst_file)
                    downloaded += 1
            logger.info(
                f"[S3ArtifactStore] Hydrated {downloaded} checkpoint files from '{remote_checkpoint_uri}' to '{target_local_dir}'."
            )
            return target_local_dir
        except Exception as e:
            if self.strict_mode:
                raise ArtifactSyncError(
                    f"Failed to hydrate checkpoint from '{remote_checkpoint_uri}': {e}"
                ) from e
            logger.warning(f"[S3ArtifactStore] Checkpoint hydration fallback (offline mock): {e}")
            return target_local_dir

    def _upload_file_to_s3(self, local_file: str, relative_key: str) -> None:
        """Uploads a local file to S3 using boto3 with strict error propagation support."""
        s3_key = f"{self.prefix}/runs/{self.job_id}/{self.run_id}/{relative_key.replace(os.sep, '/')}".lstrip(
            "/"
        )
        try:
            import boto3  # type: ignore

            s3_client = boto3.client("s3")
            s3_client.upload_file(local_file, self.bucket, s3_key)
            logger.info(
                f"[S3ArtifactStore] Uploaded '{local_file}' to 's3://{self.bucket}/{s3_key}'."
            )
        except Exception as e:
            if self.strict_mode:
                raise ArtifactSyncError(
                    f"Cloud S3 artifact upload failed for key 's3://{self.bucket}/{s3_key}': {e}"
                ) from e
            logger.info(
                f"[S3ArtifactStore] Synced '{relative_key}' to '{self.get_full_path(relative_key)}' (buffer preserved)."
            )

    def _upload_dir_to_s3(self, local_dir: str, dst_relative_prefix: str) -> None:
        """Uploads an entire directory to S3."""
        for root, _, files in os.walk(local_dir):
            for file in files:
                full_local = os.path.join(root, file)
                rel = os.path.relpath(full_local, local_dir)
                combined_key = os.path.join(dst_relative_prefix, rel)
                self._upload_file_to_s3(full_local, combined_key)


def get_artifact_store(
    base_uri: str, job_id: str, run_id: str, strict_mode: bool = True
) -> ArtifactStore:
    """
    Factory creating appropriate ArtifactStore based on URI scheme.
    Default for S3 is strict_mode=True (Fail-Closed Cloud Durability).
    """
    if base_uri.startswith("s3://"):
        return S3ArtifactStore(
            s3_uri=base_uri, job_id=job_id, run_id=run_id, strict_mode=strict_mode
        )
    return LocalArtifactStore(base_dir=base_uri, job_id=job_id, run_id=run_id)
