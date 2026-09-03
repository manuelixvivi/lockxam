import hashlib
import json
import logging
import os
import platform
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from app.models.ai.dataset_version import DatasetVersion
from app.services.ai.training.schemas import (
    LoraHyperparameters,
    SftTrainingArguments,
    TrainingRunProvenance,
)

logger = logging.getLogger(__name__)


class ProvenanceService:
    """
    Milestone A9.2: Training Run Provenance & Scientific Lineage Service.
    Generates deterministic cryptographic fingerprints of training configurations,
    audits compute environment, and produces immutable provenance manifests.
    """

    @classmethod
    def compute_config_hash(cls, config_model: Any) -> str:
        """
        Computes deterministic SHA-256 hash of any Pydantic schema or dictionary.
        """
        if hasattr(config_model, "model_dump"):
            data = config_model.model_dump()
        elif isinstance(config_model, dict):
            data = config_model
        else:
            data = dict(config_model)

        canonical_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def get_device_info(cls) -> Dict[str, Any]:
        """
        Audits execution hardware and PyTorch / CUDA runtime.
        """
        info: Dict[str, Any] = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "device": "cpu",
            "cuda_available": False,
            "gpu_count": 0,
            "gpu_names": [],
            "total_vram_gb": 0.0,
        }

        try:
            import torch  # type: ignore

            info["torch_version"] = torch.__version__
            if torch.cuda.is_available():
                info["device"] = "cuda"
                info["cuda_available"] = True
                info["cuda_version"] = torch.version.cuda
                info["gpu_count"] = torch.cuda.device_count()
                gpu_names = []
                total_mem = 0.0
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    gpu_names.append(props.name)
                    total_mem += props.total_memory / (1024**3)
                info["gpu_names"] = gpu_names
                info["total_vram_gb"] = round(total_mem, 2)
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                info["device"] = "mps"
        except Exception as e:
            info["torch_error"] = str(e)

        return info

    @classmethod
    def create_initial_provenance(
        cls,
        dataset_version: DatasetVersion,
        base_model_name: str,
        tokenizer_name: str,
        lora_params: LoraHyperparameters,
        training_args: SftTrainingArguments,
        experiment_id: str = "E2_FineTuned_Base",
    ) -> TrainingRunProvenance:
        """
        Constructs an initial TrainingRunProvenance record before training launches.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()

        lora_hash = cls.compute_config_hash(lora_params)
        args_hash = cls.compute_config_hash(training_args)
        device_info = cls.get_device_info()

        return TrainingRunProvenance(
            training_run_id=run_id,
            experiment_id=experiment_id,
            dataset_version_tag=dataset_version.version_tag,
            dataset_hash=dataset_version.dataset_hash,
            manifest_hash=dataset_version.manifest_hash,
            base_model_name=base_model_name,
            tokenizer_name=tokenizer_name,
            lora_config_hash=lora_hash,
            training_args_hash=args_hash,
            total_train_samples=dataset_version.train_count,
            total_val_samples=dataset_version.val_count,
            device_info=device_info,
            created_at=now_utc,
            status="INITIALIZED",
        )

    @classmethod
    def save_provenance_to_disk(cls, provenance: TrainingRunProvenance, output_dir: str) -> str:
        """
        Serializes the provenance manifest to training_provenance.json in the output directory.
        """
        os.makedirs(output_dir, exist_ok=True)
        manifest_path = os.path.join(output_dir, "training_provenance.json")

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(provenance.model_dump(), f, indent=2, ensure_ascii=False)

        logger.info(f"Saved immutable TrainingRunProvenance to '{manifest_path}'.")
        return manifest_path
