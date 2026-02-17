import pytest
import os
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI
from question_banks.v2 import routes
from question_banks.v2.config import get_settings

class FakeService:
    def __init__(self) -> None:
        self.publish_calls = 0
        self.jobs = {}
        self.items = {}  # Map job_id -> list of items
        
        # Seed default data
        self.seed_default_data()

    def seed_default_data(self):
        job_id = "job-1"
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": "completed",
            "progress_percent": 100,
            "requested_count": 5,
            "generated_count": 5,
            "passed_count": 5,
            "failed_count": 0,
            "token_usage": {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500, "input_cost": 0.0003, "output_cost": 0.0013, "total_cost": 0.0016},
            "timestamps": {
                "created_at": "2026-01-01T10:00:00+00:00",
                "updated_at": "2026-01-01T10:05:00+00:00",
                "started_at": "2026-01-01T10:00:01+00:00",
                "completed_at": "2026-01-01T10:05:00+00:00",
                "published_at": None,
            },
            "retry_count": 0,
            "error": None,
            "selected_subject": "Physics",
            "selected_chapter": "Laws of Motion",
            "request_payload": {"generation_model": "gemini-2.5-flash", "qc_model": "gemini-2.5-pro"},
        }
        
        self.items[job_id] = [
            {
                "item_id": 1,
                "job_id": job_id,
                "question": "What is the unit of force?",
                "options": ["Newton", "Joule", "Watt", "Pascal"],
                "correct_answer": "Newton",
                "explanation": "Newton is the SI unit of force.",
                "cognitive_level": "understanding",
                "question_type": "single_correct_answer",
                "estimated_time": 1.0,
                "concepts": "Units",
                "qc_status": "pass",
                "review_status": "approved",
                "scores": {},
                "recommendations": None,
                "violations": None,
                "category_scores": {},
                "edited": False,
                "published": False,
                "published_question_id": None,
                "created_at": "2026-01-01T10:00:00",
                "updated_at": "2026-01-01T10:00:00",
                "difficulty": "medium",
            },
             {
                "item_id": 2,
                "job_id": job_id,
                "question": "Pending review question",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "explanation": "Exp",
                "cognitive_level": "recall",
                "question_type": "single_correct_answer",
                "estimated_time": 1.0,
                "concepts": "Test",
                "qc_status": "pass",
                "review_status": "pending",  # For queue testing
                "scores": {},
                "recommendations": None,
                "violations": None,
                "category_scores": {},
                "edited": False,
                "published": False,
                "published_question_id": None,
                "created_at": datetime.now().isoformat(), # Recently created
                "updated_at": datetime.now().isoformat(),
                "difficulty": "hard",
            }
        ]

    async def create_job(self, request):
        job_id = f"job-{len(self.jobs) + 1}"
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress_percent": 0,
            "requested_count": request.count,
            "generated_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0},
            "timestamps": {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "started_at": None,
                "completed_at": None,
                "published_at": None,
            },
            "retry_count": 0,
            "error": None,
            "selected_subject": request.selected_subject,
            "selected_chapter": request.selected_chapter,
        }
        self.items[job_id] = []
        return self.jobs[job_id]

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def list_jobs(self, limit: int = 20, offset: int = 0):
        jobs_list = list(self.jobs.values())
        # Sort by created_at desc
        jobs_list.sort(key=lambda x: x["timestamps"]["created_at"], reverse=True)
        return jobs_list[offset : offset + limit], len(jobs_list)

    def list_items(self, job_id, qc_status=None, review_status=None, offset=0, limit=50):
        items = self.items.get(job_id, [])
        filtered = []
        for item in items:
            if qc_status and item.get("qc_status") != qc_status:
                continue
            if review_status and item.get("review_status") != review_status:
                continue
            filtered.append(item)
        
        return filtered[offset : offset + limit], len(filtered)

    def update_item(self, job_id, item_id, request):
        items = self.items.get(job_id, [])
        for item in items:
            if item["item_id"] == item_id:
                for key, value in request.dict(exclude_unset=True).items():
                    item[key] = value
                item["edited"] = True
                return item
        raise ValueError("Item not found")

    def bulk_update_items(self, job_id, item_ids, patch):
        items = self.items.get(job_id, [])
        count = 0
        for item in items:
            if item["item_id"] in item_ids:
                for key, value in patch.dict(exclude_unset=True).items():
                    item[key] = value
                count += 1
        return {"updated_count": count, "requested_count": len(item_ids)}

    def publish_items(self, job_id, request):
        self.publish_calls += 1
        job = self.jobs.get(job_id)
        if job:
            job["status"] = "published"
            job["timestamps"]["published_at"] = datetime.now().isoformat()
            
        return {
            "published_count": 1,
            "skipped_count": 0,
            "failed_count": 0,
            "published_question_ids": [101],
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
        return ["Topic 1", "Topic 2"]
        
    def subscribe_job(self, job_id):
        # Return dummy pubsub and channel for mocking
        class DummyPubSub:
            async def subscribe(self, channel): pass
            async def unsubscribe(self, channel): pass
            async def close(self): pass
            async def listen(self):
                # Empty async generator
                if False: yield {}
        
        return DummyPubSub(), "channel"


@pytest.fixture
def fake_service():
    return FakeService()

@pytest.fixture
def client(fake_service):
    os.environ["QBANK_V2_INTERNAL_API_KEY"] = "test-key"
    get_settings.cache_clear()

    app = FastAPI()
    app.include_router(routes.router)
    
    # Patch the service in the routes module
    old_service = routes.service
    routes.service = fake_service
    
    # Clear comment store between tests
    routes._comments_store.clear()
    
    yield TestClient(app)
    
    # Restore
    routes.service = old_service
