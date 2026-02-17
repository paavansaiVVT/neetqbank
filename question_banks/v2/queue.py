from __future__ import annotations

import json
from typing import Any

from redis import asyncio as redis_async
from redis.asyncio.client import PubSub

from question_banks.v2.config import get_settings


class RedisQueue:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._client = redis_async.Redis.from_url(settings.redis_url, decode_responses=True)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def enqueue_job(self, job_id: str) -> None:
        await self._client.lpush(self._settings.queue_name, job_id)

    async def enqueue_payload(self, payload: dict[str, Any]) -> None:
        await self._client.lpush(self._settings.queue_name, json.dumps(payload))

    async def dequeue_job(self) -> str | None:
        payload = await self._client.brpop(
            self._settings.queue_name,
            timeout=self._settings.queue_block_timeout_seconds,
        )
        if not payload:
            return None
        _, value = payload
        return value

    async def publish_progress(self, job_id: str, payload: dict[str, Any]) -> None:
        channel = self._settings.progress_channel_prefix + job_id
        await self._client.publish(channel, json.dumps(payload))

    def subscribe_progress(self, job_id: str) -> PubSub:
        channel = self._settings.progress_channel_prefix + job_id
        pubsub = self._client.pubsub()
        return pubsub, channel

    async def close(self) -> None:
        await self._client.aclose()
