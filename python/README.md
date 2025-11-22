# Tasqueue Python

**Tasqueue** is a lightweight, distributed job/worker implementation in Python, featuring async/await support.

This is the Python port of [Tasqueue](https://github.com/kalbhor/tasqueue) with full feature parity.

## Features

- ✅ Distributed job/task processing
- ✅ Support for individual jobs, groups (parallel), and chains (sequential)
- ✅ Pluggable broker and results backends (Redis, in-memory)
- ✅ Job lifecycle callbacks (processing, success, retrying, failed)
- ✅ Scheduled/delayed job execution
- ✅ Job timeout and retry mechanisms
- ✅ Async/await support throughout
- ✅ OnSuccess/OnError job chaining

## Installation

```bash
pip install -r requirements.txt
```

Or install in development mode:

```bash
pip install -e .
```

## Quick Start

### Basic Usage

```python
import asyncio
import json
from tasqueue import Server, ServerOpts, TaskOpts, Job, JobOpts, JobContext
from tasqueue.brokers import MemoryBroker
from tasqueue.results import MemoryResults

# Define a task handler
async def sum_handler(payload: bytes, ctx: JobContext) -> None:
    data = json.loads(payload)
    result = data['arg1'] + data['arg2']

    # Save result
    await ctx.save(json.dumps({'result': result}).encode())

async def main():
    # Create server
    server = Server(ServerOpts(
        broker=MemoryBroker(),
        results=MemoryResults(),
    ))

    # Register task
    await server.register_task("sum", sum_handler, TaskOpts())

    # Start server
    asyncio.create_task(server.start())

    # Enqueue a job
    job = Job.create("sum", json.dumps({'arg1': 5, 'arg2': 3}).encode())
    job_id = await server.enqueue(job)

    # Wait and get result
    await asyncio.sleep(1)
    result = await server.get_result(job_id)
    print(json.loads(result))  # {'result': 8}

asyncio.run(main())
```

### Using Redis

```python
from tasqueue.brokers.redis_broker import RedisBroker
from tasqueue.results.redis_results import RedisResults

broker = RedisBroker(host="localhost", port=6379)
results = RedisResults(host="localhost", port=6379)

server = Server(ServerOpts(broker=broker, results=results))
```

### Groups (Parallel Execution)

```python
from tasqueue import Group, GroupOpts

jobs = [
    Job.create("task1", payload1),
    Job.create("task2", payload2),
    Job.create("task3", payload3),
]

group = Group.create(jobs, GroupOpts())
group_id = await server.enqueue_group(group)

# Check status
group_msg = await server.get_group(group_id)
print(group_msg.meta.status)  # "successful" when all jobs complete
```

### Chains (Sequential Execution)

```python
from tasqueue import Chain, ChainOpts

jobs = [
    Job.create("step1", payload1),
    Job.create("step2", payload2),
    Job.create("step3", payload3),
]

chain = Chain.create(jobs, ChainOpts())
chain_id = await server.enqueue_chain(chain)

# Each job can access the previous job's result via ctx.meta.prev_job_result
```

## Core Concepts

### Server
The main component that manages task registration and job processing. Coordinates between the broker and results backends.

### Job
A unit of work with:
- Task name (references registered handler)
- Payload (bytes)
- Options (timeout, retries, schedule, etc.)
- OnSuccess/OnError job chaining

### Task
A registered handler function with:
- Handler function (`async def handler(payload: bytes, ctx: JobContext)`)
- Callbacks (success, failure, retry, processing)
- Queue assignment
- Concurrency setting

### Broker
Interface for queue operations:
- `enqueue()` - Add job to queue
- `enqueue_scheduled()` - Schedule job for future execution
- `consume()` - Listen for jobs
- `get_pending()` - Get pending jobs

### Results
Interface for job metadata and results storage:
- `get()`/`set()` - Store arbitrary results
- `set_success()`/`set_failed()` - Mark job status
- `get_success()`/`get_failed()` - Query by status

## Job Lifecycle

1. **Queued** - Initial state when enqueued
2. **Processing** - Worker picked up the job
3. **Retrying** - Job failed, being retried
4. **Successful** - Completed successfully
5. **Failed** - Failed after max retries

## Task Options

```python
TaskOpts(
    concurrency=5,              # Number of concurrent processors
    queue="my_queue",            # Queue name
    success_cb=on_success,       # Called on success
    processing_cb=on_processing, # Called when processing starts
    retrying_cb=on_retry,        # Called on retry
    failed_cb=on_failure,        # Called on final failure
)
```

## Job Options

```python
JobOpts(
    id="custom-id",              # Optional custom ID
    queue="my_queue",            # Queue override
    max_retries=3,               # Retry attempts
    timeout=timedelta(seconds=30), # Execution timeout
    eta=datetime.now() + timedelta(hours=1), # Schedule for later
)
```

## Examples

See the `examples/` directory for complete working examples:
- `memory_example.py` - Using in-memory broker/results
- `redis_example.py` - Using Redis with chains

Run examples:

```bash
cd examples
python memory_example.py
python redis_example.py  # Requires Redis running
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=tasqueue --cov-report=html
```

## Architecture

Tasqueue Python uses:
- **asyncio** for concurrency
- **msgpack** for message serialization
- **redis.asyncio** for Redis operations (optional)

The architecture mirrors the Go version while leveraging Python's async/await capabilities.

## Differences from Go Version

1. **Async/await**: All operations are async in Python
2. **Type hints**: Extensive type hints for better IDE support
3. **Pythonic naming**: snake_case instead of camelCase
4. **No NATS**: Currently supports Redis and in-memory (NATS support coming)

## Contributing

Contributions welcome! Please ensure:
- Code follows PEP 8
- All tests pass
- New features include tests
- Documentation is updated

## License

BSD-2-Clause-FreeBSD (same as original Tasqueue)

## Credits

Python port inspired by the original [Tasqueue](https://github.com/kalbhor/tasqueue) by [@kalbhor](https://github.com/kalbhor).
