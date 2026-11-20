import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .services.db import init_db
from .core.config import settings
from .api import auth, claims, fraud, investigations, dashboard, audit, lookup, users
from .api import ocr, forensics, departmental_dashboards, compliance_reports, management_reports

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    init_db()
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
app.include_router(forensics.router)
app.include_router(departmental_dashboards.router)
app.include_router(compliance_reports.router)
app.include_router(management_reports.router)

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
