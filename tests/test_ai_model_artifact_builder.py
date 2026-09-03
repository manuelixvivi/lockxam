import json
import os
import tempfile

import pytest

from app.services.ai.training.registry.artifact_builder import ModelArtifactBuilder


def create_sample_adapter_directory(base_dir: str) -> str:
    """Helper creating a standard realistic PEFT LoRA adapter directory structure."""
    adapter_dir = os.path.join(base_dir, "adapter_artifact")
    os.makedirs(adapter_dir, exist_ok=True)

    # 1. adapter_config.json
    with open(os.path.join(adapter_dir, "adapter_config.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "base_model_name_or_path": "meta-llama/Llama-3.1-8B-Instruct",
                "lora_alpha": 32,
                "lora_dropout": 0.05,
                "r": 16,
                "target_modules": ["q_proj", "v_proj"],
                "peft_type": "LORA",
            },
            f,
            indent=2,
        )

    # 2. adapter_model.safetensors (mock binary weights)
    with open(os.path.join(adapter_dir, "adapter_model.safetensors"), "wb") as f:
        f.write(b"MOCK_SAFETENSORS_TENSORS_WEIGHTS_BINARY_BLOB_FOR_TESTING_1234567890")

    # 3. special_tokens_map.json
    with open(os.path.join(adapter_dir, "special_tokens_map.json"), "w", encoding="utf-8") as f:
        json.dump({"pad_token": "<|finetune_pad|>"}, f)

    # 4. tokenizer_config.json
    with open(os.path.join(adapter_dir, "tokenizer_config.json"), "w", encoding="utf-8") as f:
        json.dump({"model_max_length": 2048, "tokenizer_class": "PreTrainedTokenizerFast"}, f)

    # 5. Nested subfolder file
    nested_dir = os.path.join(adapter_dir, "submodules", "head")
    os.makedirs(nested_dir, exist_ok=True)
    with open(os.path.join(nested_dir, "head_config.json"), "w", encoding="utf-8") as f:
        json.dump({"head_dim": 128}, f)

    return adapter_dir


# ==============================================================================
# 1. DETERMINISTIC TREE HASHING & PATH NORMALIZATION
# ==============================================================================


def test_scan_and_hash_directory_produces_deterministic_merkle_tree_hash():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)

        # First hash calculation
        records1, merkle_hash1, adapter_hash1 = ModelArtifactBuilder.scan_and_hash_directory(
            adapter_dir
        )

        # Second hash calculation on identical directory
        records2, merkle_hash2, adapter_hash2 = ModelArtifactBuilder.scan_and_hash_directory(
            adapter_dir
        )

        assert merkle_hash1 == merkle_hash2
        assert adapter_hash1 == adapter_hash2
        assert len(records1) == len(records2) == 5
        assert [r.relative_path for r in records1] == [r.relative_path for r in records2]
        assert [r.sha256_hash for r in records1] == [r.sha256_hash for r in records2]


def test_path_normalization_uses_forward_slashes_cross_platform():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)

        records, _, _ = ModelArtifactBuilder.scan_and_hash_directory(adapter_dir)

        # Verify all relative paths use canonical forward slash '/' regardless of OS (Windows / POSIX)
        rel_paths = [r.relative_path for r in records]
        assert "submodules/head/head_config.json" in rel_paths
        for p in rel_paths:
            assert "\\" not in p


# ==============================================================================
# 2. OS AND TRANSIENT NOISE EXCLUSION
# ==============================================================================


def test_exclusion_of_os_and_transient_noise():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)

        # Compute clean baseline hash
        _, clean_hash, _ = ModelArtifactBuilder.scan_and_hash_directory(adapter_dir)

        # Inject OS/transient noise files
        with open(os.path.join(adapter_dir, ".DS_Store"), "wb") as f:
            f.write(b"APPLE_METADATA_NOISE")
        with open(os.path.join(adapter_dir, "Thumbs.db"), "wb") as f:
            f.write(b"WINDOWS_THUMBNAIL_CACHE")
        with open(os.path.join(adapter_dir, "temp_scratch.tmp"), "wb") as f:
            f.write(b"TEMP_SCRATCH")

        pycache_dir = os.path.join(adapter_dir, "__pycache__")
        os.makedirs(pycache_dir, exist_ok=True)
        with open(os.path.join(pycache_dir, "module.cpython-312.pyc"), "wb") as f:
            f.write(b"BYTECODE_NOISE")

        # Re-compute hash on polluted directory
        records, polluted_hash, _ = ModelArtifactBuilder.scan_and_hash_directory(adapter_dir)

        # Hash and records count must be identical to clean baseline
        assert polluted_hash == clean_hash
        assert len(records) == 5
        assert ".DS_Store" not in [r.relative_path for r in records]
        assert "Thumbs.db" not in [r.relative_path for r in records]


# ==============================================================================
# 3. MANIFEST GENERATION & SERIALIZATION
# ==============================================================================


def test_model_manifest_building_and_saving():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)

        manifest = ModelArtifactBuilder.build_manifest(
            model_name="equigrade-essay-grader",
            version="v1",
            version_number=1,
            training_job_id="job_abc123",
            training_run_id="run_xyz789",
            experiment_id="E2_FineTuned_Base",
            dataset_version_tag="v1.0.0-train",
            dataset_hash="sha256:dset123456",
            base_model_name="meta-llama/Llama-3.1-8B-Instruct",
            base_model_revision="main",
            tokenizer_name_or_path="meta-llama/Llama-3.1-8B-Instruct",
            adapter_type="LORA",
            artifact_dir=adapter_dir,
            artifact_uri="s3://equigrade-models/runs/job_abc123/run_xyz789/adapter",
            metadata={"domain": "biology", "accuracy": 0.94},
        )

        assert manifest.model_name == "equigrade-essay-grader"
        assert manifest.version == "v1"
        assert manifest.version_number == 1
        assert manifest.artifact_manifest_hash.startswith("sha256:")
        assert len(manifest.file_manifest) == 5

        # Save manifest into artifact dir
        manifest_file = ModelArtifactBuilder.save_manifest_to_artifact_dir(manifest, adapter_dir)
        assert os.path.exists(manifest_file)

        # Verify saving manifest doesn't mutate Merkle tree hash (model_manifest.json is excluded)
        _, recomputed_hash, _ = ModelArtifactBuilder.scan_and_hash_directory(adapter_dir)
        assert recomputed_hash == manifest.artifact_manifest_hash


# ==============================================================================
# 4. CRYPTOGRAPHIC INTEGRITY & TAMPERING DETECTION
# ==============================================================================


def test_integrity_verification_happy_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)
        manifest = ModelArtifactBuilder.build_manifest(
            model_name="equigrade-model",
            version="v1",
            version_number=1,
            training_job_id="job_1",
            training_run_id="run_1",
            experiment_id="E2",
            dataset_version_tag="v1",
            dataset_hash="h1",
            base_model_name="base",
            base_model_revision="main",
            tokenizer_name_or_path="tok",
            adapter_type="LORA",
            artifact_dir=adapter_dir,
        )

        res = ModelArtifactBuilder.verify_artifact_integrity(
            artifact_dir=adapter_dir,
            expected_manifest_hash=manifest.artifact_manifest_hash,
            expected_file_manifest=manifest.file_manifest,
        )

        assert res.is_valid is True
        assert res.mismatched_files == []
        assert res.missing_files == []
        assert res.unauthorized_files == []
        assert res.total_files_checked == 5
        assert res.error_message is None


def test_integrity_verification_detects_byte_tampering():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)
        manifest = ModelArtifactBuilder.build_manifest(
            model_name="equigrade-model",
            version="v1",
            version_number=1,
            training_job_id="job_1",
            training_run_id="run_1",
            experiment_id="E2",
            dataset_version_tag="v1",
            dataset_hash="h1",
            base_model_name="base",
            base_model_revision="main",
            tokenizer_name_or_path="tok",
            adapter_type="LORA",
            artifact_dir=adapter_dir,
        )

        # Tamper with adapter_model.safetensors by altering 1 byte
        target_file = os.path.join(adapter_dir, "adapter_model.safetensors")
        with open(target_file, "ab") as f:
            f.write(b"TAMPERED_EXTRA_BYTE")

        res = ModelArtifactBuilder.verify_artifact_integrity(
            artifact_dir=adapter_dir,
            expected_manifest_hash=manifest.artifact_manifest_hash,
            expected_file_manifest=manifest.file_manifest,
        )

        assert res.is_valid is False
        assert "adapter_model.safetensors" in res.mismatched_files
        assert "Merkle hash mismatch" in res.error_message


def test_integrity_verification_detects_missing_and_unauthorized_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)
        manifest = ModelArtifactBuilder.build_manifest(
            model_name="equigrade-model",
            version="v1",
            version_number=1,
            training_job_id="job_1",
            training_run_id="run_1",
            experiment_id="E2",
            dataset_version_tag="v1",
            dataset_hash="h1",
            base_model_name="base",
            base_model_revision="main",
            tokenizer_name_or_path="tok",
            adapter_type="LORA",
            artifact_dir=adapter_dir,
        )

        # 1. Delete a required file (special_tokens_map.json)
        os.remove(os.path.join(adapter_dir, "special_tokens_map.json"))

        # 2. Add an unauthorized backdoor/unregistered file
        with open(os.path.join(adapter_dir, "unauthorized_extra_file.bin"), "wb") as f:
            f.write(b"MALICIOUS_INJECTION")

        res = ModelArtifactBuilder.verify_artifact_integrity(
            artifact_dir=adapter_dir,
            expected_manifest_hash=manifest.artifact_manifest_hash,
            expected_file_manifest=manifest.file_manifest,
        )

        assert res.is_valid is False
        assert "special_tokens_map.json" in res.missing_files
        assert "unauthorized_extra_file.bin" in res.unauthorized_files
        assert res.error_message is not None


def test_empty_or_missing_directory_raises_error():
    with pytest.raises(FileNotFoundError):
        ModelArtifactBuilder.scan_and_hash_directory("non_existent_folder_path_xyz")

    with tempfile.TemporaryDirectory() as empty_dir:
        with pytest.raises(ValueError, match="contains no valid model files"):
            ModelArtifactBuilder.scan_and_hash_directory(empty_dir)


def test_build_manifest_preserves_none_revision_without_defaulting_to_main():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)
        manifest = ModelArtifactBuilder.build_manifest(
            model_name="equigrade-model",
            version="v1",
            version_number=1,
            training_job_id="job_1",
            training_run_id="run_1",
            experiment_id="E2",
            dataset_version_tag="v1",
            dataset_hash="h1",
            base_model_name="meta-llama/Llama-3.1-8B-Instruct",
            base_model_revision=None,  # Must remain None, not mutated to "main"
            tokenizer_name_or_path="meta-llama/Llama-3.1-8B-Instruct",
            adapter_type="LORA",
            artifact_dir=adapter_dir,
        )

        assert manifest.base_model_revision is None


def test_build_manifest_fails_if_adapter_config_missing_for_lora():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = create_sample_adapter_directory(tmpdir)
        os.remove(os.path.join(adapter_dir, "adapter_config.json"))

        with pytest.raises(
            FileNotFoundError, match="Missing required 'adapter_config.json' for LORA"
        ):
            ModelArtifactBuilder.build_manifest(
                model_name="equigrade-model",
                version="v1",
                version_number=1,
                training_job_id="job_1",
                training_run_id="run_1",
                experiment_id="E2",
                dataset_version_tag="v1",
                dataset_hash="h1",
                base_model_name="meta-llama/Llama-3.1-8B-Instruct",
                base_model_revision=None,
                tokenizer_name_or_path="meta-llama/Llama-3.1-8B-Instruct",
                adapter_type="LORA",
                artifact_dir=adapter_dir,
            )
