"""
Group implementation for parallel job execution
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import uuid as uuid_lib
import msgpack

from .job import Job
from .constants import (
    STATUS_PROCESSING,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RETRYING,
    GROUP_PREFIX,
)


@dataclass
class GroupOpts:
    """Group configuration options"""
    id: Optional[str] = None


@dataclass
class GroupMeta:
    """Group metadata"""
    id: str
    status: str = STATUS_PROCESSING
    job_status: Dict[str, str] = field(default_factory=dict)


@dataclass
class Group:
    """
    Group holds multiple jobs and executes them in parallel.
    The group is successful only if all jobs succeed.
    """
    jobs: List[Job]
    opts: GroupOpts

    @staticmethod
    def create(jobs: List[Job], opts: Optional[GroupOpts] = None) -> 'Group':
        """
        Create a new group.

        Args:
            jobs: List of jobs to execute in parallel
            opts: Group options

        Returns:
            New Group instance
        """
        if opts is None:
            opts = GroupOpts()

        return Group(jobs=jobs, opts=opts)


@dataclass
class GroupMessage:
    """
    GroupMessage wraps a Group for storage.
    Contains metadata about group execution.
    """
    meta: GroupMeta
    group: Group

    def to_bytes(self) -> bytes:
        """Serialize to msgpack bytes"""
        data = {
            'meta': {
                'id': self.meta.id,
                'status': self.meta.status,
                'job_status': self.meta.job_status,
            },
            'group': {
                'jobs': [
                    {
                        'task': j.task,
                        'payload': j.payload,
                        'opts': {
                            'id': j.opts.id,
                            'queue': j.opts.queue,
                            'max_retries': j.opts.max_retries,
                        }
                    } for j in self.group.jobs
                ],
                'opts': {
                    'id': self.group.opts.id,
                }
            }
        }
        return msgpack.packb(data)

    @staticmethod
    def from_bytes(data: bytes) -> 'GroupMessage':
        """Deserialize from msgpack bytes"""
        from .job import JobOpts  # Import here to avoid circular dependency

        obj = msgpack.unpackb(data, raw=False)

        # Reconstruct GroupMeta
        meta = GroupMeta(
            id=obj['meta']['id'],
            status=obj['meta']['status'],
            job_status=obj['meta']['job_status'],
        )

        # Reconstruct Jobs
        jobs = []
        for job_data in obj['group']['jobs']:
            opts = JobOpts(
                id=job_data['opts']['id'],
                queue=job_data['opts']['queue'],
                max_retries=job_data['opts']['max_retries'],
            )
            job = Job(
                task=job_data['task'],
                payload=job_data['payload'],
                opts=opts,
            )
            jobs.append(job)

        # Reconstruct GroupOpts
        group_opts = GroupOpts(
            id=obj['group']['opts']['id'],
        )

        group = Group(jobs=jobs, opts=group_opts)

        return GroupMessage(meta=meta, group=group)


def get_group_status(job_status: Dict[str, str]) -> str:
    """
    Determine overall group status from individual job statuses.

    Args:
        job_status: Map of job ID to status

    Returns:
        Overall group status
    """
    status = STATUS_DONE

    for st in job_status.values():
        if st == STATUS_FAILED:
            return STATUS_FAILED
        if st != STATUS_DONE:
            status = STATUS_PROCESSING

    return status
