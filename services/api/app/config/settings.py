from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Backblaze B2 — standardized B2_* names (S3-compatible API).
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_region: str = ""
    b2_public_url_base: str = ""

    # Supabase (auth + Postgres). Identical shape for local (`supabase start`)
    # and hosted projects — only the URL/keys differ, so swapping environments is
    # config-only.
    #
    # Single source of truth: the URL + anon key are read from the SAME
    # NEXT_PUBLIC_* vars the frontend already needs, so each value lives in ONE
    # place in .env — no duplicate SUPABASE_URL/SUPABASE_ANON_KEY to keep in sync.
    # The plain SUPABASE_* names still win when set (first alias listed), which is
    # the escape hatch for a split deploy where the backend host would rather not
    # carry NEXT_PUBLIC_* names. Neither key is a secret (the anon key is designed
    # to be public), so the backend reading the "public" names is safe.
    supabase_url: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
    )
    supabase_anon_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"),
    )
    # Server-only; must never reach the browser. The billing slice uses it for
    # every plans/subscriptions read/write, so it is required at startup (main.py).
    supabase_service_role_key: str = ""

    # Stripe billing. All optional to boot: billing endpoints return a clean 503
    # when a key is missing, so the auth + file-manager scaffold runs without
    # Stripe configured. Test-mode keys look like sk_test_… / whsec_…; get them
    # from the Stripe Dashboard in test mode. Price IDs are account-specific and
    # map a plan tier to a recurring Price in your Stripe product catalog.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_team: str = ""
    # Where Stripe returns the browser after checkout / portal. Point these at
    # your deployed frontend origin in production.
    billing_success_url: str = "http://localhost:3000/billing?checkout=success"
    billing_cancel_url: str = "http://localhost:3000/billing?checkout=cancelled"
    billing_portal_return_url: str = "http://localhost:3000/billing"

    # AI media generation via NVIDIA NIM (orchestrated by the Genblaze SDK).
    # Optional to boot: the /generation endpoint returns a clean 503 when the
    # key is missing, so the auth + billing + file-manager scaffold runs without
    # it. Get a free key (with starter credits) at https://build.nvidia.com.
    # The model + image params are env-configurable; flux.1-schnell is a fast,
    # cheap 4-step distilled model — a good default for a demo.
    nvidia_api_key: str = ""
    nvidia_image_model: str = "black-forest-labs/flux.1-schnell"
    generation_width: int = 1024
    generation_height: int = 1024
    generation_steps: int = 4
    # Provider budget: passed to the Genblaze run AND the NVIDIA client's
    # http/nvcf timeouts, so the SDK gives up on a slow provider.
    generation_run_timeout: int = 90
    # Hard request backstop: the service aborts the (blocking) generation after
    # this many seconds even if the provider ignores its own timeout — some NIM
    # endpoints hold/trickle a slow request in a way that defeats a read timeout,
    # so without this the request (and the worker) would hang indefinitely. Keep
    # it a bit above generation_run_timeout so the SDK's cleaner error wins first.
    generation_deadline: int = 120
    # B2 key prefix for generated assets: generated/{user_id}/{date}/{run_id}/...
    generation_prefix: str = "generated"

    api_port: int = 8000
    # Explicit allowlist by default — covers Next on :3000 and the
    # fallback :3001 it picks if 3000 is busy. Production deploys should
    # override with the exact frontend origin.
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # Optional dev-only escape hatch: a regex that matches additional
    # allowed origins. Empty by default — set this to e.g.
    # `^http://localhost:\d+$` to accept any localhost port without
    # listing each one. NEVER ship this to production.
    api_cors_origin_regex: str = ""

    # Upload limits
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # Small durable counters (downloads, etc). Point at a persistent
    # volume in production if you care about surviving restarts.
    download_count_file: str = "data/download_count.json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def b2_endpoint(self) -> str:
        """Derive the S3-compatible endpoint from the region.

        Standardized on B2_REGION (parent standard #3): no separate
        B2_ENDPOINT env var, no hardcoded region string in source.
        """
        return f"https://s3.{self.b2_region}.backblazeb2.com"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]


settings = Settings()
