import os
from enum import Enum

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    CPU_TEST = "CPU_TEST"
    REAL_TRAINING = "REAL_TRAINING"


class TokenizationConfig(BaseModel):
    """
    Configuration parameters for SFT tokenization, sequence formatting, and truncation policies.
    Model paths and hyperparameters are dynamic experiment parameters, not hardcoded constants.
    """

    model_name_or_path: str = Field(
        default_factory=lambda: os.getenv(
            "EQUIGRADE_TRAINING_BASE_MODEL", "meta-llama/Llama-3.1-8B-Instruct"
        ),
        description="Target model HuggingFace repository ID or local weights path",
    )
    execution_mode: str = Field(
        default="CPU_TEST",
        description="Execution mode: 'CPU_TEST' allows offline SHA-256 mock encoder; 'REAL_TRAINING' strictly enforces real HuggingFace AutoTokenizer",
    )
    max_seq_length: int = Field(
        2048,
        description="Maximum sequence length context window before truncation",
    )
    padding_side: str = Field("right", description="Padding side: 'left' or 'right'")
    truncation_side: str = Field("right", description="Truncation side: 'left' or 'right'")
    truncation_strategy: str = Field(
        "prompt_first",
        description="'prompt_first' prioritizes protecting assistant ground-truth targets; 'strict_cut' applies raw sequence slicing",
    )
    add_generation_prompt: bool = Field(
        False, description="Whether to append assistant generation prefix"
    )
    chat_template_format: str = Field(
        "chatml",
        description="Chat template structure: 'chatml', 'llama3', or 'standard'",
    )
    mask_prompt_labels: bool = Field(
        True,
        description="If True, cross-entropy loss is only computed on assistant response tokens (-100 on user prompt)",
    )
    max_truncation_rate_pct: float = Field(
        5.0,
        description="Maximum permissible truncation rate percentage before dataset validation failure",
    )
    fail_on_target_truncation: bool = Field(
        True,
        description="Enforces zero tolerance for truncation that cuts into assistant ground-truth targets",
    )
    use_real_tokenizer: bool = Field(
        True,
        description="Whether to attempt loading real HuggingFace AutoTokenizer when in CPU_TEST mode",
    )
