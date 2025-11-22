"""
Example using in-memory broker and results backend
"""

import asyncio
import json
import logging

import sys
sys.path.insert(0, '..')

from tasqueue import Server, ServerOpts, TaskOpts, Job, JobOpts, JobContext, Group, GroupOpts
from tasqueue.brokers import MemoryBroker
from tasqueue.results import MemoryResults


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Example task handlers
async def sum_handler(payload: bytes, ctx: JobContext) -> None:
    """Sum two numbers"""
    data = json.loads(payload)
    result = data['arg1'] + data['arg2']

    logging.info(f"Sum: {data['arg1']} + {data['arg2']} = {result}")

    # Save result
    await ctx.save(json.dumps({'result': result}).encode())


async def multiply_handler(payload: bytes, ctx: JobContext) -> None:
    """Multiply two numbers"""
    data = json.loads(payload)
    result = data['arg1'] * data['arg2']

    logging.info(f"Multiply: {data['arg1']} * {data['arg2']} = {result}")

    # Save result
    await ctx.save(json.dumps({'result': result}).encode())


async def main():
    # Create broker and results backend
    broker = MemoryBroker()
    results = MemoryResults()

    # Create server
    server = Server(ServerOpts(
        broker=broker,
        results=results,
    ))

    # Register tasks
    await server.register_task(
        "sum",
        sum_handler,
        TaskOpts(
            concurrency=2,
            queue="math_ops"
        )
    )

    await server.register_task(
        "multiply",
        multiply_handler,
        TaskOpts(
            concurrency=2,
            queue="math_ops"
        )
    )

    # Start server in background
    server_task = asyncio.create_task(server.start())

    # Give server time to start
    await asyncio.sleep(0.5)

    # Enqueue individual jobs
    print("\n=== Enqueueing individual jobs ===")
    job1 = Job.create("sum", json.dumps({'arg1': 5, 'arg2': 3}).encode(), JobOpts())
    job_id = await server.enqueue(job1)
    print(f"Enqueued sum job: {job_id}")

    job2 = Job.create("multiply", json.dumps({'arg1': 4, 'arg2': 7}).encode(), JobOpts())
    job_id2 = await server.enqueue(job2)
    print(f"Enqueued multiply job: {job_id2}")

    # Wait for jobs to complete
    await asyncio.sleep(2)

    # Get results
    result1 = await server.get_result(job_id)
    print(f"Result 1: {json.loads(result1)}")

    result2 = await server.get_result(job_id2)
    print(f"Result 2: {json.loads(result2)}")

    # Enqueue a group
    print("\n=== Enqueueing a group of jobs ===")
    jobs = [
        Job.create("sum", json.dumps({'arg1': i, 'arg2': i+1}).encode(), JobOpts())
        for i in range(3)
    ]
    group = Group.create(jobs, GroupOpts())
    group_id = await server.enqueue_group(group)
    print(f"Enqueued group: {group_id}")

    # Wait and check group status
    await asyncio.sleep(2)
    group_msg = await server.get_group(group_id)
    print(f"Group status: {group_msg.meta.status}")
    print(f"Job statuses: {group_msg.meta.job_status}")

    # Stop server
    await server.stop()
    server_task.cancel()

    print("\n=== Example completed ===")


if __name__ == "__main__":
    asyncio.run(main())
