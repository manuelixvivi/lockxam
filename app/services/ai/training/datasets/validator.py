import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.repositories.ai.dataset_version_repository import dataset_version_repository
from app.services.ai.training.datasets.formatter import SftFormatter
from app.services.ai.training.datasets.loader import DatasetLoader
from app.services.ai.training.schemas import ValidationReport
from app.services.ai.training.tokenization.tokenization_config import TokenizationConfig
from app.services.ai.training.tokenization.tokenizer_service import TokenizerService

logger = logging.getLogger(__name__)


class TrainingPreflightError(Exception):
    """
    Raised when a DatasetVersion fails pre-flight scientific or structural validation
    before training execution can begin.
    """

    def __init__(self, report: ValidationReport):
        self.report = report
        errors_summary = "; ".join(report.validation_errors)
        super().__init__(
            f"Training pre-flight gate rejected DatasetVersion '{report.dataset_version}': {errors_summary}"
        )


class DatasetValidator:
    """
    Milestone A9.1: Comprehensive SFT Dataset Validator.
    Performs pre-flight scientific validation over a DatasetVersion before SFT / LoRA / QLoRA training:
    - Cryptographic identity verification (SHA-256)
    - Split set candidate ID disjunction
    - Semantic question-group key disjunction (Zero-Leakage Invariant)
    - Structural field completeness
    - Score and normalization numerical bounds
    - Target truncation protection & truncation rate policy enforcement
    """

    @classmethod
    def validate_dataset_version(
        cls,
        db: Session,
        version_tag: str,
        token_config: Optional[TokenizationConfig] = None,
    ) -> ValidationReport:
        """
        Executes complete pre-flight validation checks on a DatasetVersion release.
        """
        dv = dataset_version_repository.get_by_version_tag(db, version_tag)
        if not dv:
            raise ValueError(f"DatasetVersion with version_tag '{version_tag}' was not found.")

        validation_errors: List[str] = []
        is_valid = True

        # 1. Cryptographic Hash Verification
        try:
            split_payloads = DatasetLoader.load_from_database(db, version_tag, verify_hash=True)
        except Exception as e:
            validation_errors.append(f"Cryptographic hash check failed: {e}")
            split_payloads = dv.frozen_split_payloads or {}
            is_valid = False

        # 2. Split Disjunction (Candidate IDs)
        manifest = dv.split_manifest or {}
        train_ids = set(manifest.get("train", []))
        val_ids = set(manifest.get("val", []))
        test_ids = set(manifest.get("test", []))

        disjoint_passed = (
            train_ids.isdisjoint(val_ids)
            and train_ids.isdisjoint(test_ids)
            and val_ids.isdisjoint(test_ids)
        )

        if not disjoint_passed:
            validation_errors.append(
                "Data leakage detected: Candidate IDs between train, val, and test partitions are not mutually disjoint!"
            )
            is_valid = False

        # 3. Semantic Question-Group Disjunction Check
        train_groups: Set[str] = set()
        val_groups: Set[str] = set()
        test_groups: Set[str] = set()

        def extract_group_keys(items: List[Dict[str, Any]]) -> Set[str]:
            keys = set()
            for it in items:
                gk = it.get("question_group_key")
                if not gk:
                    # Fallback to normalized question text as group signature
                    q_text = it.get("question", "").strip().lower()
                    if q_text:
                        gk = q_text
                if gk:
                    keys.add(gk)
            return keys

        train_groups = extract_group_keys(split_payloads.get("train", []))
        val_groups = extract_group_keys(split_payloads.get("val", []))
        test_groups = extract_group_keys(split_payloads.get("test", []))

        group_disjoint_passed = (
            train_groups.isdisjoint(val_groups)
            and train_groups.isdisjoint(test_groups)
            and val_groups.isdisjoint(test_groups)
        )

        is_group_split_strategy = (
            dv.split_strategy == "QUESTION_GROUP_SPLIT" or dv.split_strategy is None
        )

        if not group_disjoint_passed and is_group_split_strategy:
            leak_train_val = train_groups.intersection(val_groups)
            leak_train_test = train_groups.intersection(test_groups)
            leak_val_test = val_groups.intersection(test_groups)
            all_leaks = leak_train_val | leak_train_test | leak_val_test
            validation_errors.append(
                f"Semantic data leakage detected for QUESTION_GROUP_SPLIT: Question group keys overlap across splits ({list(all_leaks)[:3]}...)"
            )
            is_valid = False
        elif not group_disjoint_passed and dv.split_strategy == "TEMPORAL_SPLIT":
            logger.info(
                f"Temporal generalization notice: Question group overlap across time periods preserved for '{version_tag}'."
            )

        split_counts = {
            "train": len(split_payloads.get("train", [])),
            "val": len(split_payloads.get("val", [])),
            "test": len(split_payloads.get("test", [])),
        }

        if split_counts["train"] == 0:
            validation_errors.append("Validation failed: Train split contains 0 samples.")
            is_valid = False

        # 4. Structural Field & Score Bounds Validation
        missing_fields_count = 0
        score_bounds_passed = True

        for split_name, items in split_payloads.items():
            for idx, item in enumerate(items):
                # Required top-level fields
                for field in ("question", "student_answer", "target"):
                    if not item.get(field):
                        missing_fields_count += 1
                        validation_errors.append(
                            f"Split '{split_name}' sample #{idx} is missing required field '{field}'"
                        )
                        is_valid = False

                target = item.get("target", {})
                if not isinstance(target, dict):
                    validation_errors.append(
                        f"Split '{split_name}' sample #{idx} target is not a dictionary"
                    )
                    score_bounds_passed = False
                    is_valid = False
                    continue

                # Score bounds check
                score = target.get("score")
                max_score = float(item.get("max_score", 10.0))
                if score is None or not (0.0 <= float(score) <= max_score):
                    score_bounds_passed = False
                    validation_errors.append(
                        f"Split '{split_name}' sample #{idx} score {score} out of bounds [0.0, {max_score}]"
                    )
                    is_valid = False

                # Feedback check
                feedback = target.get("feedback")
                if not feedback or not str(feedback).strip():
                    validation_errors.append(
                        f"Split '{split_name}' sample #{idx} has empty or whitespace feedback"
                    )
                    is_valid = False

        # 5. Tokenization Distribution & Target Truncation Analytics
        if token_config is None:
            token_config = TokenizationConfig()

        tokenization_summary: Dict[str, Any] = {}
        for split_name, raw_items in split_payloads.items():
            formatted_examples = SftFormatter.format_split(raw_items)
            stats = TokenizerService.compute_tokenization_stats(formatted_examples, token_config)
            tokenization_summary[split_name] = stats

            # Enforce Target Truncation Policy
            if token_config.fail_on_target_truncation and stats.target_truncated_count > 0:
                validation_errors.append(
                    f"Target truncation policy failure: Split '{split_name}' contains {stats.target_truncated_count} "
                    f"samples where assistant ground-truth completions were cut off by max_seq_length ({token_config.max_seq_length})."
                )
                is_valid = False

            # Enforce Maximum Truncation Rate Threshold
            if stats.truncation_rate_pct > token_config.max_truncation_rate_pct:
                validation_errors.append(
                    f"Truncation rate policy failure: Split '{split_name}' truncation rate {stats.truncation_rate_pct}% "
                    f"exceeds maximum allowed threshold {token_config.max_truncation_rate_pct}%."
                )
                is_valid = False

        return ValidationReport(
            is_valid=is_valid,
            dataset_version=dv.version_tag,
            dataset_hash=dv.dataset_hash,
            manifest_hash=dv.manifest_hash,
            total_samples=dv.total_samples,
            split_counts=split_counts,
            disjoint_check_passed=disjoint_passed,
            group_disjoint_passed=group_disjoint_passed,
            score_bounds_passed=score_bounds_passed,
            missing_fields_count=missing_fields_count,
            validation_errors=validation_errors,
            tokenization_summary=tokenization_summary,
        )

    @classmethod
    def assert_training_ready(
        cls,
        db: Session,
        version_tag: str,
        token_config: Optional[TokenizationConfig] = None,
    ) -> ValidationReport:
        """
        Executes validation and raises TrainingPreflightError if validation fails,
        acting as an uncompromising hard stop gate before training worker execution.
        """
        report = cls.validate_dataset_version(db, version_tag, token_config)
        if not report.is_valid:
            raise TrainingPreflightError(report)
        return report
