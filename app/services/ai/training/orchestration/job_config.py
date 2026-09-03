import json
import logging
from typing import Any, Dict, Union

from app.services.ai.training.schemas import JobConfigModel

logger = logging.getLogger(__name__)


class JobConfigParser:
    """
    Milestone A9.3: Declarative Job Configuration Parser & Sanity Validator.
    Parses YAML/JSON strings or dictionaries into validated JobConfigModel schemas.
    """

    @classmethod
    def parse_and_validate(cls, raw_config: Union[str, Dict[str, Any]]) -> JobConfigModel:
        """
        Parses raw configuration input (JSON string, YAML string, or Dict) and validates constraints.
        """
        if isinstance(raw_config, str):
            raw_config = raw_config.strip()
            if raw_config.startswith("{"):
                config_dict = json.loads(raw_config)
            else:
                # Try simple YAML/JSON parsing
                try:
                    import yaml  # type: ignore

                    config_dict = yaml.safe_load(raw_config)
                except ImportError:
                    config_dict = json.loads(raw_config)
        elif isinstance(raw_config, dict):
            config_dict = raw_config
        else:
            raise ValueError(f"Unsupported config type: {type(raw_config)}")

        # Instantiate Pydantic model
        job_config = JobConfigModel(**config_dict)

        # Sanity Bounds Checking
        if not job_config.dataset_version_tag:
            raise ValueError("Configuration error: 'dataset_version_tag' is required.")

        if job_config.training.learning_rate <= 0 or job_config.training.learning_rate > 0.1:
            raise ValueError(
                f"Configuration error: learning_rate ({job_config.training.learning_rate}) must be in range (0.0, 0.1]."
            )

        if job_config.training.per_device_train_batch_size < 1:
            raise ValueError("Configuration error: per_device_train_batch_size must be >= 1.")

        if job_config.training.gradient_accumulation_steps < 1:
            raise ValueError("Configuration error: gradient_accumulation_steps must be >= 1.")

        if job_config.training.num_train_epochs < 1:
            raise ValueError("Configuration error: num_train_epochs must be >= 1.")

        if job_config.lora.r < 1:
            raise ValueError("Configuration error: LoRA rank (r) must be >= 1.")

        if job_config.lora.lora_alpha < 1:
            raise ValueError("Configuration error: LoRA alpha must be >= 1.")

        if not (0.0 <= job_config.lora.lora_dropout < 1.0):
            raise ValueError("Configuration error: LoRA dropout must be in range [0.0, 1.0).")

        return job_config
