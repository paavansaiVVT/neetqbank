from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
import json
import io

from question_banks.v2.auth import require_auth_or_api_key, require_role
from question_banks.v2.schemas_auth import TokenPayload, UserRole
from question_banks.v2.schemas import (
    ChapterListResponse,
    DraftItemPatchRequest,
    DraftItemsResponse,
    DraftQuestionItem,
    GenerationJobCreateRequest,
    GenerationJobResponse,
    HealthResponse,
    PublishRequest,
    PublishResponse,
    SubjectListResponse,
    TopicListResponse,
    # Sprint 10: New schemas
    ActivityFeedResponse,
    ActivityItem,
    ActivityType,
    TokenUsageResponse,
    DailyUsage,
    ReviewQueueResponse,
    QueueItem,
    QueueItemPriority,
    CommentListResponse,
    Comment,
    CommentCreateRequest,
    QuestionSearchResponse,
    SearchResultItem,
    AnalyticsResponse,
)
from question_banks.v2.service import QbankV2Service
from typing import Any
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v2/qbank",
    tags=["qbank-v2"],
    dependencies=[Depends(require_auth_or_api_key)],
)

service = QbankV2Service()


@router.post("/jobs", response_model=GenerationJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_generation_job(
    request: GenerationJobCreateRequest,
    _user: TokenPayload = Depends(require_role(UserRole.creator, UserRole.admin)),
) -> GenerationJobResponse:
    try:
        data = await service.create_job(request)
        return GenerationJobResponse(**data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/jobs", response_model=dict[str, Any])
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    jobs, total = service.list_jobs(limit, offset)
    # Ensure JobStatus enum is serialized
    return {
        "items": jobs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
def get_dashboard_stats() -> dict[str, Any]:
    """Get aggregated statistics for dashboard."""
    return service.get_dashboard_stats()


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    days: int = Query(default=30, ge=1, le=90),
    user: Any = Depends(require_auth_or_api_key),
) -> AnalyticsResponse:
    """Deep analytics — admin sees full platform; others see own data."""
    effective_user_id: str | None = None

    if user is not None and hasattr(user, "role"):
        if user.role != UserRole.admin:
            effective_user_id = str(user.sub)
    # API key auth (user is None) → admin view

    data = service.get_analytics(user_id=effective_user_id, days=days)
    return AnalyticsResponse(**data)


@router.get("/jobs/{job_id}", response_model=GenerationJobResponse)
def get_generation_job(job_id: str) -> GenerationJobResponse:
    data = service.get_job(job_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return GenerationJobResponse(**data)


@router.get("/jobs/{job_id}/items", response_model=DraftItemsResponse)
def get_generation_items(
    job_id: str,
    qc_status: str | None = Query(default=None, pattern="^(pass|fail)$"),
    review_status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> DraftItemsResponse:
    if not service.get_job(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    items, total = service.list_items(job_id, qc_status, review_status, offset, limit)
    return DraftItemsResponse(
        items=[DraftQuestionItem(**item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.patch("/jobs/{job_id}/items/{item_id}", response_model=DraftQuestionItem)
def patch_generation_item(
    job_id: str, item_id: int, request: DraftItemPatchRequest,
    _user: TokenPayload = Depends(require_role(UserRole.creator, UserRole.reviewer, UserRole.admin)),
) -> DraftQuestionItem:
    if not service.get_job(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    try:
        item = service.update_item(job_id, item_id, request)
        return DraftQuestionItem(**item)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc




@router.post("/jobs/{job_id}/items/bulk-update")
def bulk_update_items(
    job_id: str, request: dict[str, Any],
    _user: TokenPayload = Depends(require_role(UserRole.creator, UserRole.reviewer, UserRole.admin)),
) -> dict[str, Any]:
    """Bulk update multiple items with the same patch payload."""
    if not service.get_job(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    
    item_ids = request.get("item_ids", [])
    patch_data = request.get("patch", {})
    
    if not item_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="item_ids required")
    
    try:
        patch = DraftItemPatchRequest(**patch_data)
        result = service.bulk_update_items(job_id, item_ids, patch)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/export")
def export_questions(
    job_id: str,
    format: str = Query("json", enum=["pdf", "excel", "docx", "json"]),
    include_explanations: bool = Query(True),
    include_metadata: bool = Query(False),
    only_approved: bool = Query(True),
    _user: TokenPayload = Depends(require_role(UserRole.creator, UserRole.publisher, UserRole.admin)),
):
    """Export questions from a specific job in PDF, Excel, Word, or JSON."""
    from question_banks.v2.export_service import generate_export

    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    review_status = "approved" if only_approved else None
    items, _ = service.list_items(job_id, None, review_status, 0, 1000)

    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No questions to export")

    title = f"{job.get('selected_subject', 'Questions')} — {job.get('selected_chapter', '')}"

    if format == "json":
        buf, filename, _ = generate_export(items, format, include_explanations, include_metadata, job_id, title)
        return JSONResponse(
            content=json.loads(buf.getvalue().decode()),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buf, filename, media_type = generate_export(items, format, include_explanations, include_metadata, job_id, title)
    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export")
def export_library(
    format: str = Query("json", enum=["pdf", "excel", "docx", "json"]),
    include_explanations: bool = Query(True),
    include_metadata: bool = Query(False),
    only_approved: bool = Query(True),
    subject: str | None = Query(None),
    chapter: str | None = Query(None),
    item_ids: str | None = Query(None, description="Comma-separated item IDs to export only specific questions"),
    _user: TokenPayload = Depends(require_role(UserRole.creator, UserRole.publisher, UserRole.admin)),
):
    """Export questions from across all jobs (library-wide export)."""
    from question_banks.v2.export_service import generate_export

    # Gather items from all completed/published jobs
    jobs, _ = service.list_jobs(1000, 0)
    all_items: list[dict] = []

    for job in jobs:
        if job["status"] not in ("completed", "published"):
            continue
        if subject and job.get("selected_subject") != subject:
            continue
        if chapter and job.get("selected_chapter") != chapter:
            continue

        review_status = "approved" if only_approved else None
        items, _ = service.list_items(job["job_id"], None, review_status, 0, 1000)
        all_items.extend(items)

    # Filter by specific item IDs if provided
    if item_ids:
        id_set = set(int(x) for x in item_ids.split(",") if x.strip())
        all_items = [it for it in all_items if it.get("item_id") in id_set]

    if not all_items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No questions to export")

    title_parts = ["Question Library"]
    if subject:
        title_parts.append(subject)
    if chapter:
        title_parts.append(chapter)
    title = " — ".join(title_parts)

    if format == "json":
        buf, filename, _ = generate_export(all_items, format, include_explanations, include_metadata, "library", title)
        return JSONResponse(
            content=json.loads(buf.getvalue().decode()),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buf, filename, media_type = generate_export(all_items, format, include_explanations, include_metadata, "library", title)
    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/jobs/{job_id}/publish", response_model=PublishResponse)
def publish_generation_items(
    job_id: str, request: PublishRequest,
    _user: TokenPayload = Depends(require_role(UserRole.creator, UserRole.publisher, UserRole.admin)),
) -> PublishResponse:
    if not service.get_job(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    try:
        result = service.publish_items(job_id, request)
        return PublishResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/restart", response_model=GenerationJobResponse)
async def restart_failed_job(
    job_id: str,
    _user: TokenPayload = Depends(require_role(UserRole.creator, UserRole.admin)),
) -> GenerationJobResponse:
    """Restart a failed or stuck job by resetting its status and re-processing."""
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job["status"] not in ("failed", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only failed or stuck jobs can be restarted (current: {job['status']})",
        )

    try:
        data = await service.restart_job(job_id)
        return GenerationJobResponse(**data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    pubsub, channel = service.subscribe_job(job_id)
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                # data is already json string from worker
                await websocket.send_text(data)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


@router.get("/health", response_model=HealthResponse)
async def qbank_v2_health() -> HealthResponse:
    return HealthResponse(**(await service.health()))


@router.get("/metadata/subjects", response_model=SubjectListResponse)
def list_subjects() -> SubjectListResponse:
    return SubjectListResponse(subjects=service.list_subjects())


@router.get("/metadata/chapters", response_model=ChapterListResponse)
def list_chapters(
    subject: str | None = Query(default=None, min_length=1),
) -> ChapterListResponse:
    return ChapterListResponse(chapters=service.list_chapters(subject))


@router.get("/metadata/topics", response_model=TopicListResponse)
def list_topics(
    subject: str | None = Query(default=None, min_length=1),
    chapter: str | None = Query(default=None, min_length=1),
) -> TopicListResponse:
    return TopicListResponse(topics=service.list_topics(subject, chapter))


# ============================================
# Sprint 10: New Backend Integration Endpoints
# ============================================

@router.get("/activity", response_model=ActivityFeedResponse)
def get_activity_feed(
    limit: int = Query(default=20, ge=1, le=100),
) -> ActivityFeedResponse:
    """Get recent activity feed for the team."""
    # For now, generate activity based on recent job data
    jobs, _ = service.list_jobs(limit=limit, offset=0)
    
    activities: list[ActivityItem] = []
    for job in jobs:
        # Add generation activity
        activities.append(ActivityItem(
            id=f"act_{job['job_id']}_gen",
            activity_type=ActivityType.generated,
            user_id="admin",
            user_name="Admin User",
            target_type="batch",
            target_id=job["job_id"],
            target_label=f"{job.get('selected_subject', 'Unknown')} - {job.get('generated_count', 0)} questions",
            timestamp=datetime.fromisoformat(job["timestamps"]["created_at"].replace("Z", "+00:00")) if isinstance(job["timestamps"]["created_at"], str) else job["timestamps"]["created_at"],
        ))
        
        # Add published activity if applicable
        if job.get("status") == "published":
            activities.append(ActivityItem(
                id=f"act_{job['job_id']}_pub",
                activity_type=ActivityType.published,
                user_id="admin",
                user_name="Admin User",
                target_type="batch",
                target_id=job["job_id"],
                target_label=f"{job.get('selected_subject', 'Unknown')} batch",
                timestamp=datetime.fromisoformat(job["timestamps"].get("published_at", job["timestamps"]["updated_at"]).replace("Z", "+00:00")) if isinstance(job["timestamps"].get("published_at", job["timestamps"]["updated_at"]), str) else job["timestamps"].get("published_at", job["timestamps"]["updated_at"]),
            ))
    
    # Sort by timestamp descending
    activities.sort(key=lambda x: x.timestamp, reverse=True)
    
    return ActivityFeedResponse(items=activities[:limit], total=len(activities))


@router.get("/usage", response_model=TokenUsageResponse)
def get_token_usage(
    days: int = Query(default=7, ge=1, le=30),
    user_id: str | None = Query(default=None, description="Filter by user (admin only)"),
    user: Any = Depends(require_auth_or_api_key),
) -> TokenUsageResponse:
    """Get token usage statistics for the dashboard.
    
    - Admin / API key: sees all users (or filtered by user_id param)
    - Regular user: sees only their own usage
    """
    from question_banks.v2.pricing import usd_to_inr
    from question_banks.v2.schemas_auth import UserRole

    # Determine filtering
    effective_user_id: str | None = None
    if user is None:
        # API key auth → admin access, optionally filter by user_id param
        effective_user_id = user_id
    elif hasattr(user, "role") and user.role == UserRole.admin:
        # JWT admin → can filter by user_id or see all
        effective_user_id = user_id
    elif hasattr(user, "sub"):
        # Regular user → only own data
        effective_user_id = str(user.sub)

    # Try the new token_usage_logs table first
    log_data = service._repository.get_token_usage_logs(days=days, user_id=effective_user_id)

    if log_data:
        # Use granular log data
        daily_usage = [
            DailyUsage(
                date=d["date"],
                input_tokens=d["input_tokens"],
                output_tokens=d["output_tokens"],
                cost=d["cost"],
                cost_inr=d["cost_inr"],
                generation_tokens=d["generation_tokens"],
                qc_tokens=d["qc_tokens"],
            )
            for d in log_data
        ]
        total_input = sum(d["input_tokens"] for d in log_data)
        total_output = sum(d["output_tokens"] for d in log_data)
        total_cost = sum(d["cost"] for d in log_data)
    else:
        # Fallback: calculate from jobs (backward compat for pre-log data)
        jobs, _ = service.list_jobs(limit=100, offset=0)

        daily_data: dict[str, dict] = {}
        today = datetime.now().date()

        for i in range(days):
            date = (today - timedelta(days=i)).isoformat()
            daily_data[date] = {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}

        total_input = 0
        total_output = 0

        for job in jobs:
            job_date = job["timestamps"]["created_at"]
            if isinstance(job_date, str):
                job_date = datetime.fromisoformat(job_date.replace("Z", "+00:00"))
            date_key = job_date.date().isoformat()

            usage = job.get("token_usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            total_input += input_tokens
            total_output += output_tokens

            if date_key in daily_data:
                daily_data[date_key]["input_tokens"] += input_tokens
                daily_data[date_key]["output_tokens"] += output_tokens
                job_cost = usage.get("total_cost", 0.0)
                if not job_cost and (input_tokens or output_tokens):
                    from question_banks.v2.pricing import calculate_cost
                    model_name = (job.get("request_payload") or {}).get(
                        "generation_model", "gemini-2.5-flash"
                    )
                    cost_data = calculate_cost(model_name, input_tokens, output_tokens)
                    job_cost = cost_data["total_cost"]
                daily_data[date_key]["cost"] += job_cost

        daily_usage = [
            DailyUsage(
                date=date,
                input_tokens=data["input_tokens"],
                output_tokens=data["output_tokens"],
                cost=round(data["cost"], 4),
                cost_inr=usd_to_inr(data["cost"]),
            )
            for date, data in sorted(daily_data.items())
        ]
        total_cost = sum(d.cost for d in daily_usage)

    return TokenUsageResponse(
        daily_usage=daily_usage,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost=round(total_cost, 4),
        total_cost_inr=usd_to_inr(total_cost),
        period_days=days,
    )


@router.get("/queue", response_model=ReviewQueueResponse)
def get_review_queue(
    priority: str | None = Query(default=None, pattern="^(urgent|normal|low)$"),
    limit: int = Query(default=20, ge=1, le=100),
) -> ReviewQueueResponse:
    """Get items assigned for review."""
    # Get pending items from recent jobs
    jobs, _ = service.list_jobs(limit=10, offset=0)
    
    queue_items: list[QueueItem] = []
    item_counter = 1
    
    for job in jobs:
        # Only include running or completed jobs with pending items
        if job.get("status") not in ["running", "completed"]:
            continue
            
        # Get pending items for this job
        items, _ = service.list_items(job["job_id"], qc_status=None, review_status="pending", offset=0, limit=5)
        
        for item in items:
            # Determine priority based on job age
            job_created = job["timestamps"]["created_at"]
            if isinstance(job_created, str):
                job_created = datetime.fromisoformat(job_created.replace("Z", "+00:00"))
            
            age_hours = (datetime.now(job_created.tzinfo) - job_created).total_seconds() / 3600
            
            if age_hours < 1:
                item_priority = QueueItemPriority.urgent
            elif age_hours < 6:
                item_priority = QueueItemPriority.normal
            else:
                item_priority = QueueItemPriority.low
            
            # Filter by priority if specified
            if priority and item_priority.value != priority:
                continue
            
            queue_items.append(QueueItem(
                id=item["item_id"],
                job_id=job["job_id"],
                question=item["question"][:100] + "..." if len(item["question"]) > 100 else item["question"],
                subject=job.get("selected_subject", "Unknown"),
                chapter=job.get("selected_chapter", "Unknown"),
                priority=item_priority,
                assigned_at=job_created,
                due_at=job_created + timedelta(hours=24) if item_priority == QueueItemPriority.urgent else None,
            ))
            
            item_counter += 1
            if item_counter > limit:
                break
        
        if item_counter > limit:
            break
    
    return ReviewQueueResponse(items=queue_items[:limit], total=len(queue_items))


# In-memory comment storage (replace with database in production)
_comments_store: dict[int, list[Comment]] = {}


@router.get("/items/{item_id}/comments", response_model=CommentListResponse)
def get_item_comments(item_id: int) -> CommentListResponse:
    """Get comments for a specific item."""
    comments = _comments_store.get(item_id, [])
    return CommentListResponse(comments=comments, total=len(comments))


@router.post("/items/{item_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
def add_item_comment(item_id: int, request: CommentCreateRequest) -> Comment:
    """Add a comment to an item."""
    comment = Comment(
        id=f"cmt_{uuid.uuid4().hex[:8]}",
        item_id=item_id,
        user_id="admin",
        user_name="Admin User",
        content=request.content,
        created_at=datetime.now(),
        parent_id=request.parent_id,
    )
    
    if item_id not in _comments_store:
        _comments_store[item_id] = []
    
    _comments_store[item_id].append(comment)
    
    return comment


@router.get("/items/search", response_model=QuestionSearchResponse)
def search_questions(
    query: str | None = Query(default=None, max_length=500),
    subject: str | None = Query(default=None),
    chapter: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    cognitive_level: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> QuestionSearchResponse:
    """Search questions across all jobs using database joins."""
    items, total = service.search_items(
        query=query,
        subject=subject,
        chapter=chapter,
        topic=topic,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
        limit=limit,
        offset=offset,
    )
    
    results = [
        SearchResultItem(
            item_id=item["item_id"],
            job_id=item["job_id"],
            question=item["question"],
            subject=item["subject"],
            chapter=item["chapter"],
            difficulty=item["difficulty"] or "medium",
            similarity_score=None,
        )
        for item in items
    ]
    
    return QuestionSearchResponse(
        items=results,
        total=total,
        query=query or "",
    )

