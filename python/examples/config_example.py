"""
Example using configuration file (config.yaml)
"""

import asyncio
import json
import logging
import sys
sys.path.insert(0, '..')

from tasqueue import Server, ServerOpts, TaskOpts, Job, JobOpts, JobContext, Group, GroupOpts
from tasqueue.config import init_config, get_config
from tasqueue.factory import create_broker_from_config, create_results_from_config


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
    # Initialize config from YAML file
    # You can specify environment: 'development', 'production', 'testing'
    config = init_config('../config.yaml', env='development')

    print(f"Running in {config.environment} environment")
    print(f"Broker type: {config.get('broker.type')}")
    print(f"Results type: {config.get('results.type')}")

    # Configure logging from config
    log_level = config.get('server.log_level', 'INFO')
    log_format = config.get('server.log_format')
    logging.basicConfig(level=log_level, format=log_format)

    # Create broker and results from config
    broker = create_broker_from_config()
    results = create_results_from_config()

    # Create server
    server = Server(ServerOpts(
        broker=broker,
        results=results,
    ))

    # Get default concurrency from config
    default_conc = config.get('server.default_concurrency', 4)

    # Register tasks with config-driven concurrency
    await server.register_task(
        "sum",
        sum_handler,
        TaskOpts(concurrency=default_conc)
    )

    await server.register_task(
        "multiply",
        multiply_handler,
        TaskOpts(concurrency=default_conc)
    )

    # Start server in background
    server_task = asyncio.create_task(server.start())

    # Give server time to start
    await asyncio.sleep(0.5)

    # Enqueue jobs with defaults from config
    job_defaults = config.get_job_defaults()
    print(f"\nJob defaults: max_retries={job_defaults.get('max_retries')}, "
          f"timeout={job_defaults.get('timeout_seconds')}s")

    print("\n=== Enqueueing jobs ===")
    job1 = Job.create("sum", json.dumps({'arg1': 10, 'arg2': 20}).encode(), JobOpts())
    job_id1 = await server.enqueue(job1)
    print(f"Enqueued sum job: {job_id1}")

    job2 = Job.create("multiply", json.dumps({'arg1': 5, 'arg2': 7}).encode(), JobOpts())
    job_id2 = await server.enqueue(job2)
    print(f"Enqueued multiply job: {job_id2}")

    # Wait for jobs to complete
    await asyncio.sleep(2)

    # Get results
    result1 = await server.get_result(job_id1)
    print(f"\nResult 1: {json.loads(result1)}")

    result2 = await server.get_result(job_id2)
    print(f"Result 2: {json.loads(result2)}")

    # Enqueue a group
    print("\n=== Enqueueing a group ===")
    jobs = [
        Job.create("sum", json.dumps({'arg1': i, 'arg2': i*2}).encode(), JobOpts())
        for i in range(3)
    ]
    group = Group.create(jobs, GroupOpts())
    group_id = await server.enqueue_group(group)
    print(f"Enqueued group: {group_id}")

    # Wait and check group status
    await asyncio.sleep(2)
    group_msg = await server.get_group(group_id)
    print(f"Group status: {group_msg.meta.status}")

    # Stop server
    await server.stop()
    server_task.cancel()

    print("\n=== Example completed ===")
    print("\nConfiguration used:")
    print(f"  Environment: {config.environment}")
    print(f"  Broker: {config.get('broker.type')}")
    print(f"  Default concurrency: {config.get('server.default_concurrency')}")


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════╗
║         Tasqueue - Configuration File Example              ║
╚════════════════════════════════════════════════════════════╝

This example demonstrates:
- Loading configuration from config.yaml
- Environment-specific settings (development/production)
- Using factory functions to create broker/results
- Applying config defaults to jobs and queues

Make sure config.yaml exists in the parent directory!
    """)

    asyncio.run(main())
