"""
Tests for Group functionality
"""

import pytest
import asyncio
import json

from tasqueue import Server, ServerOpts, TaskOpts, Job, JobOpts, JobContext, Group, GroupOpts
from tasqueue.brokers import MemoryBroker
from tasqueue.results import MemoryResults
from tasqueue import STATUS_DONE, STATUS_FAILED


@pytest.fixture
async def server():
    """Create a test server"""
    broker = MemoryBroker()
    results = MemoryResults()
    srv = Server(ServerOpts(broker=broker, results=results))

    # Register a test handler
    async def handler(payload: bytes, ctx: JobContext):
        data = json.loads(payload)
        if data.get('should_fail'):
            raise ValueError("Job failed")
        await ctx.save(json.dumps({'processed': True}).encode())

    await srv.register_task("test", handler, TaskOpts())
    return srv


@pytest.mark.asyncio
async def test_group_success(server):
    """Test successful group execution"""
    # Start server
    task = asyncio.create_task(server.start())

    # Create group of jobs
    jobs = [
        Job.create("test", json.dumps({'value': i}).encode(), JobOpts())
        for i in range(3)
    ]

    group = Group.create(jobs, GroupOpts())
    group_id = await server.enqueue_group(group)

    # Wait for all jobs to complete
    await asyncio.sleep(2)

    # Check group status
    group_msg = await server.get_group(group_id)
    assert group_msg.meta.status == STATUS_DONE

    # All jobs should be successful
    for job_status in group_msg.meta.job_status.values():
        assert job_status == STATUS_DONE

    # Cleanup
    await server.stop()
    task.cancel()


@pytest.mark.asyncio
async def test_group_with_failure(server):
    """Test group with one failing job"""
    # Start server
    task = asyncio.create_task(server.start())

    # Create group with one failing job
    jobs = [
        Job.create("test", json.dumps({'value': 1}).encode(), JobOpts()),
        Job.create("test", json.dumps({'should_fail': True}).encode(), JobOpts(max_retries=0)),
        Job.create("test", json.dumps({'value': 3}).encode(), JobOpts()),
    ]

    group = Group.create(jobs, GroupOpts())
    group_id = await server.enqueue_group(group)

    # Wait for all jobs
    await asyncio.sleep(2)

    # Group should be failed
    group_msg = await server.get_group(group_id)
    assert group_msg.meta.status == STATUS_FAILED

    # Cleanup
    await server.stop()
    task.cancel()
