from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class QbankV2Settings:
    enabled: bool
    internal_api_key: str
    generation_model_name: str
    qc_model_name: str
    generation_temperature: float
    qc_temperature: float
    redis_url: str
    queue_name: str
    queue_block_timeout_seconds: int
    max_retries: int
    batch_size: int
    max_questions_per_job: int
    database_url: str
    progress_channel_prefix: str
    queue_mode: str  # "redis" or "auto" (auto = try redis, fallback to inline)


@lru_cache(maxsize=1)
def get_settings() -> QbankV2Settings:
    return QbankV2Settings(
        enabled=_to_bool(os.getenv("QBANK_V2_ENABLED"), True),
        internal_api_key=os.getenv("QBANK_V2_INTERNAL_API_KEY", ""),
        generation_model_name=os.getenv("QBANK_V2_GENERATION_MODEL", "gemini-2.5-flash"),
        qc_model_name=os.getenv("QBANK_V2_QC_MODEL", "gemini-2.5-pro"),
        generation_temperature=float(os.getenv("QBANK_V2_GEN_TEMPERATURE", "0.8")),
        qc_temperature=float(os.getenv("QBANK_V2_QC_TEMPERATURE", "0.1")),
        redis_url=os.getenv("QBANK_V2_REDIS_URL", "redis://localhost:6379/0"),
        queue_name=os.getenv("QBANK_V2_QUEUE_NAME", "qbank_v2_jobs"),
        queue_block_timeout_seconds=int(os.getenv("QBANK_V2_QUEUE_BLOCK_TIMEOUT", "5")),
        max_retries=int(os.getenv("QBANK_V2_MAX_RETRIES", "3")),
        batch_size=int(os.getenv("QBANK_V2_BATCH_SIZE", "20")),
        max_questions_per_job=int(os.getenv("QBANK_V2_MAX_QUESTIONS_PER_JOB", "200")),
        database_url=os.getenv("QBANK_V2_DATABASE_URL", os.getenv("DATABASE_URL", "")),
        progress_channel_prefix=os.getenv("QBANK_V2_PROGRESS_CHANNEL_PREFIX", "qbank:progress:"),
        queue_mode=os.getenv("QBANK_V2_QUEUE_MODE", "auto"),
    )
