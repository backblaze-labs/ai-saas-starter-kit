import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# Single source of truth: repo-root .env. Anchored to this file's path so it
# resolves correctly regardless of where uvicorn is invoked from (local
# `cd services/api && uvicorn`, Docker WORKDIR, etc.).
REPO_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(REPO_ROOT_ENV)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

from app.config import settings  # noqa: E402
from app.runtime import auth, billing, files, health, metrics, upload  # noqa: E402

# --- Startup validation ---
# Required B2 settings are declared with empty-string defaults so that
# `Settings()` instantiation (and therefore `from main import app`) never
# raises during test collection. We instead fail fast at server startup
# with a human-readable message — uvicorn surfaces this as the first log
# line, so misconfiguration is obvious within seconds rather than turning
# into mysterious 500s on the first request.
# B2_PUBLIC_URL_BASE is intentionally NOT required: when empty the app serves
# files via short-lived presigned URLs (see repo/b2_client._public_url), so the
# file manager works fully without it. Only credentials + bucket + region are
# hard requirements for the app to boot.
REQUIRED_B2_SETTINGS = (
    ("b2_application_key_id", "B2_APPLICATION_KEY_ID"),
    ("b2_application_key", "B2_APPLICATION_KEY"),
    ("b2_bucket_name", "B2_BUCKET_NAME"),
    ("b2_region", "B2_REGION"),
)

# Exact placeholder strings shipped in .env.example. If a user copied
# the example and didn't edit it, Settings will pass the "non-empty"
# check above but every B2 call will still 403. Catch that here.
PLACEHOLDER_VALUES = frozenset({
    "your_key_id",
    "your_application_key",
    "your-bucket-name",
    "your_region",
})

# Supabase powers auth; the URL + anon key validate sessions. The service-role
# key is required too: the billing slice reads/writes plans + subscriptions with
# it on every billing request (webhook sync bypasses RLS, and plan-gating reads
# run without the caller's token). `supabase start` prints it and
# `scripts/sync-supabase-env.mjs` writes it into .env.
REQUIRED_SUPABASE_SETTINGS = (
    ("supabase_url", "SUPABASE_URL"),
    ("supabase_anon_key", "SUPABASE_ANON_KEY"),
    ("supabase_service_role_key", "SUPABASE_SERVICE_ROLE_KEY"),
)


@asynccontextmanager
async def lifespan(_app: "FastAPI"):
    missing = [
        env_name
        for attr, env_name in REQUIRED_B2_SETTINGS
        if not getattr(settings, attr)
    ]
    if missing:
        raise RuntimeError(
            "Missing required B2 configuration: "
            + ", ".join(missing)
            + f". Add them to {REPO_ROOT_ENV} (see .env.example) and restart."
        )

    placeholders = [
        env_name
        for attr, env_name in REQUIRED_B2_SETTINGS
        if getattr(settings, attr) in PLACEHOLDER_VALUES
    ]
    if placeholders:
        raise RuntimeError(
            "B2 configuration still has placeholder values: "
            + ", ".join(placeholders)
            + f". Edit {REPO_ROOT_ENV} with your real B2 credentials and restart."
        )

    missing_supabase = [
        env_name
        for attr, env_name in REQUIRED_SUPABASE_SETTINGS
        if not getattr(settings, attr)
    ]
    if missing_supabase:
        raise RuntimeError(
            "Missing required Supabase configuration: "
            + ", ".join(missing_supabase)
            + f". Add them to {REPO_ROOT_ENV} (see .env.example) and restart."
        )
    yield

# --- Structured JSON logging ---

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
# Quiet noisy libraries
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("api")


# --- App setup ---

app = FastAPI(
    title="AI Media SaaS Starter API",
    description="File upload and management API backed by Backblaze B2",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware ordering matters for CORS-on-errors ---
# Starlette wraps middleware so the LAST one registered is the OUTERMOST. We
# need CORSMiddleware to be outermost (closest to the client) so that EVERY
# response — including the 500 produced by the timing middleware's catch-all
# for an uncaught exception — flows back out through CORS and gets an
# `Access-Control-Allow-Origin` header.
#
# If CORS were registered last-but-one (inner to timing), an uncaught-exception
# 500 would be generated outside CORS and ship without that header; the browser
# would block it and the frontend would only see an opaque "network error",
# masking the real server bug. So: register the inner middleware FIRST, CORS
# LAST. Do not reorder these two without re-reading this comment.

# Request ID + timing middleware (inner). Its except-clause is the catch-all
# that turns uncaught exceptions into a typed 500 — see metrics.timing_middleware.
app.add_middleware(BaseHTTPMiddleware, dispatch=metrics.timing_middleware)

# CORS (outermost) — wraps every response, including error responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Optional regex (empty by default). When set, any origin matching
    # the pattern is allowed in addition to the explicit allowlist.
    allow_origin_regex=settings.api_cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(billing.router)
app.include_router(upload.router, tags=["upload"])
app.include_router(files.router, tags=["files"])
app.include_router(metrics.router, tags=["metrics"])
