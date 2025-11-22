"""
Example using Redis broker and results backend
"""

import asyncio
import json
import logging
import os

import sys
sys.path.insert(0, '..')

from tasqueue import Server, ServerOpts, TaskOpts, Job, JobOpts, JobContext, Chain, ChainOpts
from tasqueue.brokers.redis_broker import RedisBroker
from tasqueue.results.redis_results import RedisResults


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Get Redis connection from environment or use defaults
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)


# Example task handlers
async def add_handler(payload: bytes, ctx: JobContext) -> None:
    """Add 10 to a number"""
    data = json.loads(payload)
    value = data.get('value', 0)

    # Check if there's a previous result (in a chain)
    if ctx.meta.prev_job_result:
        prev_data = json.loads(ctx.meta.prev_job_result)
        value = prev_data.get('value', value)

    result = value + 10

    logging.info(f"Add 10: {value} + 10 = {result}")

    # Save result for next job in chain
    await ctx.save(json.dumps({'value': result}).encode())


async def multiply_handler(payload: bytes, ctx: JobContext) -> None:
    """Multiply by 2"""
    data = json.loads(payload)
    value = data.get('value', 0)

    # Check if there's a previous result (in a chain)
    if ctx.meta.prev_job_result:
        prev_data = json.loads(ctx.meta.prev_job_result)
        value = prev_data.get('value', value)

    result = value * 2

    logging.info(f"Multiply by 2: {value} * 2 = {result}")

    # Save result
    await ctx.save(json.dumps({'value': result}).encode())


async def main():
    # Create broker and results backend
    logging.info(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")

    broker = RedisBroker(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD
    )
    results = RedisResults(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD
    )

    # Create server
    server = Server(ServerOpts(
        broker=broker,
        results=results,
    ))

    # Register tasks
    await server.register_task(
        "add",
        add_handler,
        TaskOpts(
            concurrency=2,
            queue="operations"
        )
    )

    await server.register_task(
        "multiply",
        multiply_handler,
        TaskOpts(
            concurrency=2,
            queue="operations"
        )
    )

    # Start server in background
    server_task = asyncio.create_task(server.start())

    # Give server time to start
    await asyncio.sleep(1)

    # Enqueue a chain of jobs
    print("\n=== Enqueueing a chain of jobs ===")
    jobs = [
        Job.create("add", json.dumps({'value': 5}).encode(), JobOpts(queue="operations")),  # 5 + 10 = 15
        Job.create("multiply", json.dumps({}).encode(), JobOpts(queue="operations")),        # 15 * 2 = 30
        Job.create("add", json.dumps({}).encode(), JobOpts(queue="operations")),             # 30 + 10 = 40
    ]

    chain = Chain.create(jobs, ChainOpts())
    chain_id = await server.enqueue_chain(chain)
    print(f"Enqueued chain: {chain_id}")

    # Monitor chain status
    for i in range(10):
        await asyncio.sleep(1)
        chain_msg = await server.get_chain(chain_id)
        print(f"Chain status ({i+1}s): {chain_msg.meta.status}")
        print(f"  Current job: {chain_msg.meta.job_id}")
        print(f"  Completed jobs: {chain_msg.meta.prev_jobs}")

        if chain_msg.meta.status in ["successful", "failed"]:
            break

    # Get final result
    if chain_msg.meta.prev_jobs:
        last_job_id = chain_msg.meta.prev_jobs[-1]
        final_result = await server.get_result(last_job_id)
        print(f"\nFinal result: {json.loads(final_result)}")

    # Cleanup
    await server.stop()
    server_task.cancel()
    await broker.close()
    await results.close()

    print("\n=== Example completed ===")


if __name__ == "__main__":
    asyncio.run(main())
