from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from question_banks.v2.routes import router as qbank_v2_router
from question_banks.v2.routes_auth import router as auth_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # On startup: recover any jobs stuck in 'running' (e.g. from hot-reload kills)
    try:
        from question_banks.v2.service import QbankV2Service
        service = QbankV2Service()
        recovered = await service.recover_stuck_jobs(max_age_minutes=5)
        if recovered:
            logger.info("Recovered %d stuck jobs on startup", recovered)
    except Exception:
        logger.exception("Startup recovery check failed")
    yield
    # Shutdown: nothing special needed


def create_app() -> FastAPI:
    load_dotenv(override=False)

    app = FastAPI(title="QBank V2 Local API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Content-Type", "Content-Length"],
    )
    app.include_router(qbank_v2_router)
    app.include_router(auth_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    host = os.getenv("QBANK_V2_HOST", "127.0.0.1")
    port = int(os.getenv("QBANK_V2_PORT", "8000"))
    uvicorn.run("main_v2_local:app", host=host, port=port, reload=True)
