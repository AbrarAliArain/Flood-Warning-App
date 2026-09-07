from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import alerts, analytics, auth, bulletin, cases, gauges, insights, ngos, predict, reports, risk, safe_locations, subscribe, weather, zones
from .core import config
from .core.logging_conf import get_logger
from .demo_seed import seed_demo_accounts
from .safe_locations import service as safe_location_service
from .storage.db import init_db

log = get_logger(__name__)

# Absolute path to the built frontend
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
ASSETS = DIST / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Real reference data, not demo fixtures: the curated shelter registry must
    # exist in every environment, including production.
    safe_location_service.seed_defaults()
    if config.SEED_DEMO_DATA:
        created = seed_demo_accounts()
        if created:
            log.info("seeded %s demo account(s)", len(created))
    for warning in config.startup_warnings():
        log.warning(warning)
    yield


app = FastAPI(title=config.APP_NAME, version=config.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API routers (must come BEFORE static catch-all) ---
app.include_router(auth.router)
app.include_router(zones.router)
app.include_router(gauges.router)
app.include_router(reports.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(insights.router)
app.include_router(predict.router)
app.include_router(subscribe.router)
app.include_router(bulletin.router)
app.include_router(risk.router)
app.include_router(cases.router)
app.include_router(ngos.router)
app.include_router(safe_locations.router)
app.include_router(weather.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "AquaShield", "version": "0.1.0"}


@app.get("/api/dist-check")
def dist_check():
    return {
        "dist_path": str(DIST),
        "dist_exists": DIST.exists(),
        "index_exists": (DIST / "index.html").exists(),
        "assets_exists": ASSETS.exists(),
    }


@app.get("/uploads/{evidence_name}", include_in_schema=False)
def evidence_file(evidence_name: str):
    if evidence_name in {".", ".."} or Path(evidence_name).name != evidence_name:
        raise HTTPException(status_code=404, detail="evidence not found")
    evidence = config.UPLOAD_DIR / evidence_name
    if not evidence.is_file():
        raise HTTPException(status_code=404, detail="evidence not found")
    return FileResponse(str(evidence))


# --- Serve frontend ---
@app.get("/")
def root():
    return FileResponse(str(DIST / "index.html"))


# Serve JS/CSS assets
if ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS)), name="assets")


# SPA catch-all — serves index.html for any unknown route
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    requested = DIST / full_path
    if requested.exists() and requested.is_file():
        return FileResponse(str(requested))
    return FileResponse(str(DIST / "index.html"))
