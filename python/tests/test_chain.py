"""
Tests for Chain functionality
"""

import pytest
import asyncio
import json

from tasqueue import Server, ServerOpts, TaskOpts, Job, JobOpts, JobContext, Chain, ChainOpts
from tasqueue.brokers import MemoryBroker
from tasqueue.results import MemoryResults
from tasqueue import STATUS_DONE, STATUS_FAILED


@pytest.fixture
async def server():
    """Create a test server"""
    broker = MemoryBroker()
    results = MemoryResults()
    srv = Server(ServerOpts(broker=broker, results=results))

    # Register handlers that pass data along
    async def add_handler(payload: bytes, ctx: JobContext):
        data = json.loads(payload) if payload else {}
        value = data.get('value', 0)

        # Use previous result if available
        if ctx.meta.prev_job_result:
            prev_data = json.loads(ctx.meta.prev_job_result)
            value = prev_data.get('value', value)

        result = value + 10
        await ctx.save(json.dumps({'value': result}).encode())

    await srv.register_task("add", add_handler, TaskOpts())
    return srv


@pytest.mark.asyncio
async def test_chain_success(server):
    """Test successful chain execution"""
    # Start server
    task = asyncio.create_task(server.start())

    # Create chain of jobs
    jobs = [
        Job.create("add", json.dumps({'value': 5}).encode(), JobOpts()),  # 5 + 10 = 15
        Job.create("add", b"", JobOpts()),                                 # 15 + 10 = 25
        Job.create("add", b"", JobOpts()),                                 # 25 + 10 = 35
    ]

    chain = Chain.create(jobs, ChainOpts())
    chain_id = await server.enqueue_chain(chain)

    # Wait for chain to complete
    for _ in range(10):
        await asyncio.sleep(1)
        chain_msg = await server.get_chain(chain_id)
        if chain_msg.meta.status == STATUS_DONE:
            break

    # Chain should be successful
    assert chain_msg.meta.status == STATUS_DONE
    assert len(chain_msg.meta.prev_jobs) == 3

    # Check final result
    last_job_id = chain_msg.meta.prev_jobs[-1]
    result = await server.get_result(last_job_id)
    assert json.loads(result)['value'] == 35

    # Cleanup
    await server.stop()
    task.cancel()


@pytest.mark.asyncio
async def test_chain_minimum_jobs():
    """Test that chains require at least 2 jobs"""
    jobs = [Job.create("test", b"", JobOpts())]

    with pytest.raises(ValueError, match="minimum 2 tasks required"):
        Chain.create(jobs, ChainOpts())
