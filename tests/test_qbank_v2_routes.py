import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from question_banks.v2 import routes
from question_banks.v2.config import get_settings


class FakeService:
    def __init__(self) -> None:
        self.publish_calls = 0
        self.jobs = {
            "job-1": {
                "job_id": "job-1",
                "status": "queued",
                "progress_percent": 0,
                "requested_count": 5,
                "generated_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "timestamps": {
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                    "started_at": None,
                    "completed_at": None,
                    "published_at": None,
                },
                "retry_count": 0,
                "error": None,
            }
        }

    async def create_job(self, request):
        return self.jobs["job-1"]

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def list_items(self, *_args, **_kwargs):
        items = [
            {
                "item_id": 1,
                "job_id": "job-1",
                "question": "Q1",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "explanation": "exp",
                "cognitive_level": "understanding",
                "question_type": "single_correct_answer",
                "estimated_time": 1.0,
                "concepts": "test",
                "qc_status": "pass",
                "review_status": "approved",
                "scores": {},
                "recommendations": None,
                "violations": None,
                "category_scores": {},
                "edited": False,
                "published": False,
                "published_question_id": None,
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            }
        ]
        return items, 1

    def update_item(self, *_args, **_kwargs):
        return {
            "item_id": 1,
            "job_id": "job-1",
            "question": "Updated Q1",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "explanation": "updated exp",
            "cognitive_level": "understanding",
            "question_type": "single_correct_answer",
            "estimated_time": 1.0,
            "concepts": "test",
            "qc_status": "pass",
            "review_status": "approved",
            "scores": {},
            "recommendations": None,
            "violations": None,
            "category_scores": {},
            "edited": True,
            "published": False,
            "published_question_id": None,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }

    def publish_items(self, *_args, **_kwargs):
        self.publish_calls += 1
        if self.publish_calls == 1:
            return {
                "published_count": 1,
                "skipped_count": 0,
                "failed_count": 0,
                "published_question_ids": [101],
            }
        return {
            "published_count": 0,
            "skipped_count": 1,
            "failed_count": 0,
            "published_question_ids": [],
        }

    async def health(self):
        return {"api": "ok", "queue": "ok"}

    def list_subjects(self):
        return ["Physics", "Chemistry"]

    def list_chapters(self, subject=None):
        if subject == "Physics":
            return ["Laws of Motion", "Gravitation"]
        return ["Laws of Motion", "Organic Chemistry"]

    def list_topics(self, subject=None, chapter=None):
        if subject == "Physics" and chapter == "Laws of Motion":
            return ["Friction", "Newton's Laws"]
        return ["Generic Topic"]


def _make_client() -> TestClient:
    os.environ["QBANK_V2_INTERNAL_API_KEY"] = "test-key"
    get_settings.cache_clear()

    app = FastAPI()
    app.include_router(routes.router)
    routes.service = FakeService()
    return TestClient(app)


def test_create_job_requires_api_key():
    client = _make_client()
    payload = {
        "selected_subject": "Physics",
        "selected_chapter": "Laws",
        "selected_input": "Motion",
        "difficulty": "medium",
        "count": 5,
        "requested_by": "qa",
    }

    response = client.post("/v2/qbank/jobs", json=payload)
    assert response.status_code == 401


def test_create_job_rejects_wrong_api_key():
    client = _make_client()
    payload = {
        "selected_subject": "Physics",
        "selected_chapter": "Laws",
        "selected_input": "Motion",
        "difficulty": "medium",
        "count": 5,
        "requested_by": "qa",
    }

    response = client.post(
        "/v2/qbank/jobs",
        json=payload,
        headers={"X-Internal-API-Key": "wrong"},
    )
    assert response.status_code == 401


def test_create_job_success():
    client = _make_client()
    payload = {
        "selected_subject": "Physics",
        "selected_chapter": "Laws",
        "selected_input": "Motion",
        "difficulty": "medium",
        "count": 5,
        "requested_by": "qa",
    }

    response = client.post(
        "/v2/qbank/jobs",
        json=payload,
        headers={"X-Internal-API-Key": "test-key"},
    )
    assert response.status_code == 202
    assert response.json()["job_id"] == "job-1"


def test_create_job_validation_error():
    client = _make_client()
    payload = {
        "selected_subject": "Physics",
        "selected_chapter": "Laws",
        "selected_input": "Motion",
        "difficulty": "medium",
        "count": 0,
        "requested_by": "qa",
    }

    response = client.post(
        "/v2/qbank/jobs",
        json=payload,
        headers={"X-Internal-API-Key": "test-key"},
    )
    assert response.status_code == 422


def test_get_job_items_patch_and_publish():
    client = _make_client()
    headers = {"X-Internal-API-Key": "test-key"}

    details = client.get("/v2/qbank/jobs/job-1", headers=headers)
    assert details.status_code == 200

    items = client.get("/v2/qbank/jobs/job-1/items", headers=headers)
    assert items.status_code == 200
    assert items.json()["total"] == 1

    patch_resp = client.patch(
        "/v2/qbank/jobs/job-1/items/1",
        json={"question": "Updated Q1"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["edited"] is True

    bad_patch = client.patch(
        "/v2/qbank/jobs/job-1/items/1",
        json={},
        headers=headers,
    )
    assert bad_patch.status_code == 422

    publish_resp = client.post(
        "/v2/qbank/jobs/job-1/publish",
        json={"publish_mode": "all_approved"},
        headers=headers,
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["published_count"] == 1

    second_publish = client.post(
        "/v2/qbank/jobs/job-1/publish",
        json={"publish_mode": "all_approved"},
        headers=headers,
    )
    assert second_publish.status_code == 200
    assert second_publish.json()["skipped_count"] == 1


def test_health_endpoint():
    client = _make_client()
    response = client.get("/v2/qbank/health", headers={"X-Internal-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"api": "ok", "queue": "ok"}


def test_metadata_endpoints():
    client = _make_client()
    headers = {"X-Internal-API-Key": "test-key"}

    subjects = client.get("/v2/qbank/metadata/subjects", headers=headers)
    assert subjects.status_code == 200
    assert subjects.json()["subjects"] == ["Physics", "Chemistry"]

    chapters = client.get("/v2/qbank/metadata/chapters?subject=Physics", headers=headers)
    assert chapters.status_code == 200
    assert "Laws of Motion" in chapters.json()["chapters"]

    topics = client.get(
        "/v2/qbank/metadata/topics?subject=Physics&chapter=Laws%20of%20Motion",
        headers=headers,
    )
    assert topics.status_code == 200
    assert topics.json()["topics"] == ["Friction", "Newton's Laws"]
