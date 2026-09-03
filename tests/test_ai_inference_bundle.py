import json
import os
import tempfile
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.ai.model_version import ModelVersionStatus
from app.services.ai.inference.bundle import InferenceBundle, ServingExecutionContract
from app.services.ai.inference.serving_provider import model_serving_provider
from app.services.ai.training.orchestration.job_runner import JobRunner
from app.services.ai.training.registry.service import model_registry_service
from tests.test_ai_training_orchestration import create_orchestration_dataset


def create_sample_adapter_files(
    adapter_dir: str, base_model: str = "meta-llama/Llama-3.1-8B-Instruct"
):
    """Helper to create PEFT LoRA adapter files in a directory."""
    os.makedirs(adapter_dir, exist_ok=True)
    with open(os.path.join(adapter_dir, "adapter_config.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "base_model_name_or_path": base_model,
                "lora_alpha": 32,
                "lora_dropout": 0.05,
                "r": 16,
                "target_modules": ["q_proj", "v_proj"],
                "peft_type": "LORA",
            },
            f,
            indent=2,
        )
    with open(os.path.join(adapter_dir, "adapter_model.safetensors"), "wb") as f:
        f.write(b"MOCK_SAFETENSORS_WEIGHTS_INFERENCE_BUNDLE_TEST_1234567890")
    with open(os.path.join(adapter_dir, "special_tokens_map.json"), "w", encoding="utf-8") as f:
        json.dump({"pad_token": "<|finetune_pad|>"}, f)
    with open(os.path.join(adapter_dir, "tokenizer_config.json"), "w", encoding="utf-8") as f:
        json.dump({"model_max_length": 2048}, f)


def create_registered_and_promoted_model_fixture(
    db: Session,
    base_model_name: str = "meta-llama/Llama-3.1-8B-Instruct",
    school_name: str = "SMA Serving Bundle Lab",
):
    v_tag = f"v_inf_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, school_name=school_name)
    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "base_model_name": base_model_name,
                "execution_mode": "CPU_TEST",
                "training": {"num_train_epochs": 1},
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
            created_by_user_id=teacher.id,
        )
        JobRunner.start_job(db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir)
        db.refresh(job)
        return job, dv, teacher, school


# ==============================================================================
# 1. ACTIVE BUNDLE RESOLUTION & LIFECYCLE
# ==============================================================================


def test_resolve_active_production_and_staged_bundles(db: Session):
    job, dv, teacher, school = create_registered_and_promoted_model_fixture(db)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = os.path.join(tmpdir, "adapter")
        create_sample_adapter_files(adapter_dir, base_model=job.base_model_name)

        model_name = f"model-serve-{uuid.uuid4().hex[:4]}"

        # 1. Register & Validate
        mv = model_registry_service.register_model_version(
            db=db,
            model_name=model_name,
            training_job_id=job.id,
            base_artifact_dir=adapter_dir,
            school_id=school.id,
            created_by_user_id=teacher.id,
        )
        model_registry_service.validate_model_version(
            db=db, model_version_id=mv.id, artifact_dir=adapter_dir, school_id=school.id
        )

        # 2. Promote to STAGED
        model_registry_service.promote_to_staged(
            db=db, model_version_id=mv.id, reason="Staging verification", school_id=school.id
        )

        staged_bundle = model_serving_provider.get_active_model_bundle(
            db=db,
            model_name=model_name,
            school_id=school.id,
            stage="STAGED",
            local_artifact_root=adapter_dir,
        )
        assert staged_bundle is not None
        assert staged_bundle.version == "v1"
        assert staged_bundle.status == ModelVersionStatus.STAGED.value
        assert staged_bundle.base_model_name == "meta-llama/Llama-3.1-8B-Instruct"

        # 3. Promote to PRODUCTION
        model_registry_service.promote_to_production(
            db=db, model_version_id=mv.id, reason="Release live", school_id=school.id
        )

        prod_bundle = model_serving_provider.get_active_model_bundle(
            db=db,
            model_name=model_name,
            school_id=school.id,
            stage="PRODUCTION",
            local_artifact_root=adapter_dir,
        )
        assert prod_bundle is not None
        assert prod_bundle.version == "v1"
        assert prod_bundle.status == ModelVersionStatus.PRODUCTION.value


# ==============================================================================
# 2. DYNAMIC BASE MODEL PROVENANCE
# ==============================================================================


def test_dynamic_base_model_provenance_inheritance(db: Session):
    custom_base_model = "Qwen/Qwen2.5-7B-Instruct"
    job, dv, teacher, school = create_registered_and_promoted_model_fixture(
        db, base_model_name=custom_base_model
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = os.path.join(tmpdir, "adapter")
        create_sample_adapter_files(adapter_dir, base_model=custom_base_model)

        model_name = f"model-qwen-{uuid.uuid4().hex[:4]}"
        mv = model_registry_service.register_model_version(
            db=db,
            model_name=model_name,
            training_job_id=job.id,
            base_artifact_dir=adapter_dir,
            school_id=school.id,
            created_by_user_id=teacher.id,
        )
        model_registry_service.validate_model_version(
            db=db, model_version_id=mv.id, artifact_dir=adapter_dir, school_id=school.id
        )
        model_registry_service.promote_to_production(
            db=db, model_version_id=mv.id, reason="Qwen production model", school_id=school.id
        )

        bundle = model_serving_provider.get_active_model_bundle(
            db=db, model_name=model_name, school_id=school.id, local_artifact_root=adapter_dir
        )

        # Must dynamically inherit Qwen base model provenance, NOT hardcoded Llama
        assert bundle.base_model_name == "Qwen/Qwen2.5-7B-Instruct"
        assert bundle.tokenizer_name_or_path == "Qwen/Qwen2.5-7B-Instruct"


# ==============================================================================
# 3. CRYPTOGRAPHIC TAMPERING DEFENSE ON STARTUP
# ==============================================================================


def test_serving_startup_rejects_corrupted_or_tampered_weights(db: Session):
    job, dv, teacher, school = create_registered_and_promoted_model_fixture(db)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = os.path.join(tmpdir, "adapter")
        create_sample_adapter_files(adapter_dir, base_model=job.base_model_name)

        model_name = f"model-tamper-serve-{uuid.uuid4().hex[:4]}"
        mv = model_registry_service.register_model_version(
            db=db,
            model_name=model_name,
            training_job_id=job.id,
            base_artifact_dir=adapter_dir,
            school_id=school.id,
            created_by_user_id=teacher.id,
        )
        model_registry_service.validate_model_version(
            db=db, model_version_id=mv.id, artifact_dir=adapter_dir, school_id=school.id
        )
        model_registry_service.promote_to_production(
            db=db, model_version_id=mv.id, reason="Deploy", school_id=school.id
        )

        # Tamper with weight file
        with open(os.path.join(adapter_dir, "adapter_model.safetensors"), "ab") as f:
            f.write(b"TAMPERED_IN_STORAGE")

        # Attempting to load bundle for serving must be rejected by real-time integrity check
        with pytest.raises(ValueError, match="Cryptographic verification failed"):
            model_serving_provider.get_active_model_bundle(
                db=db, model_name=model_name, school_id=school.id, local_artifact_root=adapter_dir
            )


# ==============================================================================
# 4. RAG DECOUPLING & PROMPT FORMATTING CONTRACT
# ==============================================================================


def test_rag_separation_and_prompt_formatting():
    bundle = InferenceBundle(
        model_name="equigrade-bio-grader",
        version="v1",
        version_number=1,
        status="PRODUCTION",
        base_model_name="meta-llama/Llama-3.1-8B-Instruct",
        base_model_revision=None,
        tokenizer_name_or_path="meta-llama/Llama-3.1-8B-Instruct",
        adapter_type="LORA",
        adapter_dir="mock_dir",
        artifact_manifest_hash="sha256:hash",
        file_manifest=[],
        contract=ServingExecutionContract(max_sequence_length=2048, temperature=0.0),
    )

    # Verify RAG is not embedded inside the model bundle weights
    assert bundle.contract.enable_rag_augmentation is False

    # Verify prompt formatting matches SFT contract
    prompt = bundle.format_inference_prompt(
        user_instruction="Berikan evaluasi jawaban esai biologi.",
        student_answer="Mitokondria adalah organel penghasil ATP melalui respirasi sel.",
        rubric_criteria="Kriteria 1: Menyebutkan fungsi mitokondria (Skor 5).",
    )

    assert "<|begin_of_text|><|start_header_id|>system<|end_header_id|>" in prompt
    assert "Jawaban Siswa:\nMitokondria adalah organel" in prompt
    assert "<|start_header_id|>assistant<|end_header_id|>" in prompt
