from contextlib import asynccontextmanager
from importlib import import_module
import asyncio
import logging
from typing import Iterable

import constants
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Config, Server

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for graceful startup and shutdown"""
    # Startup
    logger.info("Application starting up...")
    
    # Start Qbank V2 Worker if enabled
    worker_task = None
    try:
        from question_banks.v2.config import get_settings as get_qbank_v2_settings
        if get_qbank_v2_settings().enabled:
             from question_banks.v2.worker import QbankV2Worker
             # Initialize worker
             worker = QbankV2Worker()
             # Run in background task
             worker_task = asyncio.create_task(worker.run_forever())
             logger.info("Started Qbank V2 Worker in background task")
    except Exception as e:
        logger.warning(f"Failed to start Qbank V2 Worker: {e}")

    yield
    
    # Shutdown
    logger.info("Application shutting down...")
    
    # Cancel worker task
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
            
    # Cancel all running asyncio tasks
    tasks = [task for task in asyncio.all_tasks() if not task.done()]
    if tasks:
        logger.info(f"Cancelling {len(tasks)} running tasks during shutdown...")
        for task in tasks:
            task.cancel()
        # Wait for tasks to complete cancellation with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), 
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("Some tasks did not complete within shutdown timeout")
    logger.info("Application shutdown complete.")


# Create an instance of the FastAPI class
app = FastAPI(lifespan=lifespan)

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Root-level health check for Docker HEALTHCHECK and deploy scripts."""
    return {
        "status": "ok",
        "version": constants.RELEASE_VERSION,
        "release_date": constants.RELEASE_DATE,
    }


ROUTER_MODULES: Iterable[tuple[str, str, str, bool]] = (
    ("question_banks.routes", "router", "question_banks", True),
    ("tutor_bots.routes", "router", "tutor_bots", False),
    ("study_plans.routes", "router", "study_plans", False),
    ("cs_qbanks.routes", "router", "cs_qbanks", False),
    ("cs_data_collection.routes", "router", "cs_data_collection", False),
    ("flashcard.routes", "router", "flashcard", False),
    ("locf.routes", "router", "locf", False),
    ("neet_predictor.routes", "router", "neet_predictor", False),
    ("result_page.routes", "router", "result_page", False),
    ("topall.routes", "router", "topall", False),
    ("ocr_qbank.routes", "router", "ocr_qbank", False),
)


def include_router(module_name: str, attr_name: str, label: str, required: bool = False) -> None:
    try:
        module = import_module(module_name)
        router = getattr(module, attr_name)
        app.include_router(router)
        logger.info("Loaded router: %s", label)
    except Exception:
        logger.exception("Failed to load router: %s", label)
        if required:
            raise


@app.get("/version")
def read_version():
    return f"{constants.RELEASE_DATE}-{constants.RELEASE_VERSION}"


# Load standard routers
for module_name, attr_name, label, required in ROUTER_MODULES:
    include_router(module_name, attr_name, label, required=required)

# Load Qbank V2 router
try:
    from question_banks.v2.config import get_settings as get_qbank_v2_settings
    from question_banks.v2.routes import router as qbank_v2_router
    from question_banks.v2.routes_auth import router as qbank_v2_auth_router

    if get_qbank_v2_settings().enabled:
        app.include_router(qbank_v2_auth_router)
        app.include_router(qbank_v2_router)
        logger.info("Loaded router: qbank_v2 and qbank_v2_auth")
except Exception:
    logger.exception("Failed to load router: qbank_v2")
  
    

if __name__ == "__main__":
    try:
        logger.info("Starting Uvicorn with multiple workers...")
        config = Config("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug", workers=1, timeout_keep_alive=2000)
        server = Server(config)
        server.run()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Shutting down gracefully...")
    except asyncio.CancelledError:
        logger.info("Server tasks were cancelled during shutdown.")
    except Exception as e:
        logger.error("An error occurred", exc_info=True)
# forcing reload
