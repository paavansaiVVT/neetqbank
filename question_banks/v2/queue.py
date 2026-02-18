from __future__ import annotations

import json
from typing import Any

from redis import asyncio as redis_async
from redis.asyncio.client import PubSub

from question_banks.v2.config import get_settings


import logging

logger = logging.getLogger(__name__)


class RedisQueue:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        try:
            self._client = redis_async.Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception as e:
            logger.warning("Failed to initialize Redis client (DNS error?): %s", e)
            self._client = None

    async def ping(self) -> bool:
        if not self._client:
            return False
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def enqueue_job(self, job_id: str) -> None:
        if not self._client:
            raise RuntimeError("Redis client is not initialized")
        await self._client.lpush(self._settings.queue_name, job_id)

    async def enqueue_payload(self, payload: dict[str, Any]) -> None:
        if not self._client:
            raise RuntimeError("Redis client is not initialized")
        await self._client.lpush(self._settings.queue_name, json.dumps(payload))

    async def dequeue_job(self) -> str | None:
        if not self._client:
            return None
        try:
            payload = await self._client.brpop(
                self._settings.queue_name,
                timeout=self._settings.queue_block_timeout_seconds,
            )
            if not payload:
                return None
            _, value = payload
            return value
        except Exception:
            return None

    async def publish_progress(self, job_id: str, payload: dict[str, Any]) -> None:
        if not self._client:
            return
        channel = self._settings.progress_channel_prefix + job_id
        try:
            await self._client.publish(channel, json.dumps(payload))
        except Exception:
            pass

    def subscribe_progress(self, job_id: str) -> PubSub:
        if not self._client:
            raise RuntimeError("Redis client is not initialized")
        channel = self._settings.progress_channel_prefix + job_id
        pubsub = self._client.pubsub()
        return pubsub, channel

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
