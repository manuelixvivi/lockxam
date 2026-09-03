import logging
from typing import Any, Dict, Optional, Tuple

from app.services.ai.training.lora.lora_config import (
    build_bnb_quantization_config_dict,
    build_peft_lora_config_dict,
)
from app.services.ai.training.schemas import LoraHyperparameters, QuantizationConfig

logger = logging.getLogger(__name__)


class MockModelForTesting:
    """
    Lightweight simulated CausalLM module for offline CPU verification of LoRA pipeline.
    """

    def __init__(
        self, model_name: str, trainable_params: int = 16_000_000, total_params: int = 8_000_000_000
    ):
        self.model_name = model_name
        self.trainable_params = trainable_params
        self.total_params = total_params
        self.peft_config = None
        self.device = "cpu"

    def print_trainable_parameters(self) -> Dict[str, Any]:
        pct = (self.trainable_params / self.total_params) * 100.0
        logger.info(
            f"trainable params: {self.trainable_params:,} || all params: {self.total_params:,} || trainable%: {pct:.4f}"
        )
        return {
            "trainable_params": self.trainable_params,
            "total_params": self.total_params,
            "trainable_pct": pct,
        }

    def save_pretrained(self, save_directory: str):
        import json
        import os

        os.makedirs(save_directory, exist_ok=True)
        adapter_config = {
            "base_model_name_or_path": self.model_name,
            "peft_type": "LORA",
            "trainable_params": self.trainable_params,
        }
        with open(os.path.join(save_directory, "adapter_config.json"), "w") as f:
            json.dump(adapter_config, f, indent=2)


class ModelLoader:
    """
    Milestone A9.2: Base Model & PEFT LoRA Adapter Loader.
    Orchestrates HuggingFace AutoModelForCausalLM loading, BitsAndBytes 4-bit (QLoRA) quantization,
    and PEFT LoRA adapter injection.
    """

    @classmethod
    def load_base_model_and_peft_adapter(
        cls,
        model_name_or_path: str,
        lora_params: LoraHyperparameters,
        quant_config: Optional[QuantizationConfig] = None,
        is_cpu_test_mode: bool = False,
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Loads base model and attaches PEFT LoRA adapter.
        Returns (model, trainable_params_summary).
        """
        if is_cpu_test_mode:
            logger.info(f"Loading MockModelForTesting in CPU_TEST mode for '{model_name_or_path}'.")
            mock_model = MockModelForTesting(model_name=model_name_or_path)
            stats = mock_model.print_trainable_parameters()
            return mock_model, stats

        try:
            import torch  # type: ignore
            from peft import (  # type: ignore
                LoraConfig,
                get_peft_model,
                prepare_model_for_kbit_training,
            )
            from transformers import AutoModelForCausalLM, BitsAndBytesConfig  # type: ignore

            bnb_config = None
            if quant_config and (quant_config.load_in_4bit or quant_config.load_in_8bit):
                bnb_dict = build_bnb_quantization_config_dict(quant_config)
                bnb_config = BitsAndBytesConfig(**bnb_dict)

            device_map = "auto" if torch.cuda.is_available() else None
            torch_dtype = (
                torch.bfloat16
                if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
                else torch.float32
            )

            logger.info(f"Loading real AutoModelForCausalLM from '{model_name_or_path}'...")
            base_model = AutoModelForCausalLM.from_pretrained(
                model_name_or_path,
                quantization_config=bnb_config,
                device_map=device_map,
                torch_dtype=torch_dtype,
                trust_remote_code=True,
            )

            if quant_config and quant_config.load_in_4bit:
                base_model = prepare_model_for_kbit_training(base_model)

            peft_dict = build_peft_lora_config_dict(lora_params)
            peft_cfg = LoraConfig(**peft_dict)
            peft_model = get_peft_model(base_model, peft_cfg)

            trainable_params, all_params = peft_model.get_nb_trainable_parameters()
            pct = (trainable_params / all_params) * 100.0 if all_params > 0 else 0.0
            frozen_params = all_params - trainable_params

            if trainable_params <= 0:
                raise RuntimeError(
                    "PEFT LoRA configuration error: 0 trainable parameters detected."
                )
            if frozen_params <= 0 and all_params > 1000:
                raise RuntimeError(
                    "PEFT LoRA invariant violation: Base model weights were not frozen."
                )

            logger.info(
                f"LoRA Adapter Attached: {trainable_params:,} trainable params / {all_params:,} total ({pct:.4f}%) | {frozen_params:,} frozen"
            )

            summary = {
                "trainable_params": trainable_params,
                "total_params": all_params,
                "frozen_params": frozen_params,
                "trainable_pct": pct,
                "is_device_mapped": (device_map is not None),
            }
            return peft_model, summary

        except Exception as e:
            raise RuntimeError(
                f"Failed to load base model and PEFT LoRA adapter for '{model_name_or_path}': {e}"
            )
