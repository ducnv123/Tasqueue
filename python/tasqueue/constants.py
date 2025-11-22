"""
Constants used throughout Tasqueue
"""

# Job status constants
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_FAILED = "failed"
STATUS_DONE = "successful"
STATUS_RETRYING = "retrying"

# Default values
DEFAULT_QUEUE = "tasqueue:tasks"
DEFAULT_MAX_RETRY = 1

# Prefixes for storage
JOB_PREFIX = "job:msg:"
GROUP_PREFIX = "group:msg:"
CHAIN_PREFIX = "chain:msg:"
