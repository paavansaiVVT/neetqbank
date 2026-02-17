from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"
    veryhard = "veryhard"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    publishing = "publishing"
    published = "published"


class QCStatus(str, Enum):
    passed = "pass"
    failed = "fail"


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class PublishMode(str, Enum):
    selected = "selected"
    all_approved = "all_approved"


class GenerationJobCreateRequest(BaseModel):
    selected_subject: str = Field(min_length=1, max_length=255)
    selected_chapter: str = Field(min_length=1, max_length=255)
    selected_input: str = Field(min_length=0, max_length=255, default="")
    difficulty: Difficulty | dict[str, int]
    count: int = Field(ge=1, le=500)
    requested_by: str = Field(min_length=1, max_length=255)
    cognitive: dict[str, int] | None = None
    question_types: dict[str, int] | None = None
    batch_name: str | None = Field(default=None, max_length=255)
    generation_model: str | None = Field(default=None, max_length=100)
    qc_model: str | None = Field(default=None, max_length=100)

    @field_validator("selected_subject", "selected_chapter", "selected_input", "requested_by")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class JobTimestamps(BaseModel):
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    published_at: datetime | None = None


class GenerationJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress_percent: int
    requested_count: int
    generated_count: int
    passed_count: int
    failed_count: int
    token_usage: TokenUsage
    timestamps: JobTimestamps
    retry_count: int = 0
    error: dict[str, Any] | None = None


class DraftQuestionItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    item_id: int
    job_id: str
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_answer: str
    explanation: str
    cognitive_level: str
    question_type: str
    estimated_time: float | None = None
    concepts: str | None = None
    difficulty: str | None = None
    qc_status: QCStatus
    review_status: ReviewStatus
    scores: dict[str, Any] | None = None
    recommendations: Any | None = None
    violations: Any | None = None
    category_scores: dict[str, Any] | None = None
    edited: bool
    published: bool
    published_question_id: int | None = None
    created_at: datetime
    updated_at: datetime


class DraftItemsResponse(BaseModel):
    items: list[DraftQuestionItem]
    total: int
    offset: int
    limit: int


class DraftItemPatchRequest(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    options: list[str] | None = Field(default=None, min_length=4, max_length=4)
    correct_answer: str | None = None
    explanation: str | None = Field(default=None, min_length=1)
    cognitive_level: str | None = None
    difficulty: str | None = None
    question_type: str | None = None
    estimated_time: float | None = None
    concepts: str | None = None
    review_status: ReviewStatus | None = None
    rejection_reasons: list[str] | None = None  # List of rejection reason IDs
    rejection_comment: str | None = None  # Optional detailed comment

    @model_validator(mode="after")
    def validate_payload(self) -> "DraftItemPatchRequest":
        if not any(
            [
                self.question,
                self.options,
                self.correct_answer,
                self.explanation,
                self.cognitive_level,
                self.difficulty,
                self.question_type,
                self.estimated_time is not None,
                self.concepts,
                self.review_status,
            ]
        ):
            raise ValueError("At least one editable field is required")

        if self.options and self.correct_answer and self.correct_answer not in self.options:
            raise ValueError("correct_answer must be one of the provided options")

        return self


class PublishRequest(BaseModel):
    publish_mode: PublishMode = PublishMode.all_approved
    item_ids: list[int] | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> "PublishRequest":
        if self.publish_mode == PublishMode.selected:
            if not self.item_ids:
                raise ValueError("item_ids are required when publish_mode is selected")
        return self


class PublishResponse(BaseModel):
    published_count: int
    skipped_count: int
    failed_count: int
    published_question_ids: list[int]


class HealthResponse(BaseModel):
    api: str
    queue: str


class SubjectListResponse(BaseModel):
    subjects: list[str]


class ChapterListResponse(BaseModel):
    chapters: list[str]


class TopicListResponse(BaseModel):
    topics: list[str]


# ============================================
# Sprint 10: New Schemas for Backend Integration
# ============================================

class ActivityType(str, Enum):
    created = "created"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"
    commented = "commented"
    published = "published"
    generated = "generated"


class ActivityItem(BaseModel):
    id: str
    activity_type: ActivityType
    user_id: str
    user_name: str
    target_type: str  # "job", "item", "batch"
    target_id: str
    target_label: str
    details: str | None = None
    timestamp: datetime


class ActivityFeedResponse(BaseModel):
    items: list[ActivityItem]
    total: int


class DailyUsage(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    cost: float
    cost_inr: float = 0.0
    generation_tokens: int = 0
    qc_tokens: int = 0


class TokenUsageResponse(BaseModel):
    daily_usage: list[DailyUsage]
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    total_cost_inr: float = 0.0
    period_days: int


class QueueItemPriority(str, Enum):
    urgent = "urgent"
    normal = "normal"
    low = "low"


class QueueItem(BaseModel):
    id: int
    job_id: str
    question: str
    subject: str
    chapter: str
    priority: QueueItemPriority
    assigned_at: datetime
    due_at: datetime | None = None


class ReviewQueueResponse(BaseModel):
    items: list[QueueItem]
    total: int


class Comment(BaseModel):
    id: str
    item_id: int
    user_id: str
    user_name: str
    content: str
    created_at: datetime
    parent_id: str | None = None  # For replies


class CommentCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    parent_id: str | None = None


class CommentListResponse(BaseModel):
    comments: list[Comment]
    total: int


class QuestionSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    subject: str | None = None
    chapter: str | None = None
    difficulty: Difficulty | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResultItem(BaseModel):
    item_id: int
    job_id: str
    question: str
    subject: str
    chapter: str
    difficulty: str
    similarity_score: float | None = None


class QuestionSearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
    query: str


# ============================================
# Analytics Schemas
# ============================================

class AnalyticsSummary(BaseModel):
    total_mcqs: int
    mcqs_this_week: int
    approval_rate: float
    rejection_rate: float
    total_cost_usd: float
    published_count: int


class DailyTrend(BaseModel):
    date: str
    count: int
    cost: float


class SubjectBreakdown(BaseModel):
    subject: str
    count: int


class ChapterBreakdown(BaseModel):
    subject: str
    chapter: str
    count: int


class UserAnalytics(BaseModel):
    user_id: str
    user_name: str
    count: int
    approval_rate: float
    cost: float


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    daily_trend: list[DailyTrend]
    by_subject: list[SubjectBreakdown]
    by_chapter: list[ChapterBreakdown]
    by_difficulty: dict[str, int]
    by_cognitive: dict[str, int]
    by_user: list[UserAnalytics]
    model_usage: dict[str, int]
