from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from question_banks.v2.config import get_settings
from question_banks.v2.queue import RedisQueue
from question_banks.v2.repository import QbankV2Repository
from question_banks.v2.schemas import (
    DraftItemPatchRequest,
    GenerationJobCreateRequest,
    JobStatus,
    PublishRequest,
)

logger = logging.getLogger(__name__)


class QbankV2Service:
    def __init__(self, repository: QbankV2Repository | None = None, queue: RedisQueue | None = None) -> None:
        self._settings = get_settings()
        self._repository = repository or QbankV2Repository()
        self._queue = queue or RedisQueue()
        self._redis_available: bool | None = None
        self._redis_checked_at: float = 0

    async def _check_redis(self) -> bool:
        """Check if Redis is reachable. Re-evaluates every 60 seconds."""
        now = time.monotonic()
        if self._redis_available is not None and (now - self._redis_checked_at) < 60:
            return self._redis_available
        try:
            self._redis_available = await self._queue.ping()
            self._redis_checked_at = now
        except Exception:
            if self._redis_available is not False:
                logger.warning("Redis not available — will use inline processing")
            self._redis_available = False
            self._redis_checked_at = now
        return self._redis_available

    async def create_job(self, request: GenerationJobCreateRequest) -> dict[str, Any]:
        if request.count > self._settings.max_questions_per_job:
            raise ValueError(
                f"count must be <= {self._settings.max_questions_per_job} for this deployment"
            )

        payload = request.model_dump(mode="json")
        job = self._repository.create_job(payload)

        # Determine queue mode
        use_redis = self._settings.queue_mode == "redis"
        if self._settings.queue_mode == "auto":
            use_redis = await self._check_redis()

        if use_redis:
            await self._queue.enqueue_job(job["job_id"])
            logger.info("Job %s enqueued to Redis", job["job_id"])
        else:
            # Inline mode: process in background task (no Redis needed)
            asyncio.ensure_future(self._process_inline(job["job_id"]))
            logger.info("Job %s started inline (no Redis)", job["job_id"])

        return job

    async def _process_inline(self, job_id: str) -> None:
        """Process a job directly without Redis. Used for local dev."""
        try:
            from question_banks.v2.worker import QbankV2Worker

            worker = QbankV2Worker(
                settings=self._settings,
                repository=self._repository,
                queue=self._queue,
            )
            await worker.process_job(job_id)
        except asyncio.CancelledError:
            logger.warning("Inline processing cancelled for job %s (server reload?)", job_id)
            # Don't mark as failed — the job can be recovered on restart
        except Exception:
            logger.exception("Inline processing failed for job %s", job_id)
            # Ensure the job is marked as failed so it doesn't stay stuck
            try:
                self._repository.set_job_status(
                    job_id, JobStatus.failed,
                    error={"message": "Inline processing failed unexpectedly"}
                )
            except Exception:
                pass

    async def restart_job(self, job_id: str) -> dict[str, Any]:
        """Reset a failed/stuck job to queued and re-process it."""
        # Reset status to queued
        self._repository.set_job_status(job_id, JobStatus.queued, error=None)
        # Re-trigger inline processing
        asyncio.ensure_future(self._process_inline(job_id))
        logger.info("Job %s restarted inline", job_id)
        return self._repository.get_job(job_id)

    async def recover_stuck_jobs(self, max_age_minutes: int = 5) -> int:
        """Find jobs stuck in 'running' for too long and re-process them inline."""
        try:
            stuck_jobs = self._repository.find_stuck_jobs(
                max_age_minutes=max_age_minutes
            )
            if not stuck_jobs:
                return 0

            logger.info("Found %d stuck jobs — recovering", len(stuck_jobs))
            for job_id in stuck_jobs:
                logger.info("Re-processing stuck job %s", job_id)
                asyncio.ensure_future(self._process_inline(job_id))
            return len(stuck_jobs)
        except Exception:
            logger.exception("Failed to recover stuck jobs")
            return 0

    def subscribe_job(self, job_id: str):
        return self._queue.subscribe_progress(job_id)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self._repository.get_job(job_id)

    def list_jobs(self, limit: int = 20, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        return self._repository.list_jobs(limit, offset)

    def list_items(
        self,
        job_id: str,
        qc_status: str | None,
        review_status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        return self._repository.list_items(job_id, qc_status, review_status, offset, limit)

    def update_item(self, job_id: str, item_id: int, patch: DraftItemPatchRequest) -> dict[str, Any]:
        return self._repository.update_item(job_id, item_id, patch)

    def bulk_update_items(self, job_id: str, item_ids: list[int], patch: DraftItemPatchRequest) -> dict[str, Any]:
        return self._repository.bulk_update_items(job_id, item_ids, patch)

    def publish_items(self, job_id: str, request: PublishRequest) -> dict[str, Any]:
        return self._repository.publish_items(job_id, request)

    def list_subjects(self) -> list[str]:
        return self._repository.list_subjects()

    def list_chapters(self, subject: str | None = None) -> list[str]:
        normalized_subject = subject.strip() if subject else None
        return self._repository.list_chapters(normalized_subject)

    def list_topics(self, subject: str | None = None, chapter: str | None = None) -> list[str]:
        normalized_subject = subject.strip() if subject else None
        normalized_chapter = chapter.strip() if chapter else None
        return self._repository.list_topics(normalized_subject, normalized_chapter)

    def search_items(
        self,
        query: str | None = None,
        subject: str | None = None,
        chapter: str | None = None,
        topic: str | None = None,
        difficulty: str | None = None,
        cognitive_level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        return self._repository.search_items(
            query=query,
            subject=subject,
            chapter=chapter,
            topic=topic,
            difficulty=difficulty,
            cognitive_level=cognitive_level,
            limit=limit,
            offset=offset,
        )

    async def health(self) -> dict[str, str]:
        try:
            queue_ok = await self._queue.ping()
        except Exception:
            logger.exception("Redis health check failed")
            queue_ok = False

        return {
            "api": "ok",
            "queue": "ok" if queue_ok else "error",
        }

    def get_dashboard_stats(self) -> dict[str, Any]:
        return self._repository.get_dashboard_stats()

    def get_analytics(self, user_id: str | None = None, days: int = 30) -> dict[str, Any]:
        return self._repository.get_analytics(user_id=user_id, days=days)
