import logging
from typing import Any, Dict

from app.services.ai.training.schemas import (
    LoraHyperparameters,
    QuantizationConfig,
    SftTrainingArguments,
)

logger = logging.getLogger(__name__)


def build_peft_lora_config_dict(lora_args: LoraHyperparameters) -> Dict[str, Any]:
    """
    Constructs a dictionary compatible with peft.LoraConfig.
    """
    return {
        "r": lora_args.r,
        "lora_alpha": lora_args.lora_alpha,
        "lora_dropout": lora_args.lora_dropout,
        "bias": lora_args.bias,
        "target_modules": list(lora_args.target_modules),
        "task_type": lora_args.task_type,
    }


def build_bnb_quantization_config_dict(quant_args: QuantizationConfig) -> Dict[str, Any]:
    """
    Constructs a dictionary compatible with transformers.BitsAndBytesConfig for QLoRA.
    """
    compute_dtype = quant_args.bnb_4bit_compute_dtype.lower()
    try:
        import torch  # type: ignore

        dtype_map = {
            "bfloat16": getattr(torch, "bfloat16", "bfloat16"),
            "float16": getattr(torch, "float16", "float16"),
            "float32": getattr(torch, "float32", "float32"),
        }
        compute_dtype = dtype_map.get(compute_dtype, compute_dtype)
    except Exception:
        pass

    return {
        "load_in_4bit": quant_args.load_in_4bit,
        "load_in_8bit": quant_args.load_in_8bit,
        "bnb_4bit_quant_type": quant_args.bnb_4bit_quant_type,
        "bnb_4bit_use_double_quant": quant_args.bnb_4bit_use_double_quant,
        "bnb_4bit_compute_dtype": compute_dtype,
    }


def build_hf_training_args_dict(sft_args: SftTrainingArguments) -> Dict[str, Any]:
    """
    Constructs a dictionary compatible with trl.SFTConfig / transformers.TrainingArguments.
    """
    return {
        "output_dir": sft_args.output_dir,
        "num_train_epochs": sft_args.num_train_epochs,
        "per_device_train_batch_size": sft_args.per_device_train_batch_size,
        "per_device_eval_batch_size": sft_args.per_device_eval_batch_size,
        "gradient_accumulation_steps": sft_args.gradient_accumulation_steps,
        "learning_rate": sft_args.learning_rate,
        "weight_decay": sft_args.weight_decay,
        "warmup_ratio": sft_args.warmup_ratio,
        "lr_scheduler_type": sft_args.lr_scheduler_type,
        "logging_steps": sft_args.logging_steps,
        "evaluation_strategy": sft_args.eval_strategy,
        "eval_steps": sft_args.eval_steps,
        "save_strategy": sft_args.save_strategy,
        "save_steps": sft_args.save_steps,
        "save_total_limit": sft_args.save_total_limit,
        "seed": sft_args.seed,
        "fp16": sft_args.fp16,
        "bf16": sft_args.bf16,
        "max_grad_norm": sft_args.max_grad_norm,
    }
