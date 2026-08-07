"""
Application Background Jobs — Scheduler for long-running work.

Moves periodic tasks out of request handlers to keep the API responsive.
Runs as daemon threads alongside the main event loop.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from backend.container import Container

logger = logging.getLogger("vigilant.jobs.scheduler")


class BackgroundJob:
    """Definition of a recurring background job."""

    def __init__(
        self,
        name: str,
        func: Callable[[], None],
        interval_seconds: float,
        run_immediately: bool = False,
    ) -> None:
        self.name = name
        self.func = func
        self.interval = interval_seconds
        self.run_immediately = run_immediately
        self.last_run: float = 0.0
        self.run_count: int = 0
        self.error_count: int = 0


class JobScheduler:
    """
    Simple background job scheduler running as a daemon thread.

    Jobs execute sequentially in a single thread to avoid
    resource contention with the async event loop.
    """

    def __init__(self) -> None:
        self._jobs: List[BackgroundJob] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tick_interval = 1.0  # Check jobs every second

    def register(
        self,
        name: str,
        func: Callable[[], None],
        interval_seconds: float,
        run_immediately: bool = False,
    ) -> None:
        """Register a recurring background job."""
        self._jobs.append(
            BackgroundJob(name, func, interval_seconds, run_immediately)
        )
        logger.info(
            "Registered job '%s' (every %ds)", name, int(interval_seconds)
        )

    def start(self) -> None:
        """Start the scheduler thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="job-scheduler"
        )
        self._thread.start()
        logger.info("Job scheduler started with %d jobs", len(self._jobs))

    def stop(self) -> None:
        """Stop the scheduler thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Job scheduler stopped")

    def _run_loop(self) -> None:
        """Main scheduler loop."""
        # Run immediate jobs first
        for job in self._jobs:
            if job.run_immediately:
                self._execute_job(job)

        while not self._stop_event.is_set():
            now = time.time()
            for job in self._jobs:
                if now - job.last_run >= job.interval:
                    self._execute_job(job)
            self._stop_event.wait(self._tick_interval)

    def _execute_job(self, job: BackgroundJob) -> None:
        """Execute a single job with error handling."""
        try:
            job.func()
            job.last_run = time.time()
            job.run_count += 1
        except Exception:
            job.error_count += 1
            logger.exception("Job '%s' failed (errors: %d)", job.name, job.error_count)

    def get_status(self) -> List[dict]:
        """Get status of all registered jobs."""
        return [
            {
                "name": j.name,
                "interval_seconds": j.interval,
                "run_count": j.run_count,
                "error_count": j.error_count,
                "last_run": j.last_run,
            }
            for j in self._jobs
        ]
