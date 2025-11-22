"""
Chain implementation for sequential job execution
"""

from dataclasses import dataclass
from typing import List, Optional
import uuid as uuid_lib
import msgpack

from .job import Job
from . import STATUS_PROCESSING, STATUS_DONE, STATUS_FAILED


CHAIN_PREFIX = "chain:msg:"


@dataclass
class ChainOpts:
    """Chain configuration options"""
    id: Optional[str] = None


@dataclass
class ChainMeta:
    """Chain metadata"""
    id: str
    status: str = STATUS_PROCESSING
    job_id: str = ""
    prev_jobs: List[str] = None

    def __post_init__(self):
        if self.prev_jobs is None:
            self.prev_jobs = []


@dataclass
class Chain:
    """
    Chain holds multiple jobs and executes them sequentially.
    Each job can access the result of the previous job.
    The chain is successful only if all jobs succeed.
    """
    jobs: List[Job]
    opts: ChainOpts

    @staticmethod
    def create(jobs: List[Job], opts: Optional[ChainOpts] = None) -> 'Chain':
        """
        Create a new chain.

        Args:
            jobs: List of jobs to execute sequentially
            opts: Chain options

        Returns:
            New Chain instance

        Raises:
            ValueError: If less than 2 jobs provided
        """
        if len(jobs) < 2:
            raise ValueError("minimum 2 tasks required to form chain")

        if opts is None:
            opts = ChainOpts()

        # Set OnSuccess to form the chain
        for i in range(len(jobs) - 1):
            jobs[i].on_success.append(jobs[i + 1])

        return Chain(jobs=jobs, opts=opts)


@dataclass
class ChainMessage:
    """
    ChainMessage wraps a Chain for storage.
    Contains metadata about chain execution.
    """
    meta: ChainMeta

    def to_bytes(self) -> bytes:
        """Serialize to msgpack bytes"""
        data = {
            'meta': {
                'id': self.meta.id,
                'status': self.meta.status,
                'job_id': self.meta.job_id,
                'prev_jobs': self.meta.prev_jobs,
            }
        }
        return msgpack.packb(data)

    @staticmethod
    def from_bytes(data: bytes) -> 'ChainMessage':
        """Deserialize from msgpack bytes"""
        obj = msgpack.unpackb(data, raw=False)

        meta = ChainMeta(
            id=obj['meta']['id'],
            status=obj['meta']['status'],
            job_id=obj['meta']['job_id'],
            prev_jobs=obj['meta']['prev_jobs'],
        )

        return ChainMessage(meta=meta)
