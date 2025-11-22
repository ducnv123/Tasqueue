"""
Tasqueue - A lightweight, distributed job/worker implementation in Python
"""

from .server import Server, ServerOpts, TaskOpts
from .job import Job, JobOpts, JobContext
from .group import Group, GroupOpts
from .chain import Chain, ChainOpts
from .interfaces import Broker, Results

__version__ = "2.0.0"
__all__ = [
    "Server",
    "ServerOpts",
    "TaskOpts",
    "Job",
    "JobOpts",
    "JobContext",
    "Group",
    "GroupOpts",
    "Chain",
    "ChainOpts",
    "Broker",
    "Results",
]

# Job status constants
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_FAILED = "failed"
STATUS_DONE = "successful"
STATUS_RETRYING = "retrying"
