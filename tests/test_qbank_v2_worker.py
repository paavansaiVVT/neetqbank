from unittest import mock
from question_banks.v2.config import QbankV2Settings
from question_banks.v2.worker import QbankV2Worker


class FakeResponse:
    def __init__(self, content, usage=None):
        self.content = content
        self.usage_metadata = usage or {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}


class SequenceLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    async def ainvoke(self, _prompt):
        if self._responses:
            return self._responses.pop(0)
        return FakeResponse("[]")


class FakeRepository:
    def __init__(self):
        self.job = {
            "job_id": "job-1",
            "status": "queued",
            "requested_count": 1,
            "generated_count": 0,
            "request_payload": {
                "selected_input": "Motion",
                "difficulty": "medium",
            },
        }
        self.final_status = None
        self.events = []
        self.inserted = []
        self.retry_count = 0

    def get_job(self, job_id):
        if job_id == "job-1":
            return self.job
        return None

    def set_job_status(self, _job_id, status, error=None, increment_retry=False):
        self.final_status = status.value
        self.job["status"] = status.value
        if increment_retry:
            self.retry_count += 1
        if error:
            self.job["error"] = error
        return self.job

    def add_job_event(self, job_id, event_type, payload=None):
        self.events.append((job_id, event_type, payload))

    def insert_generated_items(self, _job_id, items):
        self.inserted.extend(items)
        return len(items)

    def update_job_metrics(self, _job_id, generated_inc, passed_inc, failed_inc, tokens, gen_model=None, qc_model=None):
        self.job["generated_count"] += generated_inc
        self.job["passed_count"] = self.job.get("passed_count", 0) + passed_inc
        self.job["failed_count"] = self.job.get("failed_count", 0) + failed_inc
        token_usage = self.job.setdefault("token_usage", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        token_usage["input_tokens"] += tokens["input_tokens"]
        token_usage["output_tokens"] += tokens["output_tokens"]
        token_usage["total_tokens"] += tokens["total_tokens"]
        return {
            "requested_count": self.job["requested_count"],
            "generated_count": self.job["generated_count"],
            "progress_percent": int(self.job["generated_count"] / self.job["requested_count"] * 100),
            "passed_count": self.job.get("passed_count", 0),
            "failed_count": self.job.get("failed_count", 0),
        }


class FakeQueue:
    async def dequeue_job(self):
        return None

    async def publish_progress(self, job_id, progress):
        pass


def _settings(max_retries=1):
    return QbankV2Settings(
        enabled=True,
        internal_api_key="test",
        generation_model_name="gemini-3-pro-preview",
        qc_model_name="gemini-3-flash-preview",
        generation_temperature=0.8,
        qc_temperature=0.1,
        redis_url="redis://localhost:6379/0",
        queue_name="qbank_v2_jobs",
        queue_block_timeout_seconds=1,
        max_retries=max_retries,
        batch_size=1,
        max_questions_per_job=10,
        database_url="mysql://unused",
        progress_channel_prefix="job_progress:",
        queue_mode="auto",
    )


@mock.patch("question_banks.v2.worker.ChatGoogleGenerativeAI")
def test_worker_process_job_success(mock_llm_class):
    # Setup mock to return our SequenceLLM when instantiated
    mock_instance = mock.Mock()
    mock_llm_class.return_value = mock_instance
    
    repo = FakeRepository()
    worker = QbankV2Worker(settings=_settings(), repository=repo, queue=FakeQueue())

    # Manually inject our sequence LLMs (overriding the mocked instance which is just a placeholder)
    worker.generation_llm = SequenceLLM([FakeResponse("gen")])
    worker.qc_llm = SequenceLLM(
        [
            FakeResponse(
                """
                [
                  {
                    "question": "What is force?",
                    "correct_answer": "mass x acceleration",
                    "options": ["mass x acceleration", "mass / acceleration", "velocity", "distance"],
                    "explanation": "Newton second law",
                    "cognitive_level": "understanding",
                    "question_type": "single_correct_answer",
                    "estimated_time": 1,
                    "concepts": "force,newton",
                    "QC": "pass",
                    "scores": {"content_accuracy": 10}
                  }
                ]
                """
            )
        ]
    )

    import asyncio

    asyncio.run(worker.process_job("job-1"))

    assert repo.final_status == "completed"
    assert len(repo.inserted) == 1
    assert repo.job["generated_count"] == 1


@mock.patch("question_banks.v2.worker.ChatGoogleGenerativeAI")
def test_worker_process_job_failure_after_retries(mock_llm_class):
    mock_instance = mock.Mock()
    mock_llm_class.return_value = mock_instance
    
    repo = FakeRepository()
    worker = QbankV2Worker(settings=_settings(max_retries=1), repository=repo, queue=FakeQueue())

    worker.generation_llm = SequenceLLM([FakeResponse("gen"), FakeResponse("gen")])
    worker.qc_llm = SequenceLLM([FakeResponse("not-json"), FakeResponse("still-not-json")])

    import asyncio

    asyncio.run(worker.process_job("job-1"))

    assert repo.final_status == "failed"
    assert repo.retry_count >= 2
