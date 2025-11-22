"""
Job and JobContext implementation
"""

from dataclasses import dataclass, field
from typing import Optional, List, Callable, Any
from datetime import datetime, timedelta
import uuid as uuid_lib
import msgpack

from .constants import STATUS_QUEUED, DEFAULT_QUEUE, DEFAULT_MAX_RETRY


@dataclass
class JobOpts:
    """Job configuration options"""
    id: Optional[str] = None
    eta: Optional[datetime] = None
    queue: str = DEFAULT_QUEUE
    max_retries: int = DEFAULT_MAX_RETRY
    schedule: Optional[str] = None  # Cron expression
    timeout: Optional[timedelta] = None


@dataclass
class Meta:
    """Job metadata"""
    id: str
    on_success_ids: List[str] = field(default_factory=list)
    status: str = STATUS_QUEUED
    queue: str = DEFAULT_QUEUE
    schedule: str = ""
    max_retry: int = DEFAULT_MAX_RETRY
    retried: int = 0
    prev_err: str = ""
    processed_at: Optional[datetime] = None
    prev_job_result: Optional[bytes] = None


@dataclass
class Job:
    """
    Job represents a unit of work to be processed.
    """
    task: str
    payload: bytes
    opts: JobOpts
    on_success: List['Job'] = field(default_factory=list)
    on_error: List['Job'] = field(default_factory=list)

    @staticmethod
    def create(handler: str, payload: bytes, opts: Optional[JobOpts] = None) -> 'Job':
        """
        Create a new job.

        Args:
            handler: Task name that will process this job
            payload: Job payload bytes
            opts: Job options

        Returns:
            New Job instance
        """
        if opts is None:
            opts = JobOpts()

        if not opts.queue:
            opts.queue = DEFAULT_QUEUE

        return Job(
            task=handler,
            payload=payload,
            opts=opts
        )


class JobContext:
    """
    JobContext is passed to handler functions.
    Provides access to job metadata and allows saving results.
    """

    def __init__(self, meta: Meta, results_store: Any):
        self.meta = meta
        self._results_store = results_store

    async def save(self, data: bytes) -> None:
        """
        Save arbitrary results for this job.

        Args:
            data: Result bytes to save
        """
        await self._results_store.set(self.meta.id, data)


@dataclass
class JobMessage:
    """
    JobMessage wraps a Job for transport over the broker.
    Contains metadata and the job itself.
    """
    meta: Meta
    job: Job

    def to_bytes(self) -> bytes:
        """Serialize to msgpack bytes"""
        data = {
            'meta': {
                'id': self.meta.id,
                'on_success_ids': self.meta.on_success_ids,
                'status': self.meta.status,
                'queue': self.meta.queue,
                'schedule': self.meta.schedule,
                'max_retry': self.meta.max_retry,
                'retried': self.meta.retried,
                'prev_err': self.meta.prev_err,
                'processed_at': self.meta.processed_at.isoformat() if self.meta.processed_at else None,
                'prev_job_result': self.meta.prev_job_result,
            },
            'job': {
                'task': self.job.task,
                'payload': self.job.payload,
                'opts': {
                    'id': self.job.opts.id,
                    'eta': self.job.opts.eta.isoformat() if self.job.opts.eta else None,
                    'queue': self.job.opts.queue,
                    'max_retries': self.job.opts.max_retries,
                    'schedule': self.job.opts.schedule,
                    'timeout': self.job.opts.timeout.total_seconds() if self.job.opts.timeout else None,
                },
                'on_success': [
                    {
                        'task': j.task,
                        'payload': j.payload,
                        'opts': {
                            'id': j.opts.id,
                            'queue': j.opts.queue,
                            'max_retries': j.opts.max_retries,
                        }
                    } for j in self.job.on_success
                ],
                'on_error': [
                    {
                        'task': j.task,
                        'payload': j.payload,
                        'opts': {
                            'id': j.opts.id,
                            'queue': j.opts.queue,
                            'max_retries': j.opts.max_retries,
                        }
                    } for j in self.job.on_error
                ],
            }
        }
        return msgpack.packb(data)

    @staticmethod
    def from_bytes(data: bytes) -> 'JobMessage':
        """Deserialize from msgpack bytes"""
        obj = msgpack.unpackb(data, raw=False)

        # Reconstruct Meta
        meta = Meta(
            id=obj['meta']['id'],
            on_success_ids=obj['meta']['on_success_ids'],
            status=obj['meta']['status'],
            queue=obj['meta']['queue'],
            schedule=obj['meta']['schedule'],
            max_retry=obj['meta']['max_retry'],
            retried=obj['meta']['retried'],
            prev_err=obj['meta']['prev_err'],
            processed_at=datetime.fromisoformat(obj['meta']['processed_at']) if obj['meta']['processed_at'] else None,
            prev_job_result=obj['meta']['prev_job_result'],
        )

        # Reconstruct Job
        opts = JobOpts(
            id=obj['job']['opts']['id'],
            eta=datetime.fromisoformat(obj['job']['opts']['eta']) if obj['job']['opts']['eta'] else None,
            queue=obj['job']['opts']['queue'],
            max_retries=obj['job']['opts']['max_retries'],
            schedule=obj['job']['opts']['schedule'],
            timeout=timedelta(seconds=obj['job']['opts']['timeout']) if obj['job']['opts']['timeout'] else None,
        )

        job = Job(
            task=obj['job']['task'],
            payload=obj['job']['payload'],
            opts=opts,
        )

        return JobMessage(meta=meta, job=job)


def default_meta(opts: JobOpts) -> Meta:
    """
    Create default metadata for a job.

    Args:
        opts: Job options

    Returns:
        Meta with defaults filled in
    """
    job_id = opts.id if opts.id else str(uuid_lib.uuid4())

    return Meta(
        id=job_id,
        status=STATUS_QUEUED,
        max_retry=opts.max_retries,
        schedule=opts.schedule or "",
        queue=opts.queue,
    )
