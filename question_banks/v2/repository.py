from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

import constants
from question_banks.v2.config import get_settings
from question_banks.v2.pricing import calculate_cost
from question_banks.v2.schemas import (
    DraftItemPatchRequest,
    JobStatus,
    PublishMode,
    PublishRequest,
)

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class QbankGenerationJob(Base):
    __tablename__ = "qbank_generation_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    selected_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_chapter: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_input: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(512), nullable=False)
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)

    resolved_topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_subject_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_chapter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    input_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class QbankGenerationItem(Base):
    __tablename__ = "qbank_generation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    cognitive_level: Mapped[str] = mapped_column(String(64), nullable=False)
    question_type: Mapped[str] = mapped_column(String(128), nullable=False)
    estimated_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    concepts: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(64), nullable=True)

    qc_status: Mapped[str] = mapped_column(String(16), nullable=False)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    scores_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    recommendations_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    violations_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    category_scores_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_item_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_question_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class QbankJobEvent(Base):
    __tablename__ = "qbank_job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TokenUsageLog(Base):
    __tablename__ = "token_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(32), nullable=False)  # generation, qc, regeneration
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class QbankUser(Base):
    __tablename__ = "qbank_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="creator")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class QbankV2Repository:
    def __init__(self) -> None:
        settings = get_settings()
        self._database_url = settings.database_url
        self._engine = None
        self._session_factory = None

    def _ensure_engine(self) -> None:
        if self._session_factory is not None:
            return

        if not self._database_url:
            raise RuntimeError("QBANK_V2_DATABASE_URL or DATABASE_URL must be configured")

        self._engine = create_engine(self._database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, autocommit=False)

    @contextmanager
    def session_scope(self) -> Session:
        self._ensure_engine()
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _resolve_topic_ids(
        self,
        session: Session,
        topic_name: str,
        subject_name: str,
        chapter_name: str,
    ) -> tuple[int, int, int]:
        query = text(
            """
            SELECT t.s_no, t.s_id, t.c_id
            FROM topics t
            JOIN subjects s ON t.s_id = s.s_no
            JOIN chapters c ON t.c_id = c.s_no
            WHERE t.t_name = :topic_name
              AND s.s_name = :subject_name
              AND c.c_name = :chapter_name
            ORDER BY t.s_no DESC
            LIMIT 1
            """
        )
        row = session.execute(
            query,
            {
                "topic_name": topic_name,
                "subject_name": subject_name,
                "chapter_name": chapter_name,
            },
        ).mappings().first()
        if not row:
            raise ValueError(
                f"Topic '{topic_name}' not found under subject '{subject_name}' and chapter '{chapter_name}'"
            )
        return int(row["s_no"]), int(row["s_id"]), int(row["c_id"])

    @staticmethod
    def _resolve_subject_chapter_ids(
        session: Any, subject_name: str, chapter_name: str
    ) -> tuple[int | None, int | None]:
        """Resolve subject and chapter IDs by name (without a topic)."""
        query = text(
            """
            SELECT s.s_no as subject_id, c.s_no as chapter_id
            FROM subjects s
            JOIN chapters c ON c.s_id = s.s_no
            WHERE s.s_name = :subject_name
              AND c.c_name = :chapter_name
            LIMIT 1
            """
        )
        row = session.execute(
            query, {"subject_name": subject_name, "chapter_name": chapter_name}
        ).mappings().first()
        if row:
            return int(row["subject_id"]), int(row["chapter_id"])
        return None, None

    def list_subjects(self) -> list[str]:
        with self.session_scope() as session:
            query = text(
                """
                SELECT DISTINCT s.s_name
                FROM subjects s
                JOIN topics t ON t.s_id = s.s_no
                WHERE s.s_name IS NOT NULL
                  AND TRIM(s.s_name) <> ''
                ORDER BY s.s_name
                """
            )
            rows = session.execute(query).mappings().all()
            return [str(row["s_name"]).strip() for row in rows if row.get("s_name")]

    def list_chapters(self, subject_name: str | None = None) -> list[str]:
        with self.session_scope() as session:
            query = """
                SELECT DISTINCT c.c_name
                FROM chapters c
                JOIN topics t ON t.c_id = c.s_no
                JOIN subjects s ON t.s_id = s.s_no
                WHERE c.c_name IS NOT NULL
                  AND TRIM(c.c_name) <> ''
            """
            params: dict[str, Any] = {}
            if subject_name:
                query += " AND s.s_name = :subject_name"
                params["subject_name"] = subject_name

            query += " ORDER BY c.c_name"
            rows = session.execute(text(query), params).mappings().all()
            return [str(row["c_name"]).strip() for row in rows if row.get("c_name")]

    def list_topics(self, subject_name: str | None = None, chapter_name: str | None = None) -> list[str]:
        with self.session_scope() as session:
            query = """
                SELECT DISTINCT t.t_name
                FROM topics t
                JOIN subjects s ON t.s_id = s.s_no
                JOIN chapters c ON t.c_id = c.s_no
                WHERE t.t_name IS NOT NULL
                  AND TRIM(t.t_name) <> ''
            """
            params: dict[str, Any] = {}

            if subject_name:
                query += " AND s.s_name = :subject_name"
                params["subject_name"] = subject_name

            if chapter_name:
                query += " AND c.c_name = :chapter_name"
                params["chapter_name"] = chapter_name

            query += " ORDER BY t.t_name"
            rows = session.execute(text(query), params).mappings().all()
            return [str(row["t_name"]).strip() for row in rows if row.get("t_name")]

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.utcnow()

        with self.session_scope() as session:
            topic_name = payload.get("selected_input", "")
            # If topic is empty, skip topic resolution but still resolve subject/chapter IDs
            if topic_name and topic_name.strip():
                topic_id, subject_id, chapter_id = self._resolve_topic_ids(
                    session,
                    topic_name,
                    payload["selected_subject"],
                    payload["selected_chapter"],
                )
            else:
                # Resolve subject and chapter IDs without a topic
                topic_id = None
                subject_id, chapter_id = self._resolve_subject_chapter_ids(
                    session,
                    payload["selected_subject"],
                    payload["selected_chapter"],
                )

            # Serialize difficulty: if it's a dict (distribution), convert to JSON string
            difficulty_value = payload["difficulty"]
            if isinstance(difficulty_value, dict):
                difficulty_str = json.dumps(difficulty_value)
            else:
                difficulty_str = str(difficulty_value)

            job = QbankGenerationJob(
                job_id=str(uuid.uuid4()),
                status=JobStatus.queued.value,
                selected_subject=payload["selected_subject"],
                selected_chapter=payload["selected_chapter"],
                selected_input=payload.get("selected_input", ""),
                difficulty=difficulty_str,
                requested_count=int(payload["count"]),
                requested_by=payload["requested_by"],
                resolved_topic_id=topic_id,
                resolved_subject_id=subject_id,
                resolved_chapter_id=chapter_id,
                generated_count=0,
                passed_count=0,
                failed_count=0,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                input_cost=0.0,
                output_cost=0.0,
                total_cost=0.0,
                retry_count=0,
                request_payload=payload,
                error=None,
                created_at=now,
                updated_at=now,
                started_at=None,
                completed_at=None,
                published_at=None,
            )
            session.add(job)
            session.add(
                QbankJobEvent(
                    job_id=job.job_id,
                    event_type="queued",
                    payload={"requested_count": job.requested_count},
                    created_at=now,
                )
            )
            session.flush()
            return self._serialize_job(job)

    def add_job_event(self, job_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        with self.session_scope() as session:
            session.add(
                QbankJobEvent(
                    job_id=job_id,
                    event_type=event_type,
                    payload=payload,
                    created_at=datetime.utcnow(),
                )
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.session_scope() as session:
            job = session.get(QbankGenerationJob, job_id)
            if not job:
                return None
            return self._serialize_job(job)

    def list_jobs(self, limit: int = 20, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        with self.session_scope() as session:
            query = session.query(QbankGenerationJob)
            total = query.count()
            jobs = (
                query.order_by(QbankGenerationJob.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [self._serialize_job(job) for job in jobs], total


    def get_dashboard_stats(self) -> dict[str, Any]:
        """
        Get aggregated statistics for dashboard display.
        Returns total questions, pass rates, and token usage.
        """
        with self.session_scope() as session:
            # Count total jobs by status
            total_jobs = session.query(QbankGenerationJob).count()
            completed_jobs = session.query(QbankGenerationJob).filter(
                QbankGenerationJob.status == "completed"
            ).count()
            
            # Count total items
            total_items = session.query(QbankGenerationItem).count()
            passed_items = session.query(QbankGenerationItem).filter(
                QbankGenerationItem.qc_status == "pass"
            ).count()
            
            # Calculate pass rate
            pass_rate = int((passed_items / total_items * 100)) if total_items > 0 else 0
            
            # Sum token usage
            token_result = session.query(
                QbankGenerationJob.input_tokens,
                QbankGenerationJob.output_tokens,
                QbankGenerationJob.total_tokens,
                QbankGenerationJob.input_cost,
                QbankGenerationJob.output_cost,
                QbankGenerationJob.total_cost,
            ).all()
            
            total_input_tokens = sum(r[0] for r in token_result)
            total_output_tokens = sum(r[1] for r in token_result)
            total_tokens = sum(r[2] for r in token_result)
            total_input_cost = sum(r[3] for r in token_result)
            total_output_cost = sum(r[4] for r in token_result)
            total_cost_sum = sum(r[5] for r in token_result)
            
            return {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "total_questions": total_items,
                "passed_questions": passed_items,
                "pass_rate": pass_rate,
                "token_usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_tokens,
                    "input_cost": round(total_input_cost, 4),
                    "output_cost": round(total_output_cost, 4),
                    "total_cost": round(total_cost_sum, 4),
                }
            }

    def get_analytics(self, user_id: str | None = None, days: int = 30) -> dict[str, Any]:
        """
        Deep analytics aggregation across jobs, items, token logs, and users.
        If user_id is provided, all queries are scoped to that user only.
        """
        from sqlalchemy import func, cast, Date, case, distinct
        from datetime import timedelta

        with self.session_scope() as session:
            cutoff = datetime.utcnow() - timedelta(days=days)
            week_cutoff = datetime.utcnow() - timedelta(days=7)

            # ── Base filters ──────────────────────────────────────────
            job_filter = [QbankGenerationJob.created_at >= cutoff]
            if user_id:
                job_filter.append(QbankGenerationJob.requested_by == user_id)

            # ── 1. Summary KPIs ───────────────────────────────────────
            total_mcqs = (
                session.query(func.count(QbankGenerationItem.id))
                .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                .filter(*job_filter)
                .scalar()
            ) or 0

            mcqs_this_week = (
                session.query(func.count(QbankGenerationItem.id))
                .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                .filter(QbankGenerationJob.created_at >= week_cutoff)
                .filter(*([QbankGenerationJob.requested_by == user_id] if user_id else []))
                .scalar()
            ) or 0

            approved_count = (
                session.query(func.count(QbankGenerationItem.id))
                .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                .filter(*job_filter)
                .filter(QbankGenerationItem.review_status == "approved")
                .scalar()
            ) or 0

            rejected_count = (
                session.query(func.count(QbankGenerationItem.id))
                .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                .filter(*job_filter)
                .filter(QbankGenerationItem.review_status == "rejected")
                .scalar()
            ) or 0

            published_count = (
                session.query(func.count(QbankGenerationItem.id))
                .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                .filter(*job_filter)
                .filter(QbankGenerationItem.published == True)
                .scalar()
            ) or 0

            total_cost_usd = (
                session.query(func.coalesce(func.sum(QbankGenerationJob.total_cost), 0.0))
                .filter(*job_filter)
                .scalar()
            ) or 0.0

            approval_rate = round(approved_count / total_mcqs * 100, 1) if total_mcqs > 0 else 0.0
            rejection_rate = round(rejected_count / total_mcqs * 100, 1) if total_mcqs > 0 else 0.0

            summary = {
                "total_mcqs": total_mcqs,
                "mcqs_this_week": mcqs_this_week,
                "approval_rate": approval_rate,
                "rejection_rate": rejection_rate,
                "total_cost_usd": round(float(total_cost_usd), 4),
                "published_count": published_count,
            }

            # ── 2. Daily trend ────────────────────────────────────────
            daily_rows = (
                session.query(
                    cast(QbankGenerationJob.created_at, Date).label("date"),
                    func.sum(QbankGenerationJob.generated_count).label("count"),
                    func.sum(QbankGenerationJob.total_cost).label("cost"),
                )
                .filter(*job_filter)
                .group_by(cast(QbankGenerationJob.created_at, Date))
                .order_by(cast(QbankGenerationJob.created_at, Date))
                .all()
            )
            daily_trend = [
                {"date": str(r.date), "count": int(r.count or 0), "cost": round(float(r.cost or 0), 4)}
                for r in daily_rows
            ]

            # ── 3. By subject ─────────────────────────────────────────
            subject_rows = (
                session.query(
                    QbankGenerationJob.selected_subject.label("subject"),
                    func.sum(QbankGenerationJob.generated_count).label("count"),
                )
                .filter(*job_filter)
                .group_by(QbankGenerationJob.selected_subject)
                .order_by(func.sum(QbankGenerationJob.generated_count).desc())
                .all()
            )
            by_subject = [{"subject": r.subject, "count": int(r.count or 0)} for r in subject_rows]

            # ── 4. By chapter (top 15) ────────────────────────────────
            chapter_rows = (
                session.query(
                    QbankGenerationJob.selected_subject.label("subject"),
                    QbankGenerationJob.selected_chapter.label("chapter"),
                    func.sum(QbankGenerationJob.generated_count).label("count"),
                )
                .filter(*job_filter)
                .group_by(QbankGenerationJob.selected_subject, QbankGenerationJob.selected_chapter)
                .order_by(func.sum(QbankGenerationJob.generated_count).desc())
                .limit(15)
                .all()
            )
            by_chapter = [
                {"subject": r.subject, "chapter": r.chapter, "count": int(r.count or 0)}
                for r in chapter_rows
            ]

            # ── 5. By difficulty ──────────────────────────────────────
            diff_rows = (
                session.query(
                    QbankGenerationItem.difficulty,
                    func.count(QbankGenerationItem.id),
                )
                .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                .filter(*job_filter)
                .filter(QbankGenerationItem.difficulty.isnot(None))
                .group_by(QbankGenerationItem.difficulty)
                .all()
            )
            by_difficulty = {str(r[0]).lower(): int(r[1]) for r in diff_rows}

            # ── 6. By cognitive level ─────────────────────────────────
            cog_rows = (
                session.query(
                    QbankGenerationItem.cognitive_level,
                    func.count(QbankGenerationItem.id),
                )
                .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                .filter(*job_filter)
                .group_by(QbankGenerationItem.cognitive_level)
                .all()
            )
            by_cognitive = {str(r[0]).lower(): int(r[1]) for r in cog_rows}

            # ── 7. By user (admin only — empty for scoped users) ──────
            by_user: list[dict[str, Any]] = []
            if not user_id:
                from question_banks.v2.models_user import QbankUser
                user_rows = (
                    session.query(
                        QbankGenerationJob.requested_by.label("user_id"),
                        func.count(distinct(QbankGenerationJob.job_id)).label("job_count"),
                        func.sum(QbankGenerationJob.generated_count).label("count"),
                        func.sum(QbankGenerationJob.total_cost).label("cost"),
                    )
                    .filter(*job_filter)
                    .group_by(QbankGenerationJob.requested_by)
                    .order_by(func.sum(QbankGenerationJob.generated_count).desc())
                    .all()
                )

                # Resolve usernames
                all_user_ids = [r.user_id for r in user_rows]
                user_map: dict[str, str] = {}
                if all_user_ids:
                    try:
                        users = (
                            session.query(QbankUser.email, QbankUser.name)
                            .filter(QbankUser.email.in_(all_user_ids))
                            .all()
                        )
                        user_map = {u.email: u.name for u in users}
                    except Exception:
                        pass  # user table may not exist yet

                for r in user_rows:
                    # Compute per-user approval rate
                    u_total = (
                        session.query(func.count(QbankGenerationItem.id))
                        .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                        .filter(QbankGenerationJob.requested_by == r.user_id)
                        .filter(QbankGenerationJob.created_at >= cutoff)
                        .scalar()
                    ) or 0
                    u_approved = (
                        session.query(func.count(QbankGenerationItem.id))
                        .join(QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id)
                        .filter(QbankGenerationJob.requested_by == r.user_id)
                        .filter(QbankGenerationJob.created_at >= cutoff)
                        .filter(QbankGenerationItem.review_status == "approved")
                        .scalar()
                    ) or 0
                    u_rate = round(u_approved / u_total * 100, 1) if u_total > 0 else 0.0

                    by_user.append({
                        "user_id": r.user_id,
                        "user_name": user_map.get(r.user_id, r.user_id),
                        "count": int(r.count or 0),
                        "approval_rate": u_rate,
                        "cost": round(float(r.cost or 0), 4),
                    })

            # ── 8. Model usage ────────────────────────────────────────
            model_filter = [TokenUsageLog.created_at >= cutoff]
            if user_id:
                model_filter.append(TokenUsageLog.user_id == user_id)
            model_rows = (
                session.query(
                    TokenUsageLog.model_name,
                    func.count(TokenUsageLog.id),
                )
                .filter(*model_filter)
                .group_by(TokenUsageLog.model_name)
                .all()
            )
            model_usage = {str(r[0]): int(r[1]) for r in model_rows}

            return {
                "summary": summary,
                "daily_trend": daily_trend,
                "by_subject": by_subject,
                "by_chapter": by_chapter,
                "by_difficulty": by_difficulty,
                "by_cognitive": by_cognitive,
                "by_user": by_user,
                "model_usage": model_usage,
            }

    def get_job_or_raise(self, session: Session, job_id: str) -> QbankGenerationJob:
        job = session.get(QbankGenerationJob, job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found")
        return job

    def set_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error: dict[str, Any] | None = None,
        increment_retry: bool = False,
    ) -> dict[str, Any]:
        now = datetime.utcnow()

        with self.session_scope() as session:
            job = self.get_job_or_raise(session, job_id)
            job.status = status.value
            job.updated_at = now

            if increment_retry:
                job.retry_count += 1

            if status == JobStatus.running and not job.started_at:
                job.started_at = now

            if status in {JobStatus.completed, JobStatus.failed}:
                job.completed_at = now

            if status == JobStatus.published:
                job.published_at = now

            if error is not None:
                job.error = error

            session.add(job)
            session.flush()
            return self._serialize_job(job)

    def find_stuck_jobs(self, max_age_minutes: int = 5) -> list[str]:
        """Find jobs stuck in 'running' status for longer than max_age_minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        with self.session_scope() as session:
            rows = (
                session.query(QbankGenerationJob.job_id)
                .filter(
                    QbankGenerationJob.status == "running",
                    QbankGenerationJob.started_at < cutoff,
                )
                .all()
            )
            return [r.job_id for r in rows]

    def update_job_metrics(
        self,
        job_id: str,
        generated_inc: int,
        passed_inc: int,
        failed_inc: int,
        tokens: dict[str, int],
        gen_model: str | None = None,
        qc_model: str | None = None,
    ) -> dict[str, Any]:
        with self.session_scope() as session:
            job = self.get_job_or_raise(session, job_id)
            job.generated_count += generated_inc
            job.passed_count += passed_inc
            job.failed_count += failed_inc

            input_tokens = int(tokens.get("input_tokens", 0))
            output_tokens = int(tokens.get("output_tokens", 0))
            total_tokens_val = int(tokens.get("total_tokens", 0))

            job.input_tokens += input_tokens
            job.output_tokens += output_tokens
            job.total_tokens += total_tokens_val

            # Calculate cost based on model(s) used
            # Use a blended model name — default to the gen model for cost estimation
            model_name = gen_model or qc_model or "gemini-2.5-flash"
            cost = calculate_cost(model_name, input_tokens, output_tokens)
            job.input_cost += cost["input_cost"]
            job.output_cost += cost["output_cost"]
            job.total_cost += cost["total_cost"]

            job.updated_at = datetime.utcnow()
            session.add(job)
            session.flush()
            return self._serialize_job(job)

    def insert_generated_items(self, job_id: str, items: list[dict[str, Any]]) -> int:
        if not items:
            return 0

        now = datetime.utcnow()
        rows = []
        for item in items:
            qc_status = str(item.get("QC", "fail")).strip().lower()
            review_status = "approved" if qc_status == "pass" else "pending"
            rows.append(
                QbankGenerationItem(
                    job_id=job_id,
                    question=str(item.get("question", "")).strip(),
                    options_json=item.get("options", []),
                    correct_answer=str(item.get("correct_answer", "")).strip(),
                    explanation=str(item.get("explanation", "")).strip(),
                    cognitive_level=str(item.get("cognitive_level", "understanding")).strip().lower(),
                    question_type=str(item.get("question_type", "single_correct_answer")).strip(),
                    estimated_time=self._safe_float(item.get("estimated_time")),
                    concepts=item.get("concepts"),
                    difficulty=str(item.get("difficulty", "medium")).strip().lower() if item.get("difficulty") else None,
                    qc_status=qc_status,
                    review_status=review_status,
                    scores_json=item.get("scores"),
                    recommendations_json=item.get("recommendations"),
                    violations_json=item.get("violations"),
                    category_scores_json=item.get("categoryScores") or item.get("category_scores"),
                    raw_item_json=item,
                    edited=False,
                    published=False,
                    published_question_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )

        with self.session_scope() as session:
            session.add_all(rows)
            return len(rows)

    def list_items(
        self,
        job_id: str,
        qc_status: str | None,
        review_status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        with self.session_scope() as session:
            query = session.query(QbankGenerationItem).filter(QbankGenerationItem.job_id == job_id)

            if qc_status:
                query = query.filter(QbankGenerationItem.qc_status == qc_status)

            if review_status:
                query = query.filter(QbankGenerationItem.review_status == review_status)

            total = query.count()
            items = (
                query.order_by(QbankGenerationItem.id.asc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [self._serialize_item(item) for item in items], total

    def update_item(self, job_id: str, item_id: int, patch: DraftItemPatchRequest) -> dict[str, Any]:
        with self.session_scope() as session:
            item = (
                session.query(QbankGenerationItem)
                .filter(
                    QbankGenerationItem.job_id == job_id,
                    QbankGenerationItem.id == item_id,
                )
                .first()
            )
            if not item:
                raise ValueError(f"Item '{item_id}' not found for job '{job_id}'")

            payload = patch.model_dump(exclude_none=True)

            if "options" in payload:
                if len(payload["options"]) != 4:
                    raise ValueError("options must contain exactly 4 values")
                if item.correct_answer not in payload["options"] and "correct_answer" not in payload:
                    raise ValueError("Updated options must include the current correct_answer")
                item.options_json = payload["options"]

            if "correct_answer" in payload:
                candidate_options = payload.get("options", item.options_json)
                if payload["correct_answer"] not in candidate_options:
                    raise ValueError("correct_answer must be one of options")
                item.correct_answer = payload["correct_answer"]

            for field_name, attr_name in (
                ("question", "question"),
                ("explanation", "explanation"),
                ("cognitive_level", "cognitive_level"),
                ("question_type", "question_type"),
                ("estimated_time", "estimated_time"),
                ("concepts", "concepts"),
                ("review_status", "review_status"),
                ("rejection_comment", "rejection_comment"),
            ):
                if field_name in payload:
                    setattr(item, attr_name, payload[field_name])

            # Handle rejection_reasons as JSON
            if "rejection_reasons" in payload:
                item.rejection_reasons_json = payload["rejection_reasons"]

            item.edited = True
            item.updated_at = datetime.utcnow()
            session.add(item)
            session.flush()
            return self._serialize_item(item)


    def bulk_update_items(
        self, job_id: str, item_ids: list[int], patch: DraftItemPatchRequest
    ) -> dict[str, Any]:
        """
        Bulk update multiple items with the same patch payload.
        Useful for bulk approve/reject/delete operations.
        """
        with self.session_scope() as session:
            # Verify job exists
            self.get_job_or_raise(session, job_id)
            
            # Get all requested items
            items = (
                session.query(QbankGenerationItem)
                .filter(
                    QbankGenerationItem.job_id == job_id,
                    QbankGenerationItem.id.in_(item_ids),
                )
                .all()
            )
            
            if len(items) != len(item_ids):
                found_ids = {item.id for item in items}
                missing_ids = set(item_ids) - found_ids
                raise ValueError(f"Items not found: {missing_ids}")
            
            payload = patch.model_dump(exclude_none=True)
            updated_count = 0
            
            for item in items:
                # Apply updates (simplified - only review_status for now)
                if "review_status" in payload:
                    item.review_status = payload["review_status"]
                    item.edited = True
                    item.updated_at = datetime.utcnow()
                    session.add(item)
                    updated_count += 1
            
            session.flush()
            
            return {
                "updated_count": updated_count,
                "requested_count": len(item_ids),
            }

    def publish_items(self, job_id: str, request: PublishRequest) -> dict[str, Any]:
        with self.session_scope() as session:
            job = self.get_job_or_raise(session, job_id)
            job.status = JobStatus.publishing.value
            job.updated_at = datetime.utcnow()
            session.add(job)

            eligible_query = session.query(QbankGenerationItem).filter(
                QbankGenerationItem.job_id == job_id,
                QbankGenerationItem.qc_status == "pass",
                QbankGenerationItem.review_status == "approved",
            )

            requested_ids = []
            if request.publish_mode == PublishMode.selected:
                requested_ids = sorted(set(request.item_ids or []))
                eligible_query = eligible_query.filter(QbankGenerationItem.id.in_(requested_ids))

            eligible_items = eligible_query.all()

            if request.publish_mode == PublishMode.selected:
                skipped_count = max(0, len(requested_ids) - len(eligible_items))
            else:
                skipped_count = 0

            published_count = 0
            failed_count = 0
            published_question_ids: list[int] = []

            for item in eligible_items:
                if item.published:
                    skipped_count += 1
                    continue

                options = item.options_json or []
                if len(options) != 4 or item.correct_answer not in options:
                    failed_count += 1
                    continue

                question_type = self._normalize_question_type(item.question_type)
                cognitive_level = self._normalize_cognitive_level(item.cognitive_level)

                try:
                    insert_sql = text(
                        """
                        INSERT INTO ai_questions (
                            user_id,
                            uuid,
                            stream,
                            question,
                            correct_opt,
                            option_a,
                            option_b,
                            option_c,
                            option_d,
                            answer_desc,
                            difficulty,
                            question_type,
                            t_id,
                            s_id,
                            c_id,
                            cognitive_level,
                            keywords,
                            estimated_time,
                            "QC",
                            model,
                            model_id,
                            added_date
                        ) VALUES (
                            :user_id,
                            :uuid,
                            :stream,
                            :question,
                            :correct_opt,
                            :option_a,
                            :option_b,
                            :option_c,
                            :option_d,
                            :answer_desc,
                            :difficulty,
                            :question_type,
                            :t_id,
                            :s_id,
                            :c_id,
                            :cognitive_level,
                            :keywords,
                            :estimated_time,
                            :qc,
                            :model,
                            :model_id,
                            :added_date
                        )
                        RETURNING s_no
                        """
                    )

                    import uuid as uuid_mod
                    result = session.execute(
                        insert_sql,
                        {
                            "user_id": 0,
                            "uuid": str(uuid_mod.uuid4()),
                            "stream": 1,
                            "question": item.question,
                            "correct_opt": str(options.index(item.correct_answer) + 1),
                            "option_a": options[0],
                            "option_b": options[1],
                            "option_c": options[2],
                            "option_d": options[3],
                            "answer_desc": item.explanation,
                            "difficulty": self._resolve_difficulty_id(job.difficulty, item.difficulty),
                            "question_type": constants.question_types.get(question_type, 11),
                            "t_id": job.resolved_topic_id or 0,
                            "s_id": job.resolved_subject_id or 0,
                            "c_id": job.resolved_chapter_id or 0,
                            "cognitive_level": constants.cognitive_levels.get(cognitive_level, 2),
                            "keywords": item.concepts,
                            "estimated_time": item.estimated_time,
                            "qc": item.qc_status,
                            "model": "gemini-2.5-flash",
                            "model_id": 1,
                            "added_date": datetime.utcnow(),
                        },
                    )

                    row = result.fetchone()
                    inserted_id = int(row[0]) if row else 0
                    item.published = True
                    item.published_question_id = inserted_id
                    item.updated_at = datetime.utcnow()
                    session.add(item)

                    published_count += 1
                    published_question_ids.append(inserted_id)
                except Exception:
                    logger.exception("Failed to publish item_id=%s for job_id=%s", item.id, job_id)
                    failed_count += 1

            # Mark as published if we published anything new, OR if items were
            # already published (skipped) from a prior attempt
            any_published = session.query(QbankGenerationItem).filter(
                QbankGenerationItem.job_id == job_id,
                QbankGenerationItem.published == True,
            ).count() > 0

            if published_count or any_published:
                job.status = JobStatus.published.value
                if not job.published_at:
                    job.published_at = datetime.utcnow()
            else:
                job.status = JobStatus.completed.value

            job.updated_at = datetime.utcnow()
            session.add(job)

            session.add(
                QbankJobEvent(
                    job_id=job_id,
                    event_type="published",
                    payload={
                        "published_count": published_count,
                        "skipped_count": skipped_count,
                        "failed_count": failed_count,
                    },
                    created_at=datetime.utcnow(),
                )
            )

            return {
                "published_count": published_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
                "published_question_ids": published_question_ids,
            }

    def _serialize_job(self, job: QbankGenerationJob) -> dict[str, Any]:
        progress_percent = 0
        if job.requested_count > 0:
            progress_percent = min(100, int((job.generated_count / job.requested_count) * 100))

        return {
            "job_id": job.job_id,
            "status": job.status,
            "selected_subject": job.selected_subject,
            "selected_chapter": job.selected_chapter,
            "selected_input": job.selected_input,
            "difficulty": job.difficulty,
            "request_payload": job.request_payload,
            "progress_percent": progress_percent,
            "requested_count": job.requested_count,
            "generated_count": job.generated_count,
            "passed_count": job.passed_count,
            "failed_count": job.failed_count,
            "token_usage": {
                "input_tokens": job.input_tokens,
                "output_tokens": job.output_tokens,
                "total_tokens": job.total_tokens,
                "input_cost": round(job.input_cost, 4),
                "output_cost": round(job.output_cost, 4),
                "total_cost": round(job.total_cost, 4),
            },
            "timestamps": {
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "published_at": job.published_at,
            },
            "retry_count": job.retry_count,
            "error": job.error,
        }

    def _serialize_item(self, item: QbankGenerationItem) -> dict[str, Any]:
        return {
            "item_id": item.id,
            "job_id": item.job_id,
            "question": item.question,
            "options": item.options_json,
            "correct_answer": item.correct_answer,
            "explanation": item.explanation,
            "cognitive_level": item.cognitive_level,
            "question_type": item.question_type,
            "estimated_time": item.estimated_time,
            "concepts": item.concepts,
            "qc_status": item.qc_status,
            "review_status": item.review_status,
            "scores": item.scores_json,
            "recommendations": item.recommendations_json,
            "violations": item.violations_json,
            "category_scores": item.category_scores_json,
            "edited": item.edited,
            "published": item.published,
            "published_question_id": item.published_question_id,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _json_dumps(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value)

    @staticmethod
    def _score_total(scores: dict[str, Any] | None) -> float:
        if not scores:
            return 0.0

        total = 0.0
        for key, value in scores.items():
            if isinstance(value, (int, float)):
                total += float(value)
            elif isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, (int, float)):
                        total += float(nested)
        return total

    @staticmethod
    def _normalize_question_type(value: str | None) -> str:
        if not value:
            return "single_correct_answer"
        normalized = value.strip().replace(" ", "_").lower()
        if normalized in constants.question_types:
            return normalized
        alias = {
            "single_correct": "single_correct_answer",
            "single_correct_option": "single_correct_answer",
            "true_false": "True_false type",
        }
        return alias.get(normalized, "single_correct_answer")

    @staticmethod
    def _normalize_cognitive_level(value: str | None) -> str:
        if not value:
            return "understanding"
        normalized = value.strip().lower()
        alias = {
            "applying": "application",
            "analyze": "analyzing",
        }
        normalized = alias.get(normalized, normalized)
        if normalized in constants.cognitive_levels:
            return normalized
        return "understanding"

    @staticmethod
    def _resolve_difficulty_id(job_difficulty: str | None, item_difficulty: str | None) -> int:
        """Resolve difficulty to a numeric ID for the ai_questions table.

        Handles both:
          - Simple strings: "easy", "medium", "hard", "veryhard"
          - JSON dicts: '{"easy": 30, "medium": 50, "hard": 15, "veryhard": 5}'

        Falls back to item-level difficulty, then defaults to 2 (medium).
        """
        # 1) Try item-level difficulty first (e.g. "medium")
        if item_difficulty:
            item_key = item_difficulty.strip().lower()
            if item_key in constants.difficulty_level:
                return constants.difficulty_level[item_key]

        # 2) Try job difficulty as a plain string
        if job_difficulty:
            plain_key = job_difficulty.strip().lower()
            if plain_key in constants.difficulty_level:
                return constants.difficulty_level[plain_key]

            # 3) Try parsing as JSON dict → pick the dominant level
            try:
                dist = json.loads(job_difficulty)
                if isinstance(dist, dict) and dist:
                    dominant = max(dist, key=lambda k: dist[k])
                    return constants.difficulty_level.get(dominant.lower(), 2)
            except (json.JSONDecodeError, TypeError):
                pass

        return 2  # default: medium

    # ── Token usage log methods ────────────────────────────────────────

    def insert_token_log(
        self,
        job_id: str,
        user_id: str,
        step: str,
        model_name: str,
        tokens: dict[str, int],
    ) -> None:
        """Insert a granular token usage log entry."""
        from question_banks.v2.pricing import calculate_cost

        input_tokens = int(tokens.get("input_tokens", 0))
        output_tokens = int(tokens.get("output_tokens", 0))
        total_tokens = int(tokens.get("total_tokens", input_tokens + output_tokens))

        cost = calculate_cost(model_name, input_tokens, output_tokens)

        with self.session_scope() as session:
            log = TokenUsageLog(
                job_id=job_id,
                user_id=user_id,
                step=step,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                input_cost_usd=cost["input_cost"],
                output_cost_usd=cost["output_cost"],
                total_cost_usd=cost["total_cost"],
                created_at=datetime.utcnow(),
            )
            session.add(log)

    def get_token_usage_logs(
        self,
        days: int = 7,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get aggregated daily token usage from the logs table.
        If user_id is specified, filter by that user only.
        """
        from sqlalchemy import func, cast, Date, case
        from datetime import timedelta as td
        from question_banks.v2.pricing import usd_to_inr

        with self.session_scope() as session:
            cutoff = datetime.utcnow() - td(days=days)
            query = (
                session.query(
                    cast(TokenUsageLog.created_at, Date).label("date"),
                    func.sum(TokenUsageLog.input_tokens).label("input_tokens"),
                    func.sum(TokenUsageLog.output_tokens).label("output_tokens"),
                    func.sum(TokenUsageLog.total_cost_usd).label("cost"),
                    # Step-level breakdown
                    func.sum(
                        case(
                            (TokenUsageLog.step == "generation", TokenUsageLog.total_tokens),
                            else_=0,
                        )
                    ).label("generation_tokens"),
                    func.sum(
                        case(
                            (TokenUsageLog.step == "qc", TokenUsageLog.total_tokens),
                            else_=0,
                        )
                    ).label("qc_tokens"),
                )
                .filter(TokenUsageLog.created_at >= cutoff)
            )

            if user_id:
                query = query.filter(TokenUsageLog.user_id == user_id)

            query = query.group_by(cast(TokenUsageLog.created_at, Date)).order_by(
                cast(TokenUsageLog.created_at, Date)
            )

            results = query.all()
            return [
                {
                    "date": str(r.date),
                    "input_tokens": int(r.input_tokens or 0),
                    "output_tokens": int(r.output_tokens or 0),
                    "cost": round(float(r.cost or 0), 4),
                    "cost_inr": usd_to_inr(float(r.cost or 0)),
                    "generation_tokens": int(r.generation_tokens or 0),
                    "qc_tokens": int(r.qc_tokens or 0),
                }
                for r in results
            ]

    def search_items(
        self,
        query: str | None = None,
        subject: str | None = None,
        chapter: str | None = None,
        topic: str | None = None,
        difficulty: str | None = None,
        cognitive_level: str | None = None,
        qc_status: str | None = "pass",
        review_status: str | None = "approved",
        only_published: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        with self.session_scope() as session:
            # Base query joining items and jobs
            from sqlalchemy import or_, select
            stmt = select(QbankGenerationItem, QbankGenerationJob).join(
                QbankGenerationJob, QbankGenerationItem.job_id == QbankGenerationJob.job_id
            )

            # Apply filters
            if query:
                q = f"%{query}%"
                stmt = stmt.where(
                    or_(
                        QbankGenerationItem.question.ilike(q),
                        QbankGenerationItem.explanation.ilike(q),
                        QbankGenerationItem.concepts.ilike(q),
                    )
                )

            if subject:
                stmt = stmt.where(QbankGenerationJob.selected_subject == subject)
            if chapter:
                stmt = stmt.where(QbankGenerationJob.selected_chapter == chapter)
            if topic:
                stmt = stmt.where(QbankGenerationJob.selected_input == topic)
            if difficulty:
                stmt = stmt.where(QbankGenerationItem.difficulty == difficulty.lower())
            if cognitive_level:
                stmt = stmt.where(QbankGenerationItem.cognitive_level == cognitive_level.lower())
            if qc_status:
                stmt = stmt.where(QbankGenerationItem.qc_status == qc_status)
            if review_status:
                stmt = stmt.where(QbankGenerationItem.review_status == review_status)
            if only_published:
                stmt = stmt.where(QbankGenerationItem.published == True)

            # Count total before limit/offset
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = session.execute(count_stmt).scalar() or 0

            # Apply limit/offset and order
            stmt = stmt.order_by(QbankGenerationItem.created_at.desc())
            stmt = stmt.limit(limit).offset(offset)

            results = session.execute(stmt).all()
            items = []
            for item, job in results:
                # Merge item and job data for the frontend
                d = self._serialize_item(item)
                d["subject"] = job.selected_subject
                d["chapter"] = job.selected_chapter
                d["topic"] = job.selected_input
                items.append(d)

            return items, total

    def _serialize_item(self, item: QbankGenerationItem) -> dict[str, Any]:
        return {
            "item_id": item.id,
            "job_id": item.job_id,
            "question": item.question,
            "options": item.options_json,
            "correct_answer": item.correct_answer,
            "explanation": item.explanation,
            "cognitive_level": item.cognitive_level,
            "question_type": item.question_type,
            "estimated_time": item.estimated_time,
            "concepts": item.concepts,
            "difficulty": item.difficulty,
            "qc_status": item.qc_status,
            "review_status": item.review_status,
            "scores": item.scores_json,
            "recommendations": item.recommendations_json,
            "violations": item.violations_json,
            "category_scores": item.category_scores_json,
            "edited": item.edited,
            "published": item.published,
            "published_question_id": item.published_question_id,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }

    # ── User management ────────────────────────────────────────

    def create_user(
        self,
        email: str,
        password_hash: str,
        name: str,
        role: str = "creator",
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        with self.session_scope() as session:
            user = QbankUser(
                email=email,
                password_hash=password_hash,
                name=name,
                role=role,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            session.flush()  # populate id
            return self._user_to_dict(user)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self.session_scope() as session:
            user = session.query(QbankUser).filter(QbankUser.email == email).first()
            return self._user_to_dict(user) if user else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self.session_scope() as session:
            user = session.query(QbankUser).filter(QbankUser.id == user_id).first()
            return self._user_to_dict(user) if user else None

    def list_users(self) -> list[dict[str, Any]]:
        with self.session_scope() as session:
            users = session.query(QbankUser).order_by(QbankUser.created_at.desc()).all()
            return [self._user_to_dict(u) for u in users]

    def update_user(
        self,
        user_id: int,
        *,
        role: str | None = None,
        is_active: bool | None = None,
        name: str | None = None,
    ) -> dict[str, Any] | None:
        with self.session_scope() as session:
            user = session.query(QbankUser).filter(QbankUser.id == user_id).first()
            if not user:
                return None
            if role is not None:
                user.role = role
            if is_active is not None:
                user.is_active = is_active
            if name is not None:
                user.name = name
            user.updated_at = datetime.utcnow()
            session.flush()
            return self._user_to_dict(user)

    @staticmethod
    def _user_to_dict(user: QbankUser) -> dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "password_hash": user.password_hash,
            "name": user.name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }
