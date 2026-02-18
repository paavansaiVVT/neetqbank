from __future__ import annotations

import asyncio
import json
import logging
import re
import traceback
from typing import Any
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, ValidationError, model_validator

from question_banks import prompts
from question_banks.v2.config import QbankV2Settings, get_settings
from question_banks.v2.queue import RedisQueue
from question_banks.v2.repository import QbankV2Repository
from question_banks.v2.schemas import JobStatus

logger = logging.getLogger("qbank_v2_worker")


class GeneratedMCQ(BaseModel):
    question: str = Field(min_length=1)
    correct_answer: str = Field(min_length=1)
    options: list[str]
    explanation: str = Field(min_length=1)
    cognitive_level: str = "understanding"
    question_type: str = "single_correct_answer"
    estimated_time: float | str | int | None = None
    concepts: str | None = None
    difficulty: str | None = None
    QC: str = "fail"
    scores: dict[str, Any] | None = None
    recommendations: Any | None = None
    violations: Any | None = None
    categoryScores: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_options(self) -> "GeneratedMCQ":
        cleaned_options = [str(option).strip() for option in self.options]
        if len(cleaned_options) != 4:
            raise ValueError("options must contain exactly 4 values")

        if self.correct_answer not in cleaned_options:
            raise ValueError("correct_answer must be one of options")

        qc = str(self.QC).strip().lower()
        if qc not in {"pass", "fail"}:
            qc = "fail"

        self.options = cleaned_options
        self.correct_answer = str(self.correct_answer).strip()
        self.question = str(self.question).strip()
        self.explanation = str(self.explanation).strip()
        self.cognitive_level = str(self.cognitive_level).strip().lower()
        self.question_type = str(self.question_type).strip()
        self.QC = qc

        # === Code-level QC enforcement ===

        # 1. Auto-fail if duplicate options exist (indicates ambiguity)
        lower_opts = [o.lower().strip() for o in cleaned_options]
        if len(set(lower_opts)) < 4:
            self.QC = "fail"

        # 2. Auto-fail if correct_answer matches multiple options
        correct_lower = self.correct_answer.lower().strip()
        match_count = sum(1 for o in lower_opts if o == correct_lower)
        if match_count > 1:
            self.QC = "fail"

        # 3. Score enforcement: override pass → fail if total score < 70
        if self.scores and self.QC == "pass":
            total = 0
            for key, val in self.scores.items():
                if isinstance(val, (int, float)):
                    total += val
                elif isinstance(val, dict):
                    total += sum(v for v in val.values() if isinstance(v, (int, float)))
            if total < 70:
                self.QC = "fail"

        self.estimated_time = _parse_estimated_time(self.estimated_time)
        return self


def _parse_estimated_time(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue
            # Handle dict-style content parts (e.g. {'type': 'text', 'text': '...'})
            if isinstance(part, dict):
                text = part.get("text") or part.get("content") or ""
                if text:
                    parts.append(str(text))
                continue
            # Handle object-style parts (LangChain content blocks)
            text = getattr(part, "text", None)
            if text:
                parts.append(str(text))
                continue
            part_content = getattr(part, "content", None)
            if part_content:
                parts.append(str(part_content))
                continue
            parts.append(str(part))
        return "\n".join(parts).strip()

    return str(content).strip()


def _extract_json_block(text: str) -> str:
    block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if block_match:
        return block_match.group(1).strip()
    return text.strip()


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> or <reasoning>...</reasoning> blocks from model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _parse_mcq_list(raw_text: str) -> list[dict[str, Any]]:
    # Strip thinking blocks first
    raw_text = _strip_think_blocks(raw_text)
    cleaned = _extract_json_block(raw_text)

    candidates: list[str] = [cleaned]

    # Try extracting outermost [ ... ]
    if "[" in cleaned and "]" in cleaned:
        candidates.append(cleaned[cleaned.find("[") : cleaned.rfind("]") + 1])

    # Handle double-encoded strings
    if cleaned.startswith('"') and cleaned.endswith('"'):
        try:
            decoded = json.loads(cleaned)
            if isinstance(decoded, str):
                candidates.append(decoded)
        except json.JSONDecodeError:
            pass

    # Also try regex extraction of any JSON array in the text
    array_match = re.search(r'(\[\s*\{.*?\}\s*\])', cleaned, flags=re.DOTALL)
    if array_match:
        candidates.append(array_match.group(1))

    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            if "questions" in parsed and isinstance(parsed["questions"], list):
                return parsed["questions"]
            # Single question object — wrap in list
            if "question" in parsed:
                return [parsed]
            continue

        if isinstance(parsed, list):
            return parsed

    raise ValueError("Failed to parse generated QC payload as JSON array")


def _extract_tokens(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


class QbankV2Worker:
    def __init__(
        self,
        settings: QbankV2Settings | None = None,
        repository: QbankV2Repository | None = None,
        queue: RedisQueue | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or QbankV2Repository()
        self.queue = queue or RedisQueue()
        self.generation_llm = ChatGoogleGenerativeAI(
            model=self.settings.generation_model_name,
            temperature=self.settings.generation_temperature,
        )
        self.qc_llm = ChatGoogleGenerativeAI(
            model=self.settings.qc_model_name,
            temperature=self.settings.qc_temperature,
        )

    async def _safe_publish(self, job_id: str, payload: dict[str, Any]) -> None:
        """Publish progress to Redis, silently skipping if Redis is unavailable."""
        try:
            await self.queue.publish_progress(job_id, payload)
        except Exception:
            pass  # Redis unavailable — inline mode, progress via DB polling

    async def run_forever(self) -> None:
        logger.info("QBank V2 worker started. queue=%s", self.settings.queue_name)

        while True:
            try:
                job_payload = await self.queue.dequeue_job()
                if not job_payload:
                    await asyncio.sleep(1)  # Prevent busy loop if Redis is down/empty
                    continue

                job_id = self._decode_job_payload(job_payload)
                if not job_id:
                    continue

                await self.process_job(job_id)
            except Exception:
                logger.exception("Unexpected worker loop failure")
                await asyncio.sleep(1)

    async def process_job(self, job_id: str) -> None:
        job = self.repository.get_job(job_id)
        if not job:
            logger.warning("Skipped unknown job_id=%s", job_id)
            return

        self.repository.set_job_status(job_id, JobStatus.running)
        self.repository.add_job_event(job_id, "started", {"job_id": job_id})
        
        # Publish started event
        await self._safe_publish(job_id, {
            "status": "running",
            "progress_percent": 0,
            "generated_count": int(job.get("generated_count", 0)),
            "passed_count": int(job.get("passed_count", 0)),
            "failed_count": int(job.get("failed_count", 0)),
        })

        remaining = int(job["requested_count"]) - int(job.get("generated_count", 0))
        consecutive_failures = 0
        generated_stems: list[str] = []  # Track stems for deduplication

        try:
            while remaining > 0:
                batch_size = min(self.settings.batch_size, remaining)
                try:
                    gen_model = job["request_payload"].get("generation_model")
                    qc_model = job["request_payload"].get("qc_model")
                    
                    generated_items, token_usage = await self._generate_batch(
                        job, 
                        batch_size,
                        gen_model_override=gen_model,
                        qc_model_override=qc_model,
                        already_generated_stems=generated_stems,
                    )

                    if not generated_items:
                        raise ValueError("Batch returned zero valid items")

                    # Save ALL items to DB — don't discard excess.
                    # They'll appear in the review page as bonus questions.
                    self.repository.insert_generated_items(job_id, generated_items)

                    # Track stems for cross-batch deduplication
                    for item in generated_items:
                        stem = str(item.get("question", ""))[:120]
                        if stem:
                            generated_stems.append(stem)

                    passed_count = sum(1 for item in generated_items if item["QC"] == "pass")
                    failed_count = len(generated_items) - passed_count

                    # Count all items for metrics, but only advance remaining
                    # by up to the amount still needed
                    items_toward_target = min(len(generated_items), remaining)

                    updated_job = self.repository.update_job_metrics(
                        job_id,
                        generated_inc=len(generated_items),
                        passed_inc=passed_count,
                        failed_inc=failed_count,
                        tokens=token_usage,
                        gen_model=gen_model or self.settings.generation_model_name,
                        qc_model=qc_model or self.settings.qc_model_name,
                    )

                    self.repository.add_job_event(
                        job_id,
                        "batch_done",
                        {
                            "batch_size": len(generated_items),
                            "passed_count": passed_count,
                            "failed_count": failed_count,
                            "token_usage": token_usage,
                            "models": {
                                "generation": gen_model or self.settings.generation_model_name,
                                "qc": qc_model or self.settings.qc_model_name
                            }
                        },
                    )
                    
                    # Publish progress
                    await self._safe_publish(job_id, {
                        "status": "running",
                        "progress_percent": updated_job.get("progress_percent", 0),
                        "generated_count": updated_job.get("generated_count", 0),
                        "passed_count": updated_job.get("passed_count", 0),
                        "failed_count": updated_job.get("failed_count", 0),
                        "new_items": generated_items,
                    })

                    remaining -= items_toward_target
                    consecutive_failures = 0
                except Exception as exc:
                    consecutive_failures += 1
                    self.repository.set_job_status(
                        job_id,
                        JobStatus.running,
                        error={"message": str(exc)},
                        increment_retry=True,
                    )
                    self.repository.add_job_event(
                        job_id,
                        "batch_failed",
                        {
                            "attempt": consecutive_failures,
                            "message": str(exc),
                        },
                    )

                    if consecutive_failures > self.settings.max_retries:
                        raise

            self.repository.set_job_status(job_id, JobStatus.completed, error=None)
            self.repository.add_job_event(job_id, "completed", {"job_id": job_id})
            
            # Publish completion
            final_job = self.repository.get_job(job_id) or {}
            await self._safe_publish(job_id, {
                "status": "completed",
                "progress_percent": 100,
                "generated_count": final_job.get("generated_count", 0),
                "passed_count": final_job.get("passed_count", 0),
                "failed_count": final_job.get("failed_count", 0),
            })
            
        except Exception as exc:
            error_payload = {
                "message": str(exc),
                "traceback": traceback.format_exc(limit=3),
            }
            self.repository.set_job_status(job_id, JobStatus.failed, error=error_payload)
            self.repository.add_job_event(job_id, "failed", error_payload)
            logger.exception("Job failed job_id=%s", job_id)
            
            # Publish failure
            await self._safe_publish(job_id, {
                "status": "failed",
                "error": str(exc)
            })

    @staticmethod
    def _format_cognitive_instruction(payload: dict[str, Any]) -> str:
        cog = payload.get("cognitive")
        if not cog or not isinstance(cog, dict):
            return ""
        parts = [f"{v} {k}" for k, v in cog.items() if isinstance(v, int) and v > 0]
        if not parts:
            return ""
        return f"Cognitive level distribution: {', '.join(parts)}\n"

    @staticmethod
    def _format_question_type_instruction(payload: dict[str, Any]) -> str:
        qt = payload.get("question_types")
        if not qt or not isinstance(qt, dict):
            return ""
        parts = [f"{v} {k}" for k, v in qt.items() if isinstance(v, int) and v > 0]
        if not parts:
            return ""
        return f"Question types: {', '.join(parts)}\n"

    @staticmethod
    def _format_already_generated(stems: list[str]) -> str:
        if not stems:
            return ""
        # Keep last 50 stems max to avoid exceeding context window
        recent = stems[-50:]
        bullet_list = "\n".join(f"- {s}" for s in recent)
        return (
            f"\nThe following questions have already been generated. "
            f"Do NOT repeat or closely paraphrase any of them:\n{bullet_list}\n"
        )

    async def _generate_batch(
        self, 
        job: dict[str, Any], 
        batch_size: int,
        gen_model_override: str | None = None,
        qc_model_override: str | None = None,
        already_generated_stems: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        payload = job["request_payload"]
        gen_messages = [
            SystemMessage(content=prompts.generation_system_prompt),
            HumanMessage(content=prompts.generation_user_prompt.format(
                topic=payload["selected_input"],
                difficulty=payload["difficulty"],
                No=batch_size,
                cognitive_instruction=self._format_cognitive_instruction(payload),
                question_type_instruction=self._format_question_type_instruction(payload),
                already_generated=self._format_already_generated(already_generated_stems or []),
            )),
        ]

        gen_llm = self.generation_llm
        if gen_model_override:
            gen_llm = ChatGoogleGenerativeAI(
                model=gen_model_override,
                temperature=self.settings.generation_temperature,
            )

        generation_response = await gen_llm.ainvoke(gen_messages)
        generation_text = _coerce_text(generation_response.content)

        qc_messages = [
            SystemMessage(content=prompts.qc_system_prompt),
            HumanMessage(content=prompts.qc_user_prompt.format(mcq=generation_text)),
        ]
        
        qc_llm = self.qc_llm
        if qc_model_override:
            qc_llm = ChatGoogleGenerativeAI(
                model=qc_model_override,
                temperature=self.settings.qc_temperature,
            )

        qc_response = await qc_llm.ainvoke(qc_messages)
        qc_text = _coerce_text(qc_response.content)

        logger.info("Generation text (first 500 chars) for job_id=%s: %s", job["job_id"], generation_text[:500])
        logger.info("QC text (first 500 chars) for job_id=%s: %s", job["job_id"], qc_text[:500])

        try:
            parsed_items = _parse_mcq_list(qc_text)
        except ValueError as e:
            logger.error("Failed to parse QC text for job_id=%s: %s. Raw QC text: %s", job["job_id"], e, qc_text[:1000])
            raise
        validated_items: list[dict[str, Any]] = []

        for raw_item in parsed_items:
            try:
                validated = GeneratedMCQ.model_validate(raw_item)
                validated_items.append(validated.model_dump())
            except ValidationError as ve:
                logger.warning(
                    "Skipping invalid generated item for job_id=%s: %s | raw_keys=%s",
                    job["job_id"],
                    ve,
                    list(raw_item.keys()) if isinstance(raw_item, dict) else type(raw_item),
                )

        generation_tokens = _extract_tokens(generation_response)
        qc_tokens = _extract_tokens(qc_response)

        # Log each step separately for granular tracking
        job_id = job["job_id"]
        user_id = job.get("requested_by", "unknown")
        gen_model_name = gen_model_override or self.settings.generation_model_name
        qc_model_name = qc_model_override or self.settings.qc_model_name
        try:
            self.repository.insert_token_log(job_id, user_id, "generation", gen_model_name, generation_tokens)
            self.repository.insert_token_log(job_id, user_id, "qc", qc_model_name, qc_tokens)
        except Exception as e:
            logger.warning("Failed to insert token usage log: %s", e)

        combined_tokens = {
            "input_tokens": generation_tokens["input_tokens"] + qc_tokens["input_tokens"],
            "output_tokens": generation_tokens["output_tokens"] + qc_tokens["output_tokens"],
            "total_tokens": generation_tokens["total_tokens"] + qc_tokens["total_tokens"],
        }

        # --- Self-Correction Loop (max 1 retry for failed items) ---
        failed_items = [item for item in validated_items if item.get("QC") == "fail"]
        if failed_items and len(failed_items) <= 10:
            try:
                corrected, correction_tokens = await self._regenerate_failed(
                    failed_items, job, gen_llm, qc_llm
                )
                passed_corrections = [c for c in corrected if c.get("QC") == "pass"]
                if passed_corrections:
                    # Keep passing items + corrections, drop original fails that were corrected
                    passing_items = [i for i in validated_items if i.get("QC") != "fail"]
                    remaining_fails = failed_items[len(passed_corrections):]
                    validated_items = passing_items + passed_corrections + remaining_fails
                    # Add correction tokens to totals
                    for key in combined_tokens:
                        combined_tokens[key] += correction_tokens.get(key, 0)
                    logger.info(
                        "Self-correction recovered %d/%d failed items for job_id=%s",
                        len(passed_corrections), len(failed_items), job["job_id"],
                    )
            except Exception as e:
                logger.warning("Self-correction failed for job_id=%s: %s", job["job_id"], e)

        # --- Duplicate Detection ---
        try:
            from question_banks.v2.dedup import find_duplicates

            existing_items, _ = self.repository.list_items(
                job["job_id"], None, None, 0, 5000
            )
            existing_texts = [item["question"] for item in existing_items if item.get("question")]
            if existing_texts:
                dup_indices = find_duplicates(validated_items, existing_texts, threshold=0.80)
                if dup_indices:
                    logger.info(
                        "Removed %d duplicate questions for job_id=%s",
                        len(dup_indices), job["job_id"],
                    )
                    dup_set = set(dup_indices)
                    validated_items = [
                        item for i, item in enumerate(validated_items) if i not in dup_set
                    ]
        except Exception as e:
            logger.warning("Duplicate detection skipped for job_id=%s: %s", job["job_id"], e)

        return validated_items, combined_tokens

    async def _regenerate_failed(
        self,
        failed_items: list[dict[str, Any]],
        job: dict[str, Any],
        gen_llm: ChatGoogleGenerativeAI,
        qc_llm: ChatGoogleGenerativeAI,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Send failed question feedback to generator for self-correction (1 retry)."""

        feedback_parts: list[str] = []
        for item in failed_items[:5]:  # Limit to 5 to control token usage
            violations = item.get("violations", [])
            violation_text = "\n".join(
                f"  - [{v.get('severity', 'MINOR')}] {v.get('description', 'Unknown issue')}"
                for v in (violations if isinstance(violations, list) else [])
            )
            recs = item.get("recommendations", [])
            rec_text = ", ".join(recs) if isinstance(recs, list) else str(recs or "Improve quality")
            feedback_parts.append(
                f"Question: {str(item.get('question', ''))[:200]}\n"
                f"QC Status: FAIL\n"
                f"Violations:\n{violation_text}\n"
                f"Recommendations: {rec_text}\n"
            )

        correction_prompt = (
            f"The following {len(feedback_parts)} questions FAILED quality control.\n"
            f"Fix each question based on the specific feedback provided, "
            f"then return the corrected versions.\n\n"
            f"Topic: {job['request_payload']['selected_input']}\n"
            f"Difficulty: {job['request_payload']['difficulty']}\n\n"
            f"CRITICAL CONSTRAINTS:\n"
            f"- Each question MUST have EXACTLY ONE correct answer\n"
            f"- The correct_answer text MUST appear verbatim in the options array\n"
            f"- All 4 options must be distinct and plausible\n"
            f"- Content must be within NCERT scope\n\n"
            f"--- FAILED QUESTIONS WITH FEEDBACK ---\n"
            f"{'---'.join(feedback_parts)}\n"
            f"---\n\n"
            f"Return corrected questions ONLY as a JSON array."
        )

        gen_messages = [
            SystemMessage(content=prompts.generation_system_prompt),
            HumanMessage(content=correction_prompt),
        ]
        regen_response = await gen_llm.ainvoke(gen_messages)
        regen_text = _coerce_text(regen_response.content)

        qc_messages = [
            SystemMessage(content=prompts.qc_system_prompt),
            HumanMessage(content=prompts.qc_user_prompt.format(mcq=regen_text)),
        ]
        qc_response = await qc_llm.ainvoke(qc_messages)
        qc_text = _coerce_text(qc_response.content)

        regen_tokens = _extract_tokens(regen_response)
        qc2_tokens = _extract_tokens(qc_response)

        # Log regeneration steps separately
        user_id = job.get("requested_by", "unknown")
        gen_model_name = str(gen_llm.model) if hasattr(gen_llm, 'model') else "unknown"
        qc_model_name = str(qc_llm.model) if hasattr(qc_llm, 'model') else "unknown"
        try:
            self.repository.insert_token_log(job["job_id"], user_id, "regeneration", gen_model_name, regen_tokens)
            self.repository.insert_token_log(job["job_id"], user_id, "regeneration_qc", qc_model_name, qc2_tokens)
        except Exception as e:
            logger.warning("Failed to insert regen token usage log: %s", e)

        combined = {
            "input_tokens": regen_tokens["input_tokens"] + qc2_tokens["input_tokens"],
            "output_tokens": regen_tokens["output_tokens"] + qc2_tokens["output_tokens"],
            "total_tokens": regen_tokens["total_tokens"] + qc2_tokens["total_tokens"],
        }

        try:
            parsed = _parse_mcq_list(qc_text)
            validated: list[dict[str, Any]] = []
            for raw in parsed:
                try:
                    v = GeneratedMCQ.model_validate(raw)
                    validated.append(v.model_dump())
                except ValidationError:
                    pass
            return validated, combined
        except ValueError:
            return [], combined

    @staticmethod
    def _decode_job_payload(payload: str) -> str | None:
        if not payload:
            return None

        stripped = payload.strip()
        if not stripped:
            return None

        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
                return str(parsed.get("job_id", "")).strip() or None
            except json.JSONDecodeError:
                return None

        return stripped


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker = QbankV2Worker()
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
