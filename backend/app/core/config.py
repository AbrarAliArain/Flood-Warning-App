"""Runtime configuration.

Values come from the environment, with `backend/.env` as a convenience fallback
for local development. Every secret has a safe development default so the MVP
runs out of the box; anything that must change for production is surfaced by
`startup_warnings()` and logged on boot.
"""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BACKEND_DIR / ".env"


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


load_env()


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- app
APP_NAME = os.environ.get("APP_NAME", "AquaShield")
VERSION = os.environ.get("APP_VERSION", "0.4.0")
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
SEED_DEMO_DATA = _flag("SEED_DEMO_DATA", APP_ENV != "production")
# Base URL used to build links citizens and responders can open (map, media).
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "http://localhost:8000").rstrip("/")

# ---------------------------------------------------------------- LLM (optional)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = _int("LLM_TIMEOUT_SECONDS", 20)
LLM_ENABLED = bool(OPENAI_API_KEY)

# ---------------------------------------------------------------- database
DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'aquashield.db').as_posix()}"
)
DB_BACKEND = "postgres" if DATABASE_URL.startswith("postgres") else "sqlite"

# ---------------------------------------------------------------- auth
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_SECRET_IS_DEV_DEFAULT = not JWT_SECRET
if JWT_SECRET_IS_DEV_DEFAULT:
    JWT_SECRET = "aquashield-dev-only-secret-do-not-use-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = _int("JWT_EXPIRES_MINUTES", 720)
PBKDF2_ITERATIONS = _int("PBKDF2_ITERATIONS", 210_000)

# ---------------------------------------------------------------- risk model
# "auto" prefers XGBoost when it imports and a trained model exists, otherwise
# the transparent heuristic. Both produce the same 0-100 score and explanations.
RISK_MODEL = os.environ.get("RISK_MODEL", "auto").lower()
XGB_MODEL_PATH = Path(
    os.environ.get("XGB_MODEL_PATH", str(BACKEND_DIR / "models" / "flood_risk_xgb.json"))
)

# ---------------------------------------------------------------- uploads
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(BACKEND_DIR / "uploads")))
MAX_EVIDENCE_BYTES = _int("MAX_EVIDENCE_BYTES", 5 * 1024 * 1024)
ALLOWED_EVIDENCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}

# ---------------------------------------------------------------- whatsapp
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v20.0")
WHATSAPP_GRAPH_URL = os.environ.get(
    "WHATSAPP_GRAPH_URL", "https://graph.facebook.com"
).rstrip("/")
# Force demo mode even when credentials exist (useful for rehearsals and demos).
WHATSAPP_FORCE_DEMO = _flag("WHATSAPP_FORCE_DEMO", False)


def whatsapp_mode() -> str:
    """The transport that will actually be used.

    Reported verbatim to the UI so a demo dispatch is never presented as a real
    WhatsApp delivery.
    """
    if WHATSAPP_FORCE_DEMO:
        return "demo"
    if WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID:
        return "cloud_api"
    return "demo"


# ---------------------------------------------------------------- geo
# Generous Sindh bounding box used to reject impossible GPS fixes.
SINDH_BOUNDS = {"min_lat": 23.4, "max_lat": 28.7, "min_lng": 66.4, "max_lng": 71.3}

# Hotspot clustering: reports within this radius belong to one cluster.
HOTSPOT_RADIUS_KM = float(os.environ.get("HOTSPOT_RADIUS_KM", "8.0"))
HOTSPOT_MIN_REPORTS = _int("HOTSPOT_MIN_REPORTS", 2)
HOTSPOT_RECENT_HOURS = _int("HOTSPOT_RECENT_HOURS", 48)


# ------------------------------------------------------- live place & weather services
# OpenStreetMap requires an identifying User-Agent; a bare httpx client is blocked.
OSM_USER_AGENT = os.environ.get("OSM_USER_AGENT", "AquaShield-FloodWarning/0.4 (contact: local-dev)")
NOMINATIM_URL = os.environ.get(
    "NOMINATIM_URL", "https://nominatim.openstreetmap.org/search"
).rstrip("/")
# Public Overpass mirrors. The primary endpoint 504s under load and 429s when
# queried too often, so falling over to a mirror beats shrinking the query.
_DEFAULT_OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter,"
    "https://overpass.kumi.systems/api/interpreter"
)
OVERPASS_URLS = [
    u.strip().rstrip("/")
    for u in os.environ.get("OVERPASS_URLS", "").split(",")
    if u.strip()
] or [
    u.strip().rstrip("/")
    for u in (
        os.environ.get("OVERPASS_URL") or _DEFAULT_OVERPASS_URLS
    ).split(",")
    if u.strip()
]
OPEN_METEO_URL = os.environ.get(
    "OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"
).rstrip("/")

# Master switch: with this off the app serves only the curated Sindh registry and
# the weather tiles report unavailable instead of guessing.
LIVE_GEO_ENABLED = _flag("LIVE_GEO_ENABLED", True)
LIVE_GEO_TIMEOUT_SECONDS = _int("LIVE_GEO_TIMEOUT_SECONDS", 12)
# Overpass is far slower than Nominatim and 504s on heavy queries; it needs its
# own budget, and a timed-out lookup is retried over a smaller radius.
OVERPASS_TIMEOUT_SECONDS = _int("OVERPASS_TIMEOUT_SECONDS", 18)
# Floor for the shrinking retry ladder; keeps worst-case total wait near 36s.
OVERPASS_MIN_TIMEOUT_SECONDS = _int("OVERPASS_MIN_TIMEOUT_SECONDS", 8)
OVERPASS_RETRY_RADIUS_DIVISOR = float(os.environ.get("OVERPASS_RETRY_RADIUS_DIVISOR", "4.0"))
OVERPASS_MAX_ATTEMPTS = _int("OVERPASS_MAX_ATTEMPTS", 2)
# Global back-off after a 429: keep hammering a rate-limited service and the
# block only gets longer.
OVERPASS_COOLDOWN_SECONDS = _int("OVERPASS_COOLDOWN_SECONDS", 120)
LIVE_GEO_CACHE_TTL_SECONDS = _int("LIVE_GEO_CACHE_TTL_SECONDS", 900)
# A failed lookup is cached only briefly, so one timeout does not blind the app
# to a city for the whole success TTL.
NEGATIVE_CACHE_TTL_SECONDS = _int("NEGATIVE_CACHE_TTL_SECONDS", 60)
WEATHER_CACHE_TTL_SECONDS = _int("WEATHER_CACHE_TTL_SECONDS", 600)
# Radius for live OpenStreetMap point-of-interest lookups around a city centre.
# Kept modest on purpose: a wide box over a dense city is what makes Overpass 504.
SAFE_LOCATION_RADIUS_KM = float(os.environ.get("SAFE_LOCATION_RADIUS_KM", "10.0"))
SAFE_LOCATION_MAX_RESULTS = _int("SAFE_LOCATION_MAX_RESULTS", 12)


def startup_warnings() -> list[str]:
    """Honest, human-readable list of the degraded/demo modes the app is in."""
    warnings: list[str] = []
    if JWT_SECRET_IS_DEV_DEFAULT:
        warnings.append("JWT_SECRET is not set — using an insecure development secret.")
    if SEED_DEMO_DATA:
        warnings.append("SEED_DEMO_DATA is enabled — clearly labelled demo accounts are available.")
    if whatsapp_mode() == "demo":
        warnings.append(
            "WhatsApp credentials absent — emergency dispatch runs in DEMO mode "
            "(no real message is delivered)."
        )
    if not LLM_ENABLED:
        warnings.append(
            "OPENAI_API_KEY not set — AI report analysis and insights use the "
            "deterministic offline fallback."
        )
    if not LIVE_GEO_ENABLED:
        warnings.append(
            "LIVE_GEO_ENABLED is off — Nearby Safe Locations serves only the curated "
            "Sindh registry and weather reports as unavailable."
        )
    try:
        import xgboost  # noqa: F401
    except ImportError:
        warnings.append(
            "xgboost not installed — risk engine uses the transparent heuristic scorer."
        )
    else:
        if not XGB_MODEL_PATH.exists():
            warnings.append(
                f"XGBoost model file missing ({XGB_MODEL_PATH.name}) — "
                "risk engine uses the transparent heuristic scorer. "
                "Run `python scripts/train_risk_model.py` to generate one."
            )
    return warnings
