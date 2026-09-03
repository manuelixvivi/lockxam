import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.ai.training_job import TrainingJob, TrainingJobStatus

logger = logging.getLogger(__name__)


class TrainingJobRepository:
    """
    Milestone A9.3: Training Job Repository.
    Manages database lifecycle operations, progress metrics tracking, heartbeat monitoring,
    stale job detection, and strict defense-in-depth multi-tenant school isolation across all mutations.
    """

    def create(self, db: Session, job: TrainingJob) -> TrainingJob:
        db.add(job)
        db.flush()
        db.refresh(job)
        return job

    def get_by_job_id(
        self, db: Session, job_id: str, school_id: Optional[int] = None
    ) -> Optional[TrainingJob]:
        query = db.query(TrainingJob).filter(TrainingJob.job_id == job_id)
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)
        return query.first()

    def get_by_run_id(
        self, db: Session, run_id: str, school_id: Optional[int] = None
    ) -> Optional[TrainingJob]:
        query = db.query(TrainingJob).filter(TrainingJob.current_run_id == run_id)
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)
        return query.first()

    def list_jobs(
        self,
        db: Session,
        school_id: Optional[int] = None,
        status: Optional[str] = None,
        experiment_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TrainingJob]:
        query = db.query(TrainingJob)
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)
        if status is not None:
            query = query.filter(TrainingJob.status == status)
        if experiment_id is not None:
            query = query.filter(TrainingJob.experiment_id == experiment_id)
        return query.order_by(TrainingJob.created_at.desc()).offset(skip).limit(limit).all()

    def claim_and_initialize_job(
        self, db: Session, job_id: str, worker_id: str, school_id: Optional[int] = None
    ) -> Optional[TrainingJob]:
        """
        Atomically claims a QUEUED or RESUMING job for execution by a worker.
        Prevents duplicate execution race conditions across concurrent workers.
        """
        query = db.query(TrainingJob).filter(
            TrainingJob.job_id == job_id,
            TrainingJob.status.in_([TrainingJobStatus.QUEUED, TrainingJobStatus.RESUMING]),
        )
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)

        try:
            # Row-level lock if supported by database engine
            if db.bind and db.bind.dialect.name != "sqlite":
                job = query.with_for_update().first()
            else:
                job = query.first()
        except Exception:
            job = query.first()

        if not job:
            return None

        now_utc = datetime.now(timezone.utc)
        job.status = TrainingJobStatus.INITIALIZING
        job.worker_id = worker_id
        job.last_heartbeat_at = now_utc
        db.flush()
        db.refresh(job)
        return job

    def update_status(
        self,
        db: Session,
        job_id: str,
        status: str,
        school_id: Optional[int] = None,
        error_message: Optional[str] = None,
        failure_code: Optional[str] = None,
    ) -> Optional[TrainingJob]:
        query = db.query(TrainingJob).filter(TrainingJob.job_id == job_id)
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)
        job = query.first()
        if not job:
            return None

        job.status = status
        now_utc = datetime.now(timezone.utc)

        if status == TrainingJobStatus.RUNNING and job.started_at is None:
            job.started_at = now_utc
            job.last_heartbeat_at = now_utc
        elif status in [
            TrainingJobStatus.COMPLETED,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
            TrainingJobStatus.STALE,
        ]:
            job.completed_at = now_utc

        if error_message:
            job.error_message = error_message
        if failure_code:
            job.failure_code = failure_code

        db.flush()
        db.refresh(job)
        return job

    def update_progress(
        self,
        db: Session,
        job_id: str,
        current_epoch: float,
        current_step: int,
        total_steps: int,
        school_id: Optional[int] = None,
        train_loss: Optional[float] = None,
        eval_loss: Optional[float] = None,
        eval_perplexity: Optional[float] = None,
        best_checkpoint_path: Optional[str] = None,
        final_adapter_path: Optional[str] = None,
    ) -> Optional[TrainingJob]:
        query = db.query(TrainingJob).filter(TrainingJob.job_id == job_id)
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)
        job = query.first()
        if not job:
            return None

        job.current_epoch = current_epoch
        job.current_step = current_step
        job.total_steps = total_steps
        if train_loss is not None:
            job.train_loss = train_loss
        if eval_loss is not None:
            job.eval_loss = eval_loss
        if eval_perplexity is not None:
            job.eval_perplexity = eval_perplexity
        if best_checkpoint_path is not None:
            job.best_checkpoint_path = best_checkpoint_path
        if final_adapter_path is not None:
            job.final_adapter_path = final_adapter_path

        job.last_heartbeat_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(job)
        return job

    def update_heartbeat(
        self,
        db: Session,
        job_id: str,
        worker_id: Optional[str] = None,
        school_id: Optional[int] = None,
    ) -> Optional[TrainingJob]:
        query = db.query(TrainingJob).filter(TrainingJob.job_id == job_id)
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)
        job = query.first()
        if not job:
            return None

        job.last_heartbeat_at = datetime.now(timezone.utc)
        if worker_id:
            job.worker_id = worker_id

        db.flush()
        db.refresh(job)
        return job

    def is_cancellation_requested(
        self, db: Session, job_id: str, school_id: Optional[int] = None
    ) -> bool:
        """
        Polls whether cancellation was requested for this job in real time.
        """
        query = db.query(TrainingJob.status).filter(TrainingJob.job_id == job_id)
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)
        res = query.first()
        if not res:
            return False
        return res[0] == TrainingJobStatus.CANCEL_REQUESTED

    def request_cancellation(
        self, db: Session, job_id: str, school_id: Optional[int] = None
    ) -> Optional[TrainingJob]:
        query = db.query(TrainingJob).filter(TrainingJob.job_id == job_id)
        if school_id is not None:
            query = query.filter(TrainingJob.school_id == school_id)
        job = query.first()
        if not job:
            return None

        if job.status in [
            TrainingJobStatus.RUNNING,
            TrainingJobStatus.INITIALIZING,
            TrainingJobStatus.PREFLIGHT_PASSED,
            TrainingJobStatus.EVALUATING,
            TrainingJobStatus.QUEUED,
        ]:
            job.status = TrainingJobStatus.CANCEL_REQUESTED
            job.cancel_requested_at = datetime.now(timezone.utc)
            db.flush()
            db.refresh(job)

        return job

    def find_and_mark_stale_jobs(
        self, db: Session, stale_threshold_seconds: int = 300
    ) -> List[TrainingJob]:
        """
        Scans for active jobs that have stopped emitting heartbeats beyond stale_threshold_seconds.
        Transitions them from RUNNING/EVALUATING to STALE.
        """
        threshold_time = datetime.now(timezone.utc) - timedelta(seconds=stale_threshold_seconds)
        active_statuses = [
            TrainingJobStatus.RUNNING,
            TrainingJobStatus.EVALUATING,
            TrainingJobStatus.INITIALIZING,
        ]

        stale_jobs = (
            db.query(TrainingJob)
            .filter(
                TrainingJob.status.in_(active_statuses),
                TrainingJob.last_heartbeat_at.isnot(None),
                TrainingJob.last_heartbeat_at < threshold_time,
            )
            .all()
        )

        for job in stale_jobs:
            logger.warning(
                f"TrainingJob '{job.job_id}' (Worker '{job.worker_id}') timed out. Last heartbeat: {job.last_heartbeat_at}. Marking as STALE."
            )
            job.status = TrainingJobStatus.STALE
            job.failure_code = "WORKER_HEARTBEAT_TIMEOUT"
            job.error_message = f"Execution worker '{job.worker_id}' timed out after {stale_threshold_seconds}s without heartbeat."
            job.completed_at = datetime.now(timezone.utc)

        if stale_jobs:
            db.flush()

        return stale_jobs


training_job_repository = TrainingJobRepository()
