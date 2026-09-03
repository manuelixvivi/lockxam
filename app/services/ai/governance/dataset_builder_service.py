import hashlib
import json
import logging
import random
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.ai.dataset_version import DatasetVersion
from app.models.ai.training_candidate import TrainingCandidate
from app.repositories.ai.dataset_version_repository import dataset_version_repository
from app.repositories.ai.training_candidate_repository import training_candidate_repository

logger = logging.getLogger(__name__)


class DatasetBuilderService:
    """
    Milestone A8: Dataset Versioning & Group-Based Leakage-Free Split Engine.
    Builds immutable, cryptographically hashed training dataset releases from eligible
    TrainingCandidate records with frozen SFT snapshots for true byte-exact reproducibility.
    """

    ALLOWED_STRATEGIES: Set[str] = {"QUESTION_GROUP_SPLIT", "TEMPORAL_SPLIT"}

    @classmethod
    def build_dataset_version(
        cls,
        db: Session,
        version_tag: str,
        min_quality_score: float = 0.70,
        train_ratio: float = 0.80,
        val_ratio: float = 0.10,
        test_ratio: float = 0.10,
        split_strategy: str = "QUESTION_GROUP_SPLIT",
        subject_id: Optional[int] = None,
        school_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
        random_seed: int = 42,
    ) -> DatasetVersion:
        """
        Builds a new versioned dataset release with leakage-free group splitting and cryptographic identity.
        """
        # 1. Strategy & Ratio Invariant Verification
        if split_strategy not in cls.ALLOWED_STRATEGIES:
            raise ValueError(
                f"Unsupported split strategy '{split_strategy}'. "
                f"Allowed strategies are: {sorted(cls.ALLOWED_STRATEGIES)}."
            )

        if not (0.0 < train_ratio <= 1.0 and 0.0 <= val_ratio < 1.0 and 0.0 <= test_ratio < 1.0):
            raise ValueError("Split ratios must be non-negative and train_ratio must be positive.")

        if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-4:
            raise ValueError(
                f"Split ratios must sum to 1.0 (received sum: {train_ratio + val_ratio + test_ratio:.4f})."
            )

        # 2. Verify Version Tag Uniqueness
        existing = dataset_version_repository.get_by_version_tag(db, version_tag)
        if existing:
            raise ValueError(f"DatasetVersion with tag '{version_tag}' already exists.")

        # 3. Retrieve Eligible Candidates
        candidates = training_candidate_repository.get_eligible_candidates(
            db=db,
            min_quality_score=min_quality_score,
            subject_id=subject_id,
            school_id=school_id,
        )

        if academic_year_id is not None:
            candidates = [c for c in candidates if c.academic_year_id == academic_year_id]

        if not candidates:
            raise ValueError(
                f"No eligible training candidates found meeting quality threshold >= {min_quality_score}."
            )

        # 4. Group-Based Splitting Strategy (Zero Prompt Leakage)
        train_ids: List[int] = []
        val_ids: List[int] = []
        test_ids: List[int] = []

        if split_strategy == "QUESTION_GROUP_SPLIT":
            groups: Dict[str, List[int]] = {}
            for c in candidates:
                groups.setdefault(c.question_group_key, []).append(c.id)

            group_keys = list(groups.keys())
            rng = random.Random(random_seed)
            rng.shuffle(group_keys)

            n_groups = len(group_keys)
            if n_groups == 1:
                train_groups = set(group_keys)
                val_groups = set()
                test_groups = set()
            elif n_groups == 2:
                train_groups = {group_keys[0]}
                val_groups = set()
                test_groups = {group_keys[1]}
            else:
                n_train_g = max(1, int(n_groups * train_ratio))
                n_val_g = max(0, int(n_groups * val_ratio))
                if n_train_g + n_val_g >= n_groups:
                    n_train_g = max(1, n_groups - 2)
                    n_val_g = 1

                train_groups = set(group_keys[:n_train_g])
                val_groups = set(group_keys[n_train_g : n_train_g + n_val_g])
                test_groups = set(group_keys[n_train_g + n_val_g :])

                if not test_groups and val_groups:
                    test_groups = val_groups
                    val_groups = set()

            for g_key in train_groups:
                train_ids.extend(groups[g_key])
            for g_key in val_groups:
                val_ids.extend(groups[g_key])
            for g_key in test_groups:
                test_ids.extend(groups[g_key])

        elif split_strategy == "TEMPORAL_SPLIT":

            def get_assessment_time(c: TrainingCandidate):
                if c.assessment_history is not None and hasattr(c.assessment_history, "created_at"):
                    return c.assessment_history.created_at
                return c.created_at

            sorted_candidates = sorted(candidates, key=get_assessment_time)
            n_total = len(sorted_candidates)
            n_train = max(1, int(n_total * train_ratio))
            n_val = int(n_total * val_ratio)

            train_ids = [c.id for c in sorted_candidates[:n_train]]
            val_ids = [c.id for c in sorted_candidates[n_train : n_train + n_val]]
            test_ids = [c.id for c in sorted_candidates[n_train + n_val :]]

        # 5. Invariant Verification: Disjoint Split Sets
        set_train = set(train_ids)
        set_val = set(val_ids)
        set_test = set(test_ids)

        if not (
            set_train.isdisjoint(set_val)
            and set_train.isdisjoint(set_test)
            and set_val.isdisjoint(set_test)
        ):
            raise RuntimeError("Data leakage detected: Split candidate ID sets overlap!")

        all_candidate_ids = train_ids + val_ids + test_ids

        # 6. Build True Immutable Frozen Payload Snapshots
        cand_map = {c.id: c.formatted_sft_payload for c in candidates}
        frozen_payloads: Dict[str, List[Dict[str, Any]]] = {
            "train": [cand_map[cid] for cid in train_ids if cid in cand_map],
            "val": [cand_map[cid] for cid in val_ids if cid in cand_map],
            "test": [cand_map[cid] for cid in test_ids if cid in cand_map],
        }

        # 7. Cryptographic Dataset Identity (SHA-256)
        canonical_payload_json = json.dumps(frozen_payloads, sort_keys=True)
        dataset_hash = hashlib.sha256(canonical_payload_json.encode("utf-8")).hexdigest()

        split_manifest_dict = {
            "train": train_ids,
            "val": val_ids,
            "test": test_ids,
        }
        manifest_hash = hashlib.sha256(
            json.dumps(split_manifest_dict, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # 8. Statistical Summary
        subjects_dist: Dict[str, int] = {}
        classes_dist: Dict[str, int] = {}
        for c in candidates:
            if c.id in set(all_candidate_ids):
                subjects_dist[c.subject_name] = subjects_dist.get(c.subject_name, 0) + 1
                classes_dist[c.class_level] = classes_dist.get(c.class_level, 0) + 1

        metadata = {
            "random_seed": random_seed,
            "min_quality_score": min_quality_score,
            "subjects_distribution": subjects_dist,
            "classes_distribution": classes_dist,
            "average_quality_score": round(
                sum(c.quality_score for c in candidates) / len(candidates), 3
            ),
        }

        # 9. Create and Persist DatasetVersion
        dataset_version = DatasetVersion(
            version_tag=version_tag,
            task_type="ESSAY_GRADING",
            split_strategy=split_strategy,
            dataset_hash=dataset_hash,
            manifest_hash=manifest_hash,
            total_samples=len(all_candidate_ids),
            train_count=len(train_ids),
            val_count=len(val_ids),
            test_count=len(test_ids),
            quality_threshold_applied=min_quality_score,
            split_manifest=split_manifest_dict,
            candidate_ids=all_candidate_ids,
            frozen_split_payloads=frozen_payloads,
            school_id=school_id,
            academic_year_id=academic_year_id,
            created_by_user_id=created_by_user_id,
            metadata_json=metadata,
        )

        dataset_version_repository.create(db, dataset_version)
        db.commit()
        db.refresh(dataset_version)
        return dataset_version

    @classmethod
    def export_dataset_split(
        cls, db: Session, version_tag: str, split_name: str = "train"
    ) -> List[Dict[str, Any]]:
        """
        Exports frozen JSONL training payload objects directly from immutable snapshot.
        Guarantees byte-exact reproducibility across exports.
        """
        dv = dataset_version_repository.get_by_version_tag(db, version_tag)
        if not dv:
            raise ValueError(f"DatasetVersion '{version_tag}' not found.")

        if split_name not in ["train", "val", "test"]:
            raise ValueError(
                f"Invalid split name '{split_name}'. Must be 'train', 'val', or 'test'."
            )

        return dv.frozen_split_payloads.get(split_name, [])
