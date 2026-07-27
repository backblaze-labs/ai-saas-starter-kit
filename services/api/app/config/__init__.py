from app.config.settings import Settings, settings

# Single source of truth for the app version. Lives in the config layer so both
# the runtime (main.py FastAPI `version`) and repo (b2_client user-agent, per the
# B2 sample "<slug>/<version> (backblaze-b2-samples)" standard) read one value —
# no backward import from main, no drift on a version bump.
APP_VERSION = "0.1.0"

__all__ = ["APP_VERSION", "Settings", "settings"]
