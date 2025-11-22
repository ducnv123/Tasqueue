"""
Server implementation - the main component for task processing
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Callable, Optional, Any
from datetime import datetime
import os

from .interfaces import Broker, Results
from .job import Job, JobContext, JobMessage, Meta, default_meta, JobOpts
from .group import Group, GroupMessage, GroupMeta, get_group_status
from .chain import Chain, ChainMessage, ChainMeta
from .constants import (
    STATUS_QUEUED,
    STATUS_PROCESSING,
    STATUS_FAILED,
    STATUS_DONE,
    STATUS_RETRYING,
    JOB_PREFIX,
    GROUP_PREFIX,
    CHAIN_PREFIX,
)

# Handler is a function that processes job payload
Handler = Callable[[bytes, JobContext], Any]


@dataclass
class TaskOpts:
    """Task configuration options"""
    concurrency: int = 0
    queue: str = "tasqueue:tasks"
    success_cb: Optional[Callable[[JobContext], None]] = None
    processing_cb: Optional[Callable[[JobContext], None]] = None
    retrying_cb: Optional[Callable[[JobContext, Exception], None]] = None
    failed_cb: Optional[Callable[[JobContext, Exception], None]] = None


@dataclass
class Task:
    """Task represents a pre-registered job handler with callbacks"""
    name: str
    handler: Handler
    opts: TaskOpts


@dataclass
class ServerOpts:
    """Server configuration options"""
    broker: Broker
    results: Results
    logger: Optional[logging.Logger] = None


class NotFoundError(Exception):
    """Raised when a result is not found"""
    pass


class Server:
    """
    Server is the main component that coordinates task processing.
    """

    def __init__(self, opts: ServerOpts):
        if not opts.broker:
            raise ValueError("broker is required")
        if not opts.results:
            raise ValueError("results is required")

        self.broker = opts.broker
        self.results = opts.results
        self.logger = opts.logger or logging.getLogger(__name__)

        self._tasks: Dict[str, Task] = {}
        self._queues: Dict[str, int] = {}
        self._default_conc = os.cpu_count() or 4
        self._running = False
        self._task_futures = []

    async def register_task(
        self,
        name: str,
        handler: Handler,
        opts: Optional[TaskOpts] = None
    ) -> None:
        """
        Register a task handler.

        Args:
            name: Task name
            handler: Handler function
            opts: Task options

        Raises:
            ValueError: If queue concurrency conflicts with existing queue
        """
        if opts is None:
            opts = TaskOpts()

        if not opts.queue:
            opts.queue = "tasqueue:tasks"

        if opts.concurrency <= 0:
            opts.concurrency = self._default_conc

        # Check if queue already exists with different concurrency
        if opts.queue in self._queues:
            existing_conc = self._queues[opts.queue]
            if opts.concurrency != existing_conc:
                raise ValueError(
                    f"queue '{opts.queue}' already defined with {existing_conc} concurrency"
                )
        else:
            self._queues[opts.queue] = opts.concurrency

        task = Task(name=name, handler=handler, opts=opts)
        self._tasks[name] = task

        self.logger.debug(f"Registered task '{name}' on queue '{opts.queue}'")

    async def enqueue(self, job: Job) -> str:
        """
        Enqueue a job for processing.

        Args:
            job: Job to enqueue

        Returns:
            Job ID
        """
        return await self._enqueue_with_meta(job, default_meta(job.opts))

    async def _enqueue_with_meta(self, job: Job, meta: Meta) -> str:
        """Enqueue a job with specific metadata"""
        # Handle scheduled jobs
        if job.opts.schedule:
            # For scheduled jobs, we would use a cron scheduler
            # For simplicity in this implementation, we'll skip cron parsing
            pass

        msg = JobMessage(meta=meta, job=job)

        # Set job status in results store
        await self._set_status_started(msg)

        # Enqueue the message
        if job.opts.eta:
            await self.broker.enqueue_scheduled(
                msg.to_bytes(),
                meta.queue,
                job.opts.eta
            )
        else:
            await self.broker.enqueue(msg.to_bytes(), meta.queue)

        return meta.id

    async def get_job(self, job_id: str) -> JobMessage:
        """
        Get job message by ID.

        Args:
            job_id: Job ID

        Returns:
            JobMessage

        Raises:
            NotFoundError: If job not found
        """
        try:
            data = await self.results.get(JOB_PREFIX + job_id)
            return JobMessage.from_bytes(data)
        except Exception as e:
            if self.results.is_not_found_error(e):
                raise NotFoundError(f"Job {job_id} not found")
            raise

    async def get_result(self, job_id: str) -> bytes:
        """
        Get job result by ID.

        Args:
            job_id: Job ID

        Returns:
            Result bytes

        Raises:
            NotFoundError: If result not found
        """
        try:
            return await self.results.get(job_id)
        except Exception as e:
            if self.results.is_not_found_error(e):
                raise NotFoundError(f"Result {job_id} not found")
            raise

    async def delete_job(self, job_id: str) -> None:
        """Delete job metadata"""
        await self.results.delete_job(job_id)

    async def get_failed(self) -> list[str]:
        """Get list of failed job IDs"""
        return await self.results.get_failed()

    async def get_success(self) -> list[str]:
        """Get list of successful job IDs"""
        return await self.results.get_success()

    async def get_tasks(self) -> list[str]:
        """Get list of registered task names"""
        return list(self._tasks.keys())

    async def enqueue_group(self, group: Group) -> str:
        """
        Enqueue a group of jobs for parallel execution.

        Args:
            group: Group to enqueue

        Returns:
            Group ID
        """
        import uuid as uuid_lib

        if not group.opts.id:
            group.opts.id = str(uuid_lib.uuid4())

        msg = GroupMessage(
            meta=GroupMeta(
                id=group.opts.id,
                status=STATUS_PROCESSING,
                job_status={}
            ),
            group=group
        )

        # Enqueue all jobs
        for job in group.jobs:
            job_id = await self.enqueue(job)
            msg.meta.job_status[job_id] = STATUS_QUEUED

        # Store group message
        await self._set_group_message(msg)

        return msg.meta.id

    async def get_group(self, group_id: str) -> GroupMessage:
        """
        Get group status.

        Args:
            group_id: Group ID

        Returns:
            GroupMessage
        """
        msg = await self._get_group_message(group_id)

        # If already in final state, return as is
        if msg.meta.status in (STATUS_DONE, STATUS_FAILED):
            return msg

        # Update job statuses
        updated_status = {}
        for job_id, status in msg.meta.job_status.items():
            if status in (STATUS_DONE, STATUS_FAILED):
                updated_status[job_id] = status
            else:
                # Re-check status
                try:
                    job_msg = await self.get_job(job_id)
                    updated_status[job_id] = job_msg.meta.status
                except NotFoundError:
                    updated_status[job_id] = status

        msg.meta.job_status = updated_status
        msg.meta.status = get_group_status(updated_status)

        # Update stored message
        await self._set_group_message(msg)

        return msg

    async def enqueue_chain(self, chain: Chain) -> str:
        """
        Enqueue a chain of jobs for sequential execution.

        Args:
            chain: Chain to enqueue

        Returns:
            Chain ID
        """
        import uuid as uuid_lib

        if not chain.opts.id:
            chain.opts.id = str(uuid_lib.uuid4())

        msg = ChainMessage(
            meta=ChainMeta(
                id=chain.opts.id,
                status=STATUS_PROCESSING,
            )
        )

        # Enqueue the first job
        root = chain.jobs[0]
        job_id = await self.enqueue(root)
        msg.meta.job_id = job_id

        # Store chain message
        await self._set_chain_message(msg)

        return msg.meta.id

    async def get_chain(self, chain_id: str) -> ChainMessage:
        """
        Get chain status.

        Args:
            chain_id: Chain ID

        Returns:
            ChainMessage
        """
        msg = await self._get_chain_message(chain_id)

        # If already in final state, return as is
        if msg.meta.status in (STATUS_DONE, STATUS_FAILED):
            return msg

        # Check current job status
        try:
            curr_job = await self.get_job(msg.meta.job_id)
        except NotFoundError:
            return msg

        # Update chain based on current job status
        while True:
            if curr_job.meta.status == STATUS_FAILED:
                msg.meta.prev_jobs.append(curr_job.meta.id)
                msg.meta.status = STATUS_FAILED
                break
            elif curr_job.meta.status in (STATUS_QUEUED, STATUS_PROCESSING, STATUS_RETRYING):
                msg.meta.status = STATUS_PROCESSING
                break
            elif curr_job.meta.status == STATUS_DONE:
                msg.meta.prev_jobs.append(curr_job.meta.id)
                if not curr_job.meta.on_success_ids:
                    # Chain complete
                    msg.meta.status = STATUS_DONE
                    break
                else:
                    # Move to next job
                    try:
                        curr_job = await self.get_job(curr_job.meta.on_success_ids[0])
                        msg.meta.job_id = curr_job.meta.id
                    except NotFoundError:
                        break
            else:
                break

        # Update stored message
        await self._set_chain_message(msg)

        return msg

    async def start(self) -> None:
        """
        Start the server and begin processing jobs.
        This is a blocking call that runs until interrupted.
        """
        self._running = True
        self.logger.info("Starting Tasqueue server...")

        # Start consumers and processors for each queue
        for queue, concurrency in self._queues.items():
            self.logger.info(f"Starting queue '{queue}' with concurrency {concurrency}")

            # Create work queue for this queue
            work_queue = asyncio.Queue()

            # Start consumer
            consumer_task = asyncio.create_task(
                self._consume(queue, work_queue)
            )
            self._task_futures.append(consumer_task)

            # Start processors
            for i in range(concurrency):
                processor_task = asyncio.create_task(
                    self._process(work_queue)
                )
                self._task_futures.append(processor_task)

        # Wait for all tasks
        try:
            await asyncio.gather(*self._task_futures)
        except asyncio.CancelledError:
            self.logger.info("Server shutdown requested")
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop the server"""
        self.logger.info("Stopping server...")
        self._running = False
        for task in self._task_futures:
            task.cancel()
        await asyncio.gather(*self._task_futures, return_exceptions=True)

    async def _consume(self, queue: str, work_queue: asyncio.Queue) -> None:
        """Consume messages from broker and put them in work queue"""
        self.logger.debug(f"Starting consumer for queue '{queue}'")

        async def callback(msg: bytes):
            await work_queue.put(msg)

        await self.broker.consume(queue, callback)

    async def _process(self, work_queue: asyncio.Queue) -> None:
        """Process jobs from work queue"""
        self.logger.debug("Starting processor")

        while self._running:
            try:
                # Get work with timeout to allow shutdown
                work = await asyncio.wait_for(
                    work_queue.get(),
                    timeout=1.0
                )

                # Decode message
                try:
                    msg = JobMessage.from_bytes(work)
                except Exception as e:
                    self.logger.error(f"Error unmarshalling task: {e}")
                    continue

                # Get task handler
                if msg.job.task not in self._tasks:
                    self.logger.error(f"Handler '{msg.job.task}' not found")
                    continue

                task = self._tasks[msg.job.task]

                # Set status to processing
                await self._set_status_processing(msg)

                # Execute job
                try:
                    await self._exec_job(msg, task)
                except Exception as e:
                    self.logger.error(f"Error executing job: {e}")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error in processor: {e}")

    async def _exec_job(self, msg: JobMessage, task: Task) -> None:
        """Execute a job"""
        # Create job context
        job_ctx = JobContext(meta=msg.meta, results_store=self.results)

        # Call processing callback
        if task.opts.processing_cb:
            try:
                task.opts.processing_cb(job_ctx)
            except Exception as e:
                self.logger.error(f"Error in processing callback: {e}")

        # Execute handler with timeout
        err = None
        try:
            if msg.job.opts.timeout:
                await asyncio.wait_for(
                    task.handler(msg.job.payload, job_ctx),
                    timeout=msg.job.opts.timeout.total_seconds()
                )
            else:
                await task.handler(msg.job.payload, job_ctx)
        except asyncio.TimeoutError:
            err = TimeoutError("Job execution timeout")
        except Exception as e:
            err = e

        # Handle error
        if err:
            msg.meta.prev_err = str(err)

            # Check if we should retry
            if msg.meta.retried < msg.meta.max_retry:
                if task.opts.retrying_cb:
                    try:
                        task.opts.retrying_cb(job_ctx, err)
                    except Exception as e:
                        self.logger.error(f"Error in retrying callback: {e}")

                await self._retry_job(msg)
                return
            else:
                # Max retries reached
                if task.opts.failed_cb:
                    try:
                        task.opts.failed_cb(job_ctx, err)
                    except Exception as e:
                        self.logger.error(f"Error in failed callback: {e}")

                # Enqueue OnError jobs
                if msg.job.on_error:
                    for error_job in msg.job.on_error:
                        try:
                            error_meta = default_meta(error_job.opts)
                            await self._enqueue_with_meta(error_job, error_meta)
                        except Exception as e:
                            self.logger.error(f"Error enqueueing OnError job: {e}")

                await self._set_status_failed(msg)
                return

        # Success case
        if task.opts.success_cb:
            try:
                task.opts.success_cb(job_ctx)
            except Exception as e:
                self.logger.error(f"Error in success callback: {e}")

        # Enqueue OnSuccess jobs
        if msg.job.on_success:
            for success_job in msg.job.on_success:
                try:
                    success_meta = default_meta(success_job.opts)

                    # Get previous job result
                    try:
                        success_meta.prev_job_result = await self.get_result(msg.meta.id)
                    except NotFoundError:
                        success_meta.prev_job_result = None

                    success_id = await self._enqueue_with_meta(success_job, success_meta)
                    msg.meta.on_success_ids.append(success_id)
                except Exception as e:
                    self.logger.error(f"Error enqueueing OnSuccess job: {e}")

        await self._set_status_done(msg)

    async def _retry_job(self, msg: JobMessage) -> None:
        """Retry a job"""
        msg.meta.retried += 1
        await self._set_status_retrying(msg)
        await self.broker.enqueue(msg.to_bytes(), msg.meta.queue)

    async def _set_status_started(self, msg: JobMessage) -> None:
        """Set job status to started"""
        msg.meta.processed_at = datetime.now()
        msg.meta.status = STATUS_QUEUED
        await self._set_job_message(msg)

    async def _set_status_processing(self, msg: JobMessage) -> None:
        """Set job status to processing"""
        msg.meta.processed_at = datetime.now()
        msg.meta.status = STATUS_PROCESSING
        await self._set_job_message(msg)

    async def _set_status_done(self, msg: JobMessage) -> None:
        """Set job status to done"""
        msg.meta.processed_at = datetime.now()
        msg.meta.status = STATUS_DONE
        await self.results.set_success(msg.meta.id)
        await self._set_job_message(msg)

    async def _set_status_failed(self, msg: JobMessage) -> None:
        """Set job status to failed"""
        msg.meta.processed_at = datetime.now()
        msg.meta.status = STATUS_FAILED
        await self.results.set_failed(msg.meta.id)
        await self._set_job_message(msg)

    async def _set_status_retrying(self, msg: JobMessage) -> None:
        """Set job status to retrying"""
        msg.meta.processed_at = datetime.now()
        msg.meta.status = STATUS_RETRYING
        await self._set_job_message(msg)

    async def _set_job_message(self, msg: JobMessage) -> None:
        """Store job message in results"""
        await self.results.set(JOB_PREFIX + msg.meta.id, msg.to_bytes())

    async def _set_group_message(self, msg: GroupMessage) -> None:
        """Store group message in results"""
        await self.results.set(GROUP_PREFIX + msg.meta.id, msg.to_bytes())

    async def _get_group_message(self, group_id: str) -> GroupMessage:
        """Get group message from results"""
        data = await self.results.get(GROUP_PREFIX + group_id)
        return GroupMessage.from_bytes(data)

    async def _set_chain_message(self, msg: ChainMessage) -> None:
        """Store chain message in results"""
        await self.results.set(CHAIN_PREFIX + msg.meta.id, msg.to_bytes())

    async def _get_chain_message(self, chain_id: str) -> ChainMessage:
        """Get chain message from results"""
        data = await self.results.get(CHAIN_PREFIX + chain_id)
        return ChainMessage.from_bytes(data)
