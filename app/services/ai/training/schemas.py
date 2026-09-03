from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SftMessage(BaseModel):
    """
    Standard conversational message for SFT training (OpenAI / ChatML format).
    """

    role: str = Field(..., description="'system', 'user', or 'assistant'")
    content: str = Field(..., description="Text content of the message")


class SftTargetPayload(BaseModel):
    """
    Structured ground-truth target emitted by teacher assessment.
    """

    score: float
    normalized_score: float
    feedback: str
    rubric_applied: Optional[List[Dict[str, Any]]] = None


class SftConversationExample(BaseModel):
    """
    Complete conversational training example for Supervised Fine-Tuning.
    """

    messages: List[SftMessage] = Field(..., description="Ordered conversation messages")
    task: str = Field("essay_grading", description="Task identifier")
    candidate_id: Optional[int] = None
    question_group_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenizedSample(BaseModel):
    """
    Tokenized representation of a single training example.
    """

    input_ids: List[int]
    attention_mask: List[int]
    labels: Optional[List[int]] = None
    token_length: int
    is_truncated: bool = False
    target_is_truncated: bool = False


class TokenizationStats(BaseModel):
    """
    Statistical summary of token length distribution across a dataset split.
    """

    total_samples: int
    total_tokens: int
    avg_tokens_per_sample: float
    min_tokens: int
    max_tokens: int
    p95_tokens: float
    truncated_samples_count: int
    target_truncated_count: int = 0
    truncation_rate_pct: float


class ValidationReport(BaseModel):
    """
    Cryptographic, structural, and semantic integrity report for a DatasetVersion.
    """

    is_valid: bool
    dataset_version: str
    dataset_hash: str
    manifest_hash: str
    total_samples: int
    split_counts: Dict[str, int]
    disjoint_check_passed: bool
    group_disjoint_passed: bool = True
    score_bounds_passed: bool
    missing_fields_count: int
    validation_errors: List[str] = Field(default_factory=list)
    tokenization_summary: Optional[Dict[str, TokenizationStats]] = None


# ==============================================================================
# MILESTONE A9.2: LORA / QLORA & TRAINING ENGINE SCHEMAS
# ==============================================================================


class LoraHyperparameters(BaseModel):
    """
    PEFT / LoRA (Low-Rank Adaptation) hyperparameter configuration.
    """

    r: int = Field(16, description="LoRA rank dimension (typical values: 8, 16, 32, 64)")
    lora_alpha: int = Field(32, description="LoRA scaling factor (typically 2 * r)")
    lora_dropout: float = Field(0.05, description="Dropout probability for LoRA layers")
    bias: Literal["none", "all", "lora_only"] = Field(
        "none", description="Bias training strategy: 'none', 'all', or 'lora_only'"
    )
    target_modules: List[str] = Field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        description="List of module names to apply LoRA adapter weights",
    )
    task_type: str = Field("CAUSAL_LM", description="PEFT task type")


class QuantizationConfig(BaseModel):
    """
    BitsAndBytes 4-bit (QLoRA) or 8-bit quantization configuration.
    """

    load_in_4bit: bool = Field(True, description="Enable 4-bit quantization (QLoRA)")
    load_in_8bit: bool = Field(False, description="Enable 8-bit quantization")
    bnb_4bit_quant_type: Literal["nf4", "fp4"] = Field(
        "nf4", description="Quantization data type: 'nf4' (NormalFloat4) or 'fp4'"
    )
    bnb_4bit_use_double_quant: bool = Field(
        True, description="Nested double quantization for extra memory savings"
    )
    bnb_4bit_compute_dtype: Literal["bfloat16", "float16", "float32"] = Field(
        "bfloat16", description="Compute precision: 'bfloat16', 'float16', or 'float32'"
    )


class SftTrainingArguments(BaseModel):
    """
    Supervised Fine-Tuning hyperparameters, optimization settings, and checkpointing policies.
    """

    output_dir: str = Field(
        "./checkpoints/sft_run",
        description="Directory to save checkpoints and final adapter weights",
    )
    num_train_epochs: int = Field(3, description="Total number of training epochs")
    per_device_train_batch_size: int = Field(
        2, description="Batch size per GPU/device for training"
    )
    per_device_eval_batch_size: int = Field(
        2, description="Batch size per GPU/device for evaluation"
    )
    gradient_accumulation_steps: int = Field(
        4, description="Number of update steps to accumulate before backward pass"
    )
    learning_rate: float = Field(2e-4, description="Initial peak learning rate")
    weight_decay: float = Field(0.01, description="L2 weight decay regularization factor")
    warmup_ratio: float = Field(0.03, description="Linear warmup ratio over total training steps")
    lr_scheduler_type: Literal["cosine", "linear", "constant", "constant_with_warmup"] = Field(
        "cosine", description="Learning rate schedule: 'cosine', 'linear', or 'constant'"
    )
    logging_steps: int = Field(10, description="Log loss and metrics every N steps")
    eval_strategy: Literal["steps", "epoch", "no"] = Field(
        "steps", description="Evaluation frequency strategy: 'steps', 'epoch', or 'no'"
    )
    eval_steps: int = Field(50, description="Run evaluation loop every N steps")
    save_strategy: Literal["steps", "epoch", "no"] = Field(
        "steps", description="Checkpoint saving strategy: 'steps' or 'epoch'"
    )
    save_steps: int = Field(50, description="Save model checkpoint every N steps")
    save_total_limit: int = Field(3, description="Maximum number of checkpoints to retain on disk")
    seed: int = Field(42, description="Global random seed for deterministic reproducibility")
    fp16: bool = Field(False, description="Enable 16-bit (half) floating point training")
    bf16: bool = Field(True, description="Enable Brain Floating Point (bfloat16) training")
    max_grad_norm: float = Field(0.3, description="Maximum gradient norm for gradient clipping")
    resume_from_checkpoint: Optional[str] = Field(
        None, description="Path to checkpoint directory to resume from"
    )


class TrainingEvaluationResult(BaseModel):
    """
    Validation step or epoch evaluation output.
    """

    epoch: float
    step: int
    eval_loss: float
    eval_perplexity: float
    eval_samples_count: int
    metrics: Dict[str, float] = Field(default_factory=dict)


class TrainingRunProvenance(BaseModel):
    """
    Immutable cryptographic provenance manifest for a completed or active training run.
    Ensures scientific repeatability across experimental conditions (E0..E3).
    """

    training_run_id: str
    experiment_id: str = "E2_FineTuned_Base"
    dataset_version_tag: str
    dataset_hash: str
    manifest_hash: str
    base_model_name: str
    tokenizer_name: str
    lora_config_hash: str
    training_args_hash: str
    total_train_samples: int
    total_val_samples: int
    device_info: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    completed_at: Optional[str] = None
    status: str = "INITIALIZED"
    execution_mode: str = "REAL_TRAINING"
    trainable_param_count: Optional[int] = None
    total_param_count: Optional[int] = None
    trainable_percentage: Optional[float] = None
    final_train_loss: Optional[float] = None
    final_eval_loss: Optional[float] = None
    best_checkpoint_path: Optional[str] = None
    error_message: Optional[str] = None


# ==============================================================================
# MILESTONE A9.3: TRAINING ORCHESTRATION SCHEMAS
# ==============================================================================


class StepMetric(BaseModel):
    """
    Fine-grained step metric record appended to metrics.jsonl.
    """

    timestamp: str
    step: int
    epoch: float
    train_loss: float
    eval_loss: Optional[float] = None
    eval_perplexity: Optional[float] = None
    learning_rate: float
    grad_norm: Optional[float] = None
    tokens_processed: Optional[int] = None
    elapsed_seconds: float


class JobConfigModel(BaseModel):
    """
    Declarative configuration for an entire training job orchestration.
    """

    experiment_id: str = Field("E2_FineTuned_Base", description="Experiment identifier")
    dataset_version_tag: str = Field(..., description="Target DatasetVersion tag")
    base_model_name: str = Field(
        "meta-llama/Llama-3.1-8B-Instruct", description="Base model name or path"
    )
    execution_mode: Literal["CPU_TEST", "LOCAL_GPU", "AWS_GPU", "REMOTE_WORKER"] = Field(
        "CPU_TEST", description="Execution mode: CPU_TEST, LOCAL_GPU, AWS_GPU, REMOTE_WORKER"
    )
    lora: LoraHyperparameters = Field(default_factory=LoraHyperparameters)
    quantization: QuantizationConfig = Field(default_factory=QuantizationConfig)
    training: SftTrainingArguments = Field(default_factory=SftTrainingArguments)
    description: Optional[str] = None


class TrainingJobResponse(BaseModel):
    """
    API representation of a TrainingJob.
    """

    job_id: str
    current_run_id: str
    parent_run_id: Optional[str] = None
    experiment_id: str
    dataset_version_tag: str
    base_model_name: str
    status: str
    execution_mode: str
    worker_id: Optional[str] = None
    retry_count: int = 0
    total_epochs: int
    current_epoch: float
    current_step: int
    total_steps: int
    train_loss: Optional[float] = None
    eval_loss: Optional[float] = None
    eval_perplexity: Optional[float] = None
    best_checkpoint_path: Optional[str] = None
    final_adapter_path: Optional[str] = None
    artifact_uri: str
    error_message: Optional[str] = None
    failure_code: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class JobCancellationRequest(BaseModel):
    reason: Optional[str] = "User requested cancellation"


class JobResumeRequest(BaseModel):
    checkpoint_path: Optional[str] = None
    additional_epochs: Optional[int] = None
