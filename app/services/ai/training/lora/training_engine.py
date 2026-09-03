import json
import logging
import math
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.repositories.ai.dataset_version_repository import dataset_version_repository
from app.services.ai.training.datasets.formatter import SftFormatter
from app.services.ai.training.datasets.loader import DatasetLoader
from app.services.ai.training.datasets.validator import (
    DatasetValidator,
)
from app.services.ai.training.lora.model_loader import ModelLoader
from app.services.ai.training.lora.provenance import ProvenanceService
from app.services.ai.training.schemas import (
    LoraHyperparameters,
    QuantizationConfig,
    SftTrainingArguments,
    TokenizedSample,
    TrainingEvaluationResult,
    TrainingRunProvenance,
)
from app.services.ai.training.tokenization.tokenization_config import (
    ExecutionMode,
    TokenizationConfig,
)
from app.services.ai.training.tokenization.tokenizer_service import TokenizerService

logger = logging.getLogger(__name__)


class TrainingCancelledError(RuntimeError):
    """Raised when training is cancelled cooperatively midway through execution."""

    pass


class TrainingStepCalculator:
    """
    Unified, deterministic step and epoch progress calculator across JobRunner and SftTrainingEngine.
    """

    @staticmethod
    def calculate_steps(
        sample_count: int,
        per_device_batch_size: int,
        gradient_accumulation_steps: int,
        epochs: int,
    ) -> Tuple[int, int]:
        effective_batch = max(1, per_device_batch_size * gradient_accumulation_steps)
        steps_per_epoch = max(1, math.ceil(sample_count / effective_batch))
        total_steps = steps_per_epoch * epochs
        return steps_per_epoch, total_steps


class SftDataCollator:
    """
    Dynamic tensor padding and batch collator for Supervised Fine-Tuning.
    Pads input_ids with pad_token_id (resolved from tokenizer), attention_mask with 0,
    and labels with -100 (IGNORE_INDEX).
    """

    def __init__(self, pad_token_id: int = 0, ignore_index: int = -100):
        self.pad_token_id = pad_token_id
        self.ignore_index = ignore_index

    def __call__(self, samples: List[TokenizedSample]) -> Dict[str, Any]:
        try:
            import torch  # type: ignore

            max_len = max(len(s.input_ids) for s in samples)
            batch_input_ids = []
            batch_attention_mask = []
            batch_labels = []

            for s in samples:
                pad_len = max_len - len(s.input_ids)
                batch_input_ids.append(s.input_ids + [self.pad_token_id] * pad_len)
                batch_attention_mask.append(s.attention_mask + [0] * pad_len)
                labels = s.labels if s.labels is not None else s.input_ids
                batch_labels.append(labels + [self.ignore_index] * pad_len)

            return {
                "input_ids": torch.tensor(batch_input_ids, dtype=torch.long),
                "attention_mask": torch.tensor(batch_attention_mask, dtype=torch.long),
                "labels": torch.tensor(batch_labels, dtype=torch.long),
            }
        except ImportError:
            # Fallback for environments without PyTorch installed
            max_len = max(len(s.input_ids) for s in samples)
            return {
                "input_ids": [
                    s.input_ids + [self.pad_token_id] * (max_len - len(s.input_ids))
                    for s in samples
                ],
                "attention_mask": [
                    s.attention_mask + [0] * (max_len - len(s.attention_mask)) for s in samples
                ],
                "labels": [
                    (s.labels if s.labels is not None else s.input_ids)
                    + [self.ignore_index] * (max_len - len(s.input_ids))
                    for s in samples
                ],
            }


class SftTrainingEngine:
    """
    Milestone A9.2: Supervised Fine-Tuning (SFT / LoRA / QLoRA) Execution Engine.
    Orchestrates end-to-end training runs: pre-flight gate validation, dataset tokenization,
    PEFT adapter injection, real PyTorch gradient optimization loop, checkpoint management,
    validation evaluation, and immutable provenance recording.
    """

    @classmethod
    def run_training(
        cls,
        db: Session,
        version_tag: str,
        base_model_name: Optional[str] = None,
        lora_params: Optional[LoraHyperparameters] = None,
        quant_config: Optional[QuantizationConfig] = None,
        training_args: Optional[SftTrainingArguments] = None,
        token_config: Optional[TokenizationConfig] = None,
        experiment_id: str = "E2_FineTuned_Base",
        cancellation_check: Optional[Callable[[], bool]] = None,
        step_callback: Optional[Callable[[int, float, float, Optional[float], float], None]] = None,
        eval_callback: Optional[Callable[[int, float], None]] = None,
        eval_start_callback: Optional[Callable[[int, float], None]] = None,
        eval_end_callback: Optional[Callable[[int, float], None]] = None,
    ) -> TrainingRunProvenance:
        """
        Executes a supervised fine-tuning run with hard pre-flight guarantees and complete provenance tracking.
        """
        if lora_params is None:
            lora_params = LoraHyperparameters()
        if quant_config is None:
            quant_config = QuantizationConfig()
        if training_args is None:
            training_args = SftTrainingArguments()
        if token_config is None:
            token_config = TokenizationConfig()

        if base_model_name:
            token_config.model_name_or_path = base_model_name
        else:
            base_model_name = token_config.model_name_or_path

        # 1. Hard Pre-Flight Gate Invariant
        logger.info(f"Running pre-flight gate check on DatasetVersion '{version_tag}'...")
        validation_report = DatasetValidator.assert_training_ready(db, version_tag, token_config)

        dv = dataset_version_repository.get_by_version_tag(db, version_tag)
        if not dv:
            raise ValueError(f"DatasetVersion '{version_tag}' not found.")

        # 2. Create Initial Provenance Manifest
        provenance = ProvenanceService.create_initial_provenance(
            dataset_version=dv,
            base_model_name=base_model_name,
            tokenizer_name=base_model_name,
            lora_params=lora_params,
            training_args=training_args,
            experiment_id=experiment_id,
        )
        os.makedirs(training_args.output_dir, exist_ok=True)
        ProvenanceService.save_provenance_to_disk(provenance, training_args.output_dir)

        # 3. Load & Tokenize Datasets
        split_payloads = DatasetLoader.load_from_database(db, version_tag, verify_hash=True)
        train_examples = SftFormatter.format_split(split_payloads.get("train", []))
        val_examples = SftFormatter.format_split(split_payloads.get("val", []))

        train_tokens: List[TokenizedSample] = [
            TokenizerService.tokenize_conversation(ex, token_config) for ex in train_examples
        ]
        val_tokens: List[TokenizedSample] = [
            TokenizerService.tokenize_conversation(ex, token_config) for ex in val_examples
        ]

        logger.info(
            f"Prepared {len(train_tokens)} training samples and {len(val_tokens)} validation samples for run '{provenance.training_run_id}'."
        )

        # 4. Model & PEFT Adapter Setup
        is_cpu_test = token_config.execution_mode == ExecutionMode.CPU_TEST
        model, param_summary = ModelLoader.load_base_model_and_peft_adapter(
            model_name_or_path=base_model_name,
            lora_params=lora_params,
            quant_config=quant_config,
            is_cpu_test_mode=is_cpu_test,
        )

        # Update provenance with parameter counts & execution mode
        provenance.status = "RUNNING"
        provenance.execution_mode = token_config.execution_mode
        provenance.trainable_param_count = param_summary.get("trainable_params")
        provenance.total_param_count = param_summary.get("total_params")
        provenance.trainable_percentage = param_summary.get("trainable_pct")
        ProvenanceService.save_provenance_to_disk(provenance, training_args.output_dir)

        # 5. Resolve pad_token_id dynamically from Tokenizer
        resolved_pad_id = 0
        try:
            hf_tok = TokenizerService.get_hf_tokenizer(
                token_config.model_name_or_path, strict_mode=not is_cpu_test
            )
            if hf_tok is not None:
                if getattr(hf_tok, "pad_token_id", None) is not None:
                    resolved_pad_id = hf_tok.pad_token_id
                elif getattr(hf_tok, "eos_token_id", None) is not None:
                    resolved_pad_id = hf_tok.eos_token_id
        except Exception as tok_err:
            logger.warning(f"Could not resolve tokenizer pad_token_id ({tok_err}), defaulting to 0.")
            resolved_pad_id = 0

        # 6. Execute Training Loop (Real PyTorch or Mock CPU Test Harness)
        try:
            if is_cpu_test:
                logger.info(
                    f"Executing training loop via Mock CPU Test Harness for '{provenance.training_run_id}'..."
                )
                final_train_loss, final_eval_loss, best_ckpt = cls._execute_mock_cpu_simulation(
                    model=model,
                    train_tokens=train_tokens,
                    val_tokens=val_tokens,
                    training_args=training_args,
                    cancellation_check=cancellation_check,
                    step_callback=step_callback,
                    eval_callback=eval_callback,
                    eval_start_callback=eval_start_callback,
                    eval_end_callback=eval_end_callback,
                )
            else:
                logger.info(
                    f"Executing REAL PyTorch/PEFT gradient-based training for '{provenance.training_run_id}'..."
                )
                final_train_loss, final_eval_loss, best_ckpt = cls._execute_real_pytorch_training(
                    model=model,
                    train_tokens=train_tokens,
                    val_tokens=val_tokens,
                    training_args=training_args,
                    pad_token_id=resolved_pad_id,
                    is_device_mapped=param_summary.get("is_device_mapped", False),
                    cancellation_check=cancellation_check,
                    step_callback=step_callback,
                    eval_callback=eval_callback,
                    eval_start_callback=eval_start_callback,
                    eval_end_callback=eval_end_callback,
                )

            provenance.status = "COMPLETED"
            provenance.completed_at = datetime.now(timezone.utc).isoformat()
            provenance.final_train_loss = final_train_loss
            provenance.final_eval_loss = final_eval_loss
            provenance.best_checkpoint_path = best_ckpt

            # 7. Restore Best Validation Checkpoint as Final Adapter
            final_model_dir = os.path.join(training_args.output_dir, "final_adapter")
            os.makedirs(final_model_dir, exist_ok=True)
            best_adapter_dir = os.path.join(training_args.output_dir, "best_adapter")

            source_to_promote = (
                best_adapter_dir
                if (os.path.exists(best_adapter_dir) and os.listdir(best_adapter_dir))
                else best_ckpt
            )

            if source_to_promote and os.path.exists(source_to_promote):
                logger.info(
                    f"Promoting best validation checkpoint '{source_to_promote}' to final_adapter..."
                )
                for item in os.listdir(source_to_promote):
                    s = os.path.join(source_to_promote, item)
                    d = os.path.join(final_model_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
            elif hasattr(model, "save_pretrained"):
                model.save_pretrained(final_model_dir)

            ProvenanceService.save_provenance_to_disk(provenance, training_args.output_dir)
            logger.info(
                f"Training run '{provenance.training_run_id}' finished successfully. Final Train Loss: {final_train_loss:.4f}, Eval Loss: {final_eval_loss:.4f}"
            )
            return provenance

        except Exception as e:
            provenance.status = "FAILED"
            provenance.completed_at = datetime.now(timezone.utc).isoformat()
            provenance.error_message = str(e)
            ProvenanceService.save_provenance_to_disk(provenance, training_args.output_dir)
            logger.error(f"Training run '{provenance.training_run_id}' failed: {e}")
            raise

    @classmethod
    def _execute_real_pytorch_training(
        cls,
        model: Any,
        train_tokens: List[TokenizedSample],
        val_tokens: List[TokenizedSample],
        training_args: SftTrainingArguments,
        pad_token_id: int = 0,
        is_device_mapped: bool = False,
        cancellation_check: Optional[Callable[[], bool]] = None,
        step_callback: Optional[Callable[[int, float, float, Optional[float], float], None]] = None,
        eval_callback: Optional[Callable[[int, float], None]] = None,
        eval_start_callback: Optional[Callable[[int, float], None]] = None,
        eval_end_callback: Optional[Callable[[int, float], None]] = None,
    ) -> Tuple[float, float, str]:
        """
        Executes actual PyTorch forward/backward gradient descent with AdamW optimizer,
        configurable learning rate scheduling (cosine, linear, constant), gradient accumulation,
        mixed-precision (fp16/bf16), clipping, true checkpoint resume (model + optimizer + scheduler + RNG),
        protected best_adapter preservation, cooperative cancellation, step metrics callbacks, and real validation evaluation.
        """
        import torch  # type: ignore
        from torch.utils.data import DataLoader, Dataset  # type: ignore

        # Reproducibility seed
        torch.manual_seed(training_args.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(training_args.seed)

        # Device selection: CUDA -> MPS -> CPU
        if torch.cuda.is_available():
            device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = torch.device("mps")
        else:
            device = torch.device("cpu")

        if not is_device_mapped and hasattr(model, "to"):
            model.to(device)
        model.train()

        # Mixed Precision Setup
        use_amp = False
        amp_dtype = torch.float32
        scaler = None

        if training_args.bf16 and (torch.cuda.is_available() and torch.cuda.is_bf16_supported()):
            use_amp = True
            amp_dtype = torch.bfloat16
        elif training_args.fp16 and torch.cuda.is_available():
            use_amp = True
            amp_dtype = torch.float16
            scaler = torch.cuda.amp.GradScaler()

        # Build DataLoader with dynamic padding
        collator = SftDataCollator(pad_token_id=pad_token_id, ignore_index=-100)

        class TokenizedDataset(Dataset):
            def __init__(self, data: List[TokenizedSample]):
                self.data = data

            def __len__(self):
                return len(self.data)

            def __getitem__(self, idx):
                return self.data[idx]

        train_loader = DataLoader(
            TokenizedDataset(train_tokens),
            batch_size=training_args.per_device_train_batch_size,
            shuffle=True,
            collate_fn=collator,
        )

        val_loader = (
            DataLoader(
                TokenizedDataset(val_tokens),
                batch_size=training_args.per_device_eval_batch_size,
                shuffle=False,
                collate_fn=collator,
            )
            if val_tokens
            else None
        )

        # Optimizer: train only LoRA adapter parameters
        trainable_params = [p for p in model.parameters() if p.requires_grad]
        if not trainable_params:
            trainable_params = list(model.parameters())

        optimizer = torch.optim.AdamW(
            trainable_params,
            lr=training_args.learning_rate,
            weight_decay=training_args.weight_decay,
        )

        steps_per_epoch = max(
            1, math.ceil(len(train_loader) / training_args.gradient_accumulation_steps)
        )
        total_training_steps = steps_per_epoch * training_args.num_train_epochs
        warmup_steps = int(total_training_steps * training_args.warmup_ratio)

        # Configurable Learning Rate Scheduler
        sched_type = (training_args.lr_scheduler_type or "cosine").lower()
        if sched_type == "linear":

            def lr_lambda(current_step: int) -> float:
                if current_step < warmup_steps:
                    return float(current_step) / float(max(1, warmup_steps))
                progress = float(current_step - warmup_steps) / float(
                    max(1, total_training_steps - warmup_steps)
                )
                return max(0.0, 1.0 - progress)

        elif sched_type == "constant":

            def lr_lambda(current_step: int) -> float:
                if current_step < warmup_steps:
                    return float(current_step) / float(max(1, warmup_steps))
                return 1.0

        else:  # "cosine" default

            def lr_lambda(current_step: int) -> float:
                if current_step < warmup_steps:
                    return float(current_step) / float(max(1, warmup_steps))
                progress = float(current_step - warmup_steps) / float(
                    max(1, total_training_steps - warmup_steps)
                )
                return max(0.0, 0.5 * (1.0 + math.cos(math.pi * progress)))

        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

        # Resume from checkpoint if requested (Full state: model + optimizer + scheduler + RNG + position)
        start_step = 0
        if training_args.resume_from_checkpoint and os.path.exists(
            training_args.resume_from_checkpoint
        ):
            ckpt_dir = training_args.resume_from_checkpoint
            opt_path = os.path.join(ckpt_dir, "optimizer.pt")
            sched_path = os.path.join(ckpt_dir, "scheduler.pt")
            state_path = os.path.join(ckpt_dir, "trainer_state.json")
            rng_path = os.path.join(ckpt_dir, "rng_state.pt")

            # 1. Restore Model / LoRA Weights
            try:
                if hasattr(model, "load_adapter"):
                    model.load_adapter(ckpt_dir, adapter_name="default", is_trainable=True)
                elif hasattr(model, "load_pretrained"):
                    model.load_pretrained(ckpt_dir)
                else:
                    for wname in ["adapter_model.bin", "model_weights.pt", "pytorch_model.bin"]:
                        wpath = os.path.join(ckpt_dir, wname)
                        if os.path.exists(wpath):
                            st = torch.load(wpath, map_location=device)
                            model.load_state_dict(st, strict=False)
                            break
                logger.info(f"Restored model/LoRA adapter weights from '{ckpt_dir}'.")
            except Exception as e:
                logger.warning(f"Could not load adapter weights from '{ckpt_dir}': {e}")

            # 2. Restore Optimizer & Scheduler
            if os.path.exists(opt_path):
                optimizer.load_state_dict(torch.load(opt_path, map_location=device))
            if os.path.exists(sched_path):
                scheduler.load_state_dict(torch.load(sched_path, map_location=device))
            if os.path.exists(state_path):
                with open(state_path, "r") as f:
                    start_step = json.load(f).get("global_step", 0)
            if os.path.exists(rng_path):
                rng = torch.load(rng_path, map_location="cpu")
                if "torch" in rng:
                    torch.set_rng_state(rng["torch"])

        start_epoch = start_step // steps_per_epoch if steps_per_epoch > 0 else 0
        skip_batches_in_start_epoch = (
            start_step % steps_per_epoch
        ) * training_args.gradient_accumulation_steps

        global_step = start_step
        total_loss_accum = 0.0
        best_eval_loss = float("inf")
        latest_eval_loss = None
        best_checkpoint_path = ""
        saved_checkpoints: List[str] = []
        best_adapter_dir = os.path.join(training_args.output_dir, "best_adapter")

        train_start_time = time.time()
        tokens_accum = 0

        for epoch in range(start_epoch, training_args.num_train_epochs):
            optimizer.zero_grad()
            for batch_idx, batch in enumerate(train_loader):
                # Cooperative Cancellation Check
                if cancellation_check and cancellation_check():
                    logger.info(
                        f"Cooperative cancellation requested at step {global_step}. Saving emergency checkpoint..."
                    )
                    cancel_ckpt = os.path.join(
                        training_args.output_dir, f"checkpoint-cancelled-step-{global_step}"
                    )
                    os.makedirs(cancel_ckpt, exist_ok=True)
                    if hasattr(model, "save_pretrained"):
                        model.save_pretrained(cancel_ckpt)
                    elif hasattr(model, "state_dict"):
                        torch.save(
                            model.state_dict(), os.path.join(cancel_ckpt, "model_weights.pt")
                        )
                    raise TrainingCancelledError(
                        f"Training cancelled gracefully at step {global_step}."
                    )

                if epoch == start_epoch and batch_idx < skip_batches_in_start_epoch:
                    continue

                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                tokens_accum += int(input_ids.numel())

                # Real Forward Pass with Autocast (Mixed Precision)
                device_type = (
                    "cuda" if device.type == "cuda" else ("mps" if device.type == "mps" else "cpu")
                )
                with torch.autocast(device_type=device_type, dtype=amp_dtype, enabled=use_amp):
                    outputs = model(
                        input_ids=input_ids, attention_mask=attention_mask, labels=labels
                    )
                    loss = outputs.loss if hasattr(outputs, "loss") else outputs[0]
                    loss_scaled = loss / training_args.gradient_accumulation_steps

                # Backward pass
                if scaler is not None:
                    scaler.scale(loss_scaled).backward()
                else:
                    loss_scaled.backward()
                total_loss_accum += loss.item()

                if (batch_idx + 1) % training_args.gradient_accumulation_steps == 0 or (
                    batch_idx + 1
                ) == len(train_loader):
                    # Gradient Clipping & Optimization Step
                    grad_norm_val = training_args.max_grad_norm
                    if scaler is not None:
                        scaler.unscale_(optimizer)
                        torch.nn.utils.clip_grad_norm_(
                            trainable_params, training_args.max_grad_norm
                        )
                        scaler.step(optimizer)
                        scaler.update()
                    else:
                        torch.nn.utils.clip_grad_norm_(
                            trainable_params, training_args.max_grad_norm
                        )
                        optimizer.step()

                    scheduler.step()
                    optimizer.zero_grad()
                    global_step += 1

                    is_epoch_end = batch_idx + 1 == len(train_loader)
                    is_final_step = global_step == total_training_steps
                    current_epoch_val = round(epoch + (batch_idx + 1) / len(train_loader), 2)
                    current_avg_loss = round(total_loss_accum / max(1, global_step), 4)

                    # Validation Evaluation Condition (steps vs epoch)
                    is_eval_step = False
                    if (
                        training_args.eval_strategy == "epoch"
                        and (is_epoch_end or is_final_step)
                        and val_loader
                    ):
                        is_eval_step = True
                    elif (
                        training_args.eval_strategy == "steps"
                        and (global_step % training_args.eval_steps == 0 or is_final_step)
                        and val_loader
                    ):
                        is_eval_step = True

                    if is_eval_step:
                        if eval_start_callback:
                            eval_start_callback(global_step, current_epoch_val)
                        elif eval_callback:
                            eval_callback(global_step, current_epoch_val)

                        eval_res = cls._evaluate_real_pytorch_validation(
                            model, val_loader, device, global_step, epoch
                        )
                        latest_eval_loss = eval_res.eval_loss
                        if eval_res.eval_loss < best_eval_loss:
                            best_eval_loss = eval_res.eval_loss
                            best_checkpoint_path = os.path.join(
                                training_args.output_dir, f"checkpoint-{global_step}"
                            )

                            # Protect best checkpoint by storing in dedicated best_adapter/ directory
                            os.makedirs(best_adapter_dir, exist_ok=True)
                            if hasattr(model, "save_pretrained"):
                                model.save_pretrained(best_adapter_dir)
                            elif hasattr(model, "state_dict"):
                                torch.save(
                                    model.state_dict(),
                                    os.path.join(best_adapter_dir, "model_weights.pt"),
                                )
                                with open(
                                    os.path.join(best_adapter_dir, "adapter_config.json"), "w"
                                ) as f:
                                    json.dump(
                                        {
                                            "best_step": global_step,
                                            "best_eval_loss": eval_res.eval_loss,
                                        },
                                        f,
                                        indent=2,
                                    )

                        if eval_end_callback and not is_final_step:
                            eval_end_callback(global_step, current_epoch_val)

                    # Step Callback with Full Telemetry
                    if step_callback:
                        current_lr = (
                            scheduler.get_last_lr()[0]
                            if hasattr(scheduler, "get_last_lr")
                            else training_args.learning_rate
                        )
                        elapsed_sec = round(time.time() - train_start_time, 2)
                        step_callback(
                            global_step,
                            current_epoch_val,
                            current_avg_loss,
                            latest_eval_loss,
                            current_lr,
                            grad_norm_val,
                            tokens_accum,
                            elapsed_sec,
                        )

                    # Checkpoint Saving Condition (steps vs epoch)
                    is_save_step = False
                    if training_args.save_strategy == "epoch" and (is_epoch_end or is_final_step):
                        is_save_step = True
                    elif training_args.save_strategy == "steps" and (
                        global_step % training_args.save_steps == 0 or is_final_step
                    ):
                        is_save_step = True

                    if is_save_step:
                        ckpt_dir = os.path.join(
                            training_args.output_dir, f"checkpoint-{global_step}"
                        )
                        os.makedirs(ckpt_dir, exist_ok=True)
                        if hasattr(model, "save_pretrained"):
                            model.save_pretrained(ckpt_dir)
                        elif hasattr(model, "state_dict"):
                            torch.save(
                                model.state_dict(), os.path.join(ckpt_dir, "model_weights.pt")
                            )

                        torch.save(optimizer.state_dict(), os.path.join(ckpt_dir, "optimizer.pt"))
                        torch.save(scheduler.state_dict(), os.path.join(ckpt_dir, "scheduler.pt"))
                        torch.save(
                            {
                                "torch": torch.get_rng_state(),
                                "cuda": (
                                    torch.cuda.get_rng_state_all()
                                    if torch.cuda.is_available()
                                    else None
                                ),
                            },
                            os.path.join(ckpt_dir, "rng_state.pt"),
                        )

                        state_payload = {
                            "global_step": global_step,
                            "epoch": current_epoch_val,
                            "train_loss": current_avg_loss,
                            "saved_at": datetime.now(timezone.utc).isoformat(),
                        }
                        with open(os.path.join(ckpt_dir, "trainer_state.json"), "w") as f:
                            json.dump(state_payload, f, indent=2)

                        saved_checkpoints.append(ckpt_dir)

                        # Clean disk while preserving best_adapter
                        while len(saved_checkpoints) > training_args.save_total_limit:
                            oldest = saved_checkpoints.pop(0)
                            if os.path.exists(oldest) and oldest != best_checkpoint_path:
                                shutil.rmtree(oldest, ignore_errors=True)

        final_train_loss = round(total_loss_accum / max(1, global_step), 4)
        final_eval_loss = best_eval_loss if best_eval_loss != float("inf") else final_train_loss
        if not best_checkpoint_path:
            best_checkpoint_path = os.path.join(
                training_args.output_dir, f"checkpoint-{global_step}"
            )

        return final_train_loss, final_eval_loss, best_checkpoint_path

    @classmethod
    def _evaluate_real_pytorch_validation(
        cls, model: Any, val_loader: Any, device: Any, step: int, epoch: float
    ) -> TrainingEvaluationResult:
        """
        Executes genuine forward pass evaluation over validation batches with torch.no_grad().
        """
        import torch  # type: ignore

        model.eval()
        total_eval_loss = 0.0
        batch_count = 0
        total_samples = 0

        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)

                outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
                loss = outputs.loss if hasattr(outputs, "loss") else outputs[0]
                total_eval_loss += loss.item()
                batch_count += 1
                total_samples += input_ids.size(0)

        model.train()
        avg_eval_loss = round(total_eval_loss / max(1, batch_count), 4)
        perplexity = round(math.exp(min(avg_eval_loss, 20.0)), 4)

        logger.info(
            f"[Real Eval Step {step} | Epoch {epoch:.2f}] Validation Loss: {avg_eval_loss:.4f} | Perplexity: {perplexity:.4f}"
        )

        return TrainingEvaluationResult(
            epoch=epoch,
            step=step,
            eval_loss=avg_eval_loss,
            eval_perplexity=perplexity,
            eval_samples_count=total_samples,
            metrics={"eval_loss": avg_eval_loss, "perplexity": perplexity},
        )

    @classmethod
    def _execute_mock_cpu_simulation(
        cls,
        model: Any,
        train_tokens: List[TokenizedSample],
        val_tokens: List[TokenizedSample],
        training_args: SftTrainingArguments,
        cancellation_check: Optional[Callable[[], bool]] = None,
        step_callback: Optional[Callable[[int, float, float, Optional[float], float], None]] = None,
        eval_callback: Optional[Callable[[int, float], None]] = None,
        eval_start_callback: Optional[Callable[[int, float], None]] = None,
        eval_end_callback: Optional[Callable[[int, float], None]] = None,
    ) -> Tuple[float, float, str]:
        """
        Mock CPU test harness for fast, deterministic unit test verification without requiring GPUs.
        """
        num_samples = len(train_tokens)
        effective_batch_size = (
            training_args.per_device_train_batch_size * training_args.gradient_accumulation_steps
        )
        steps_per_epoch = max(1, math.ceil(num_samples / effective_batch_size))
        total_steps = steps_per_epoch * training_args.num_train_epochs

        start_step = 0
        if training_args.resume_from_checkpoint and os.path.exists(
            training_args.resume_from_checkpoint
        ):
            ckpt_state_file = os.path.join(
                training_args.resume_from_checkpoint, "trainer_state.json"
            )
            if os.path.exists(ckpt_state_file):
                with open(ckpt_state_file, "r") as f:
                    st = json.load(f)
                    start_step = st.get("global_step", 0)

        global_step = start_step
        current_loss = 2.50
        best_eval_loss = float("inf")
        latest_eval_loss = None
        best_checkpoint_path = ""
        saved_checkpoints: List[str] = []
        best_adapter_dir = os.path.join(training_args.output_dir, "best_adapter")

        sim_start_time = time.time()
        for step in range(start_step + 1, total_steps + 1):
            # Cooperative Cancellation Check
            if cancellation_check and cancellation_check():
                logger.info(
                    f"Cooperative cancellation requested at simulation step {step}. Saving emergency checkpoint..."
                )
                cancel_ckpt = os.path.join(
                    training_args.output_dir, f"checkpoint-cancelled-step-{step}"
                )
                os.makedirs(cancel_ckpt, exist_ok=True)
                if hasattr(model, "save_pretrained"):
                    model.save_pretrained(cancel_ckpt)
                raise TrainingCancelledError(f"Training cancelled gracefully at step {step}.")

            global_step = step
            epoch = round(step / steps_per_epoch, 2)
            progress = step / total_steps
            decay = 0.5 * (1.0 + math.cos(math.pi * progress))
            current_loss = round(0.40 + (1.80 * decay) + (0.05 * math.sin(step)), 4)

            # Evaluation trigger
            if training_args.eval_strategy in ["steps", "epoch"] and (
                step % training_args.eval_steps == 0 or step == total_steps
            ):
                if eval_start_callback:
                    eval_start_callback(step, epoch)
                elif eval_callback:
                    eval_callback(step, epoch)

                eval_loss = round(current_loss * 1.05, 4) if val_tokens else current_loss
                latest_eval_loss = eval_loss
                if eval_loss < best_eval_loss:
                    best_eval_loss = eval_loss
                    best_checkpoint_path = os.path.join(
                        training_args.output_dir, f"checkpoint-{step}"
                    )
                    os.makedirs(best_adapter_dir, exist_ok=True)
                    if hasattr(model, "save_pretrained"):
                        model.save_pretrained(best_adapter_dir)

                if eval_end_callback and step < total_steps:
                    eval_end_callback(step, epoch)

            # Step Callback with Full Telemetry
            if step_callback:
                elapsed_sec = round(time.time() - sim_start_time, 2)
                tokens_est = step * effective_batch_size * 256
                step_callback(
                    step,
                    epoch,
                    current_loss,
                    latest_eval_loss,
                    training_args.learning_rate,
                    1.0,
                    tokens_est,
                    elapsed_sec,
                )

            # Checkpoint saving
            if step % training_args.save_steps == 0 or step == total_steps:
                ckpt_dir = os.path.join(training_args.output_dir, f"checkpoint-{step}")
                os.makedirs(ckpt_dir, exist_ok=True)
                if hasattr(model, "save_pretrained"):
                    model.save_pretrained(ckpt_dir)

                state_payload = {
                    "global_step": step,
                    "epoch": epoch,
                    "train_loss": current_loss,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                }
                with open(os.path.join(ckpt_dir, "trainer_state.json"), "w") as f:
                    json.dump(state_payload, f, indent=2)

                saved_checkpoints.append(ckpt_dir)
                while len(saved_checkpoints) > training_args.save_total_limit:
                    oldest = saved_checkpoints.pop(0)
                    if os.path.exists(oldest):
                        shutil.rmtree(oldest, ignore_errors=True)

        final_eval_loss = best_eval_loss if best_eval_loss != float("inf") else current_loss
        if not best_checkpoint_path:
            best_checkpoint_path = os.path.join(
                training_args.output_dir, f"checkpoint-{global_step}"
            )

        return current_loss, final_eval_loss, best_checkpoint_path
