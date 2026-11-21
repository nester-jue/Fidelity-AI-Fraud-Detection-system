import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .services.db import init_db
from .core.config import settings
from .api import auth, claims, fraud, investigations, dashboard, audit, lookup, users, chatbot
from .api import ocr, forensics, sample_claim_documents, departmental_dashboards, compliance_reports, management_reports
# Advanced NEXA Intelligence modules (enterprise upgrade)
from .api import (
    fraud_network, claim_timeline, evidence, historical_behavior,
    predictive, zim, model_performance,
)

logger = logging.getLogger("fraud_app")


def _seed_knowledge_packages():
    """Seed structured departmental knowledge packages into the knowledge base.

    Idempotent: packages already present are skipped. Disabled via
    CHATBOT_KB_SEED=false.
    """
    if not settings.CHATBOT_KB_SEED:
        return
    from .services.knowledge.packages import seed_knowledge_packages

    try:
        result = seed_knowledge_packages()
        if result["added"] or result["updated"]:
            logger.info(
                "Knowledge base sync — %s package(s) added, %s updated",
                result["added"], result["updated"],
            )
    except Exception as exc:  # pragma: no cover - defensive; startup continues
        logger.exception("Knowledge package seeding failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    init_db()
    # Seed departmental knowledge packages (Phase 5 of the Assistant roadmap)
    _seed_knowledge_packages()
    yield

app = FastAPI(
    title="FIDELITY LIFE ASSURANCE - AI Fraud Claims Detection API",
    description="Enterprise production AI fraud detection, OCR document analysis, and claims risk intelligence platform.",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(fraud.router)
app.include_router(investigations.router)
app.include_router(dashboard.router)
app.include_router(audit.router)
app.include_router(lookup.router)
app.include_router(users.router)
# New routers
app.include_router(ocr.router)
app.include_router(sample_claim_documents.router)
app.include_router(forensics.router)
app.include_router(departmental_dashboards.router)
app.include_router(compliance_reports.router)
app.include_router(management_reports.router)
# NEXA AI Intelligence Assistant (role-aware conversational chatbot)
app.include_router(chatbot.router)

# Advanced NEXA Intelligence modules (enterprise upgrade)
app.include_router(fraud_network.router)        # Phase 3 — Fraud network detection
app.include_router(claim_timeline.router)       # Phase 6 — Claim timeline reconstruction
app.include_router(evidence.router)             # Phase 9 — Digital evidence
app.include_router(historical_behavior.router)  # Phase 5 — Historical behaviour
app.include_router(predictive.router)           # Phase 11 — Predictive monitoring
app.include_router(zim.router)                  # Phase 9 — Zimbabwe intelligence
app.include_router(model_performance.router)    # Phase 13 — AI model performance

# Mount static web dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", tags=["Dashboard UI"])
async def serve_dashboard():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "organization": settings.ORGANIZATION,
        "system": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "Operational",
    }

@app.get("/dashboard", tags=["Dashboard UI"])
async def dashboard_page():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return FileResponse(index_file)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "nexa-fraud-detection-api"}
