"""
Tests for Job functionality
"""

import pytest
import asyncio
import json

from tasqueue import Server, ServerOpts, TaskOpts, Job, JobOpts, JobContext
from tasqueue.brokers import MemoryBroker
from tasqueue.results import MemoryResults
from tasqueue import STATUS_DONE, STATUS_FAILED


@pytest.fixture
async def server():
    """Create a test server"""
    broker = MemoryBroker()
    results = MemoryResults()
    srv = Server(ServerOpts(broker=broker, results=results))
    return srv


@pytest.mark.asyncio
async def test_enqueue_job(server):
    """Test basic job enqueueing"""
    async def handler(payload: bytes, ctx: JobContext):
        data = json.loads(payload)
        await ctx.save(json.dumps({'result': data['value'] * 2}).encode())

    await server.register_task("test", handler, TaskOpts())

    # Start server
    task = asyncio.create_task(server.start())

    # Enqueue job
    job = Job.create("test", json.dumps({'value': 5}).encode())
    job_id = await server.enqueue(job)

    # Wait for processing
    await asyncio.sleep(1)

    # Check result
    result = await server.get_result(job_id)
    assert json.loads(result)['result'] == 10

    # Get job message
    job_msg = await server.get_job(job_id)
    assert job_msg.meta.status == STATUS_DONE

    # Cleanup
    await server.stop()
    task.cancel()


@pytest.mark.asyncio
async def test_job_failure_and_retry(server):
    """Test job failure and retry mechanism"""
    attempt_count = {'count': 0}

    async def failing_handler(payload: bytes, ctx: JobContext):
        attempt_count['count'] += 1
        if attempt_count['count'] < 3:
            raise ValueError("Simulated failure")
        await ctx.save(b"success")

    await server.register_task("failing", failing_handler, TaskOpts())

    # Start server
    task = asyncio.create_task(server.start())

    # Enqueue job with retries
    job = Job.create("failing", b"test", JobOpts(max_retries=3))
    job_id = await server.enqueue(job)

    # Wait for retries
    await asyncio.sleep(2)

    # Should succeed on third attempt
    job_msg = await server.get_job(job_id)
    assert job_msg.meta.status == STATUS_DONE
    assert job_msg.meta.retried == 2

    # Cleanup
    await server.stop()
    task.cancel()


@pytest.mark.asyncio
async def test_job_max_retries_exceeded(server):
    """Test job failing after max retries"""
    async def always_failing_handler(payload: bytes, ctx: JobContext):
        raise ValueError("Always fails")

    await server.register_task("always_fail", always_failing_handler, TaskOpts())

    # Start server
    task = asyncio.create_task(server.start())

    # Enqueue job with limited retries
    job = Job.create("always_fail", b"test", JobOpts(max_retries=2))
    job_id = await server.enqueue(job)

    # Wait for all retries
    await asyncio.sleep(2)

    # Should be failed
    job_msg = await server.get_job(job_id)
    assert job_msg.meta.status == STATUS_FAILED
    assert job_msg.meta.retried == 2

    # Cleanup
    await server.stop()
    task.cancel()


@pytest.mark.asyncio
async def test_job_timeout(server):
    """Test job timeout"""
    async def slow_handler(payload: bytes, ctx: JobContext):
        await asyncio.sleep(5)  # Sleep longer than timeout

    await server.register_task("slow", slow_handler, TaskOpts())

    # Start server
    task = asyncio.create_task(server.start())

    # Enqueue job with short timeout
    from datetime import timedelta
    job = Job.create("slow", b"test", JobOpts(
        timeout=timedelta(seconds=1),
        max_retries=0
    ))
    job_id = await server.enqueue(job)

    # Wait for timeout
    await asyncio.sleep(3)

    # Should be failed due to timeout
    job_msg = await server.get_job(job_id)
    assert job_msg.meta.status == STATUS_FAILED

    # Cleanup
    await server.stop()
    task.cancel()


@pytest.mark.asyncio
async def test_on_success_jobs(server):
    """Test OnSuccess job chaining"""
    results = []

    async def handler1(payload: bytes, ctx: JobContext):
        results.append('job1')
        await ctx.save(b"result1")

    async def handler2(payload: bytes, ctx: JobContext):
        results.append('job2')
        # Should have access to previous result
        assert ctx.meta.prev_job_result == b"result1"
        await ctx.save(b"result2")

    await server.register_task("job1", handler1, TaskOpts())
    await server.register_task("job2", handler2, TaskOpts())

    # Start server
    task = asyncio.create_task(server.start())

    # Create jobs with OnSuccess
    job2 = Job.create("job2", b"", JobOpts())
    job1 = Job.create("job1", b"", JobOpts())
    job1.on_success.append(job2)

    # Enqueue
    job_id = await server.enqueue(job1)

    # Wait for both jobs
    await asyncio.sleep(2)

    # Both jobs should have executed
    assert results == ['job1', 'job2']

    # Cleanup
    await server.stop()
    task.cancel()
