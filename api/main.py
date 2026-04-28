"""
PROVCHAIN — FastAPI Application Entry Point
=============================================
Main application with:
- Lifespan context manager (startup/shutdown)
- CORS middleware
- Global exception handlers for ProvchainError hierarchy
- All route routers mounted under /api/v1
- Health check at /health (no prefix)
- Root / redirects to /docs

Run locally:
    uvicorn api.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from core.config import get_settings
from core.exceptions import ProvchainError

# Route imports
from api.routes import health, register, scan, alerts, evidence, notice

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("provchain")


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs on startup and shutdown."""
    settings = get_settings()
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.APP_VERSION} starting up")
    logger.info(f"  Debug mode: {settings.DEBUG}")
    logger.info(f"  GCP Project: {settings.GOOGLE_CLOUD_PROJECT or '(not set)'}")
    logger.info("=" * 60)

    # Initialize Firebase Admin SDK (required for Firestore)
    if settings.FIREBASE_CREDENTIALS_PATH:
        try:
            import firebase_admin
            from firebase_admin import credentials as fb_credentials
            cred = fb_credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred, {
                "projectId": settings.GOOGLE_CLOUD_PROJECT,
            })
            logger.info("Firebase Admin SDK initialized")
        except ValueError:
            # Already initialized (e.g., during hot reload)
            logger.debug("Firebase Admin SDK already initialized")
        except Exception as e:
            logger.warning("Firebase init failed: %s — Firestore will be unavailable", e)
    else:
        logger.warning(
            "FIREBASE_CREDENTIALS_PATH not set — Firestore will be unavailable. "
            "Set it in .env to enable asset storage."
        )

    yield  # App is running

    logger.info(f"{settings.APP_NAME} shutting down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Unified digital asset intelligence platform for Indian publishers. "
        "Register content, detect propagation anomalies, and generate "
        "legally-ready evidence bundles."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(ProvchainError)
async def provchain_error_handler(request: Request, exc: ProvchainError):
    """Handle all ProvchainError subclasses → structured JSON response."""
    logger.error(
        f"{exc.__class__.__name__}: {exc.message}",
        extra={"detail": exc.detail},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# Health check — no prefix (Cloud Run expects /health at root)
app.include_router(health.router)

# API v1 routes
app.include_router(register.router, prefix="/api/v1")
app.include_router(scan.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(notice.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return RedirectResponse(url="/docs")
