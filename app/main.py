# app/main.py
# The FastAPI application entry point.
# Sets up logging, loads config, registers routes, and starts the server.

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.config.config_loader import ConfigLoader
from app.logging_config import setup_logging
from app.services.message_service import MessageService
from app.api.webhook import router as webhook_router
from app.api.demo import router as demo_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs at startup and shutdown.
    We load the FAQ config here so the app fails fast if it's broken.
    """
    # --- STARTUP ---
    setup_logging(settings.log_level)
    logger.info("=== Trading FAQ Bot starting up ===")
    logger.info(f"Provider: {settings.provider}")
    logger.info(f"FAQ config: {settings.faq_config_path}")

    # Load FAQ config — this will raise a clear error if the file is missing/broken
    config_loader = ConfigLoader(settings.faq_config_path)
    try:
        config = config_loader.load()
        logger.info(f"Loaded {len(config.entries)} FAQ entries")
    except RuntimeError as e:
        # Print a clear error and stop startup
        logger.critical(f"STARTUP FAILED: {e}")
        raise

    # Store shared objects in app.state so routes can access them
    app.state.config_loader = config_loader
    app.state.message_service = MessageService(config_loader)

    logger.info("=== Bot is ready to receive messages ===")

    yield  # App runs here

    # --- SHUTDOWN ---
    logger.info("=== Trading FAQ Bot shutting down ===")


# Create the FastAPI app
app = FastAPI(
    title="Trading FAQ WhatsApp Bot",
    description="Rule-based trading education bot for WhatsApp",
    version="1.0.0",
    lifespan=lifespan,
)

# Register all routes
app.include_router(webhook_router)
app.include_router(demo_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch any unhandled exception.
    Log it and return 200 to prevent the provider from retrying.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # Return 200 so the provider doesn't keep retrying
    return JSONResponse(
        status_code=200,
        content={"status": "error", "detail": "Internal error — logged"},
    )


# =====================================================================
# Run directly with: python app/main.py
# Or with uvicorn: uvicorn app.main:app --host 0.0.0.0 --port 8000
# =====================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # Set to True during development
        log_level=settings.log_level.lower(),
    )
