import json
import logging
import os
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.repositories.ai.dataset_version_repository import dataset_version_repository

logger = logging.getLogger(__name__)


class DatasetLoader:
    """
    Milestone A9.1: Dataset Loader for Fine-Tuning.
    Retrieves immutable frozen SFT split payloads from DatasetVersion (A8)
    and enforces cryptographic SHA-256 fingerprint verification prior to training consumption.
    """

    @classmethod
    def load_from_database(
        cls, db: Session, version_tag: str, verify_hash: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Loads frozen dataset split payloads from the database.
        Optionally verifies cryptographic dataset_hash and manifest_hash.
        """
        dv = dataset_version_repository.get_by_version_tag(db, version_tag)
        if not dv:
            raise ValueError(f"DatasetVersion with tag '{version_tag}' not found.")

        payloads = dv.frozen_split_payloads or {}

        if verify_hash:
            # Deterministic SHA-256 validation over frozen split payloads matching A8 canonicalization
            canonical_payload_json = json.dumps(payloads, sort_keys=True)
            import hashlib

            computed_dataset_hash = hashlib.sha256(
                canonical_payload_json.encode("utf-8")
            ).hexdigest()

            if computed_dataset_hash != dv.dataset_hash:
                raise ValueError(
                    f"Cryptographic dataset integrity error: computed hash {computed_dataset_hash} "
                    f"does not match registered dataset_hash {dv.dataset_hash}."
                )

            # Deterministic manifest hash validation
            manifest_json = json.dumps(dv.split_manifest or {}, sort_keys=True)
            computed_manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

            if computed_manifest_hash != dv.manifest_hash:
                raise ValueError(
                    f"Cryptographic manifest integrity error: computed hash {computed_manifest_hash} "
                    f"does not match registered manifest_hash {dv.manifest_hash}."
                )

        logger.info(
            f"Successfully loaded and verified DatasetVersion '{version_tag}' "
            f"(Total samples: {dv.total_samples}, Dataset Hash: {dv.dataset_hash[:8]}...)"
        )
        return payloads

    @classmethod
    def load_from_jsonl(cls, filepath: str) -> List[Dict[str, Any]]:
        """
        Loads records from a single JSONL file on disk.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Dataset file '{filepath}' does not exist.")

        records = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    records.append(json.loads(clean_line))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Malformed JSON on line {line_idx} of {filepath}: {e}")

        return records

    @classmethod
    def export_splits_to_jsonl(
        cls, db: Session, version_tag: str, output_dir: str
    ) -> Dict[str, str]:
        """
        Exports all frozen dataset splits and a verified metadata manifest to disk.
        Returns a dictionary mapping split names to written file paths.
        """
        dv = dataset_version_repository.get_by_version_tag(db, version_tag)
        if not dv:
            raise ValueError(f"DatasetVersion '{version_tag}' not found.")

        os.makedirs(output_dir, exist_ok=True)
        split_payloads = cls.load_from_database(db, version_tag, verify_hash=True)
        written_files = {}

        for split_name, items in split_payloads.items():
            out_file = os.path.join(output_dir, f"{split_name}.jsonl")
            with open(out_file, "w", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            written_files[split_name] = out_file

        # Write manifest file
        manifest_path = os.path.join(output_dir, "dataset_manifest.json")
        manifest_data = {
            "version_tag": dv.version_tag,
            "task_type": dv.task_type,
            "split_strategy": dv.split_strategy,
            "dataset_hash": dv.dataset_hash,
            "manifest_hash": dv.manifest_hash,
            "total_samples": dv.total_samples,
            "train_count": dv.train_count,
            "val_count": dv.val_count,
            "test_count": dv.test_count,
            "split_manifest": dv.split_manifest,
            "school_id": dv.school_id,
            "academic_year_id": dv.academic_year_id,
            "created_by_user_id": dv.created_by_user_id,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)

        written_files["manifest"] = manifest_path
        return written_files
