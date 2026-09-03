import logging
import platform
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.models.ai.dataset_version import DatasetVersion
from app.services.ai.training.lora.provenance import ProvenanceService
from app.services.ai.training.orchestration.artifact_store import ArtifactStore
from app.services.ai.training.schemas import JobConfigModel

logger = logging.getLogger(__name__)


class ManifestBuilder:
    """
    Milestone A9.3: Training Manifest & Environment Reproducibility Builder.
    Generates 'training_manifest.json' capturing exact software dependencies,
    git commit, hardware specifications, and cryptographic configuration hashes.
    """

    @classmethod
    def get_git_commit_and_status(cls) -> Tuple[Optional[str], bool]:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res.returncode == 0 and res.stdout and len(res.stdout.strip()) == 40:
                return res.stdout.strip(), True
        except Exception:
            pass
        return None, False

    @classmethod
    def get_software_environment(cls) -> Dict[str, Any]:
        git_commit, git_available = cls.get_git_commit_and_status()
        env: Dict[str, Any] = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "git_commit": git_commit,
            "git_repository_available": git_available,
        }

        # Check key AI library versions
        for pkg_name in ["torch", "transformers", "peft", "bitsandbytes", "trl", "fastapi"]:
            try:
                mod = __import__(pkg_name)
                env[f"{pkg_name}_version"] = getattr(mod, "__version__", "installed")
            except ImportError:
                env[f"{pkg_name}_version"] = "not_installed"

        return env

    @classmethod
    def build_and_save_manifest(
        cls,
        job_id: str,
        run_id: str,
        job_config: JobConfigModel,
        dataset_version: DatasetVersion,
        artifact_store: ArtifactStore,
        worker_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        status: str = "INITIALIZING",
    ) -> Dict[str, Any]:
        """
        Constructs and writes training_manifest.json via the active ArtifactStore.
        """
        config_hash = ProvenanceService.compute_config_hash(job_config)
        hardware_info = ProvenanceService.get_device_info()
        software_env = cls.get_software_environment()

        manifest_payload: Dict[str, Any] = {
            "manifest_version": "1.0.0",
            "job_id": job_id,
            "training_run_id": run_id,
            "parent_run_id": parent_run_id,
            "experiment_id": job_config.experiment_id,
            "dataset_version_tag": dataset_version.version_tag,
            "dataset_hash": dataset_version.dataset_hash,
            "dataset_manifest_hash": dataset_version.manifest_hash,
            "base_model_name": job_config.base_model_name,
            "execution_mode": job_config.execution_mode,
            "config_hash": config_hash,
            "worker_id": worker_id or "local_worker_01",
            "status": status,
            "software_environment": software_env,
            "hardware_specification": hardware_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        artifact_store.save_json("training_manifest.json", manifest_payload)
        logger.info(f"Built and saved training manifest for Job '{job_id}' (Run '{run_id}').")
        return manifest_payload
