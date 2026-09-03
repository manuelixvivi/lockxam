import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.ai.training.orchestration.artifact_store import ArtifactStore
from app.services.ai.training.schemas import StepMetric

logger = logging.getLogger(__name__)


class MetricsLogger:
    """
    Milestone A9.3: Streaming Step Metrics Logger.
    Appends real-time training and evaluation metrics to 'metrics.jsonl' via ArtifactStore,
    maintains in-memory summaries, and handles process restarts cleanly.
    """

    def __init__(self, artifact_store: ArtifactStore, log_filename: str = "metrics.jsonl"):
        self.artifact_store = artifact_store
        self.log_filename = log_filename
        self.start_time = time.time()
        self.logged_metrics: List[StepMetric] = []

    def log_step(
        self,
        step: int,
        epoch: float,
        train_loss: float,
        learning_rate: float,
        eval_loss: Optional[float] = None,
        eval_perplexity: Optional[float] = None,
        grad_norm: Optional[float] = None,
        tokens_processed: Optional[int] = None,
        elapsed_seconds: Optional[float] = None,
    ) -> StepMetric:
        """
        Logs a single training/evaluation step metric record.
        """
        elapsed = (
            elapsed_seconds
            if elapsed_seconds is not None
            else round(time.time() - self.start_time, 2)
        )
        metric = StepMetric(
            timestamp=datetime.now(timezone.utc).isoformat(),
            step=step,
            epoch=round(epoch, 3),
            train_loss=round(train_loss, 4),
            eval_loss=round(eval_loss, 4) if eval_loss is not None else None,
            eval_perplexity=round(eval_perplexity, 4) if eval_perplexity is not None else None,
            learning_rate=learning_rate,
            grad_norm=round(grad_norm, 4) if grad_norm is not None else None,
            tokens_processed=tokens_processed,
            elapsed_seconds=elapsed,
        )

        # Append to stream through ArtifactStore
        self.artifact_store.append_jsonl_record(self.log_filename, metric.model_dump())
        self.logged_metrics.append(metric)

        logger.info(
            f"[Job Step {step:4d} | Epoch {epoch:5.2f}] Train Loss: {train_loss:.4f}"
            + (
                f" | Eval Loss: {eval_loss:.4f} | PPL: {eval_perplexity:.4f}"
                if eval_loss is not None
                else ""
            )
            + f" | LR: {learning_rate:.2e} | Elapsed: {elapsed}s"
        )
        return metric

    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """
        Reads all historical metrics from the active store.
        """
        records: List[Dict[str, Any]] = []
        if not self.artifact_store.exists(self.log_filename):
            return records

        full_path = self.artifact_store.get_full_path(self.log_filename)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        return records
