import pytest
from httpx import ASGITransport, AsyncClient

from app.runtime.auth import get_current_user
from app.types.auth import AuthUser
from main import app

# Stable identity for the authenticated `auth_client` fixture. File tests key
# their fake objects under this user's prefixes (uploads/{TEST_USER_ID}/ and
# generated/{TEST_USER_ID}/) so ownership scoping resolves them as owned.
TEST_USER_ID = "u-test"


@pytest.fixture
async def client():
    """Unauthenticated client. Routes guarded by get_current_user return 401;
    the auth/billing/generation/admin suites set their own identity by
    monkeypatching auth_service.user_from_token and sending a bearer header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client():
    """Client authenticated as a fixed test user via a dependency override, so
    protected file routes resolve to a real caller id without a live Supabase.
    The override is scoped to the fixture and torn down after each test."""
    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=TEST_USER_ID, email="test@example.com", role="user"
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def clear_list_cache():
    """Clear the repo's bucket-listing cache before each test so cached
    listings never leak across tests (keeps the pagination tests hermetic)."""
    from app.repo import b2_client

    b2_client._invalidate_list_cache()
    yield


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset the per-IP rate-limit counters before each test — otherwise the
    whole suite shares one client IP and accumulates hits across tests."""
    from app.runtime import ratelimit

    ratelimit._reset_state()
    yield


@pytest.fixture(autouse=True)
def reset_shared_module_state():
    """Reset the remaining shared module state (B2 connectivity cache and the
    in-process metrics counters) so absolute-value assertions can't become
    order-dependent across the suite."""
    from app.repo import b2_client
    from app.runtime import metrics

    b2_client._health_cache = None
    with metrics._lock:
        metrics._request_count.clear()
        metrics._request_duration_sum.clear()
        metrics._upload_count = 0
        metrics._upload_errors = 0
    yield


@pytest.fixture(autouse=True)
def isolate_download_counter(tmp_path, monkeypatch):
    """Redirect the persisted download counter to a temp file per test and
    reset the in-memory counter to 0. Keeps tests hermetic and prevents
    stray writes to services/api/data/."""
    from app.config import settings
    from app.repo import counter

    counter_path = tmp_path / "download_count.json"
    monkeypatch.setattr(settings, "download_count_file", str(counter_path))
    monkeypatch.setattr(counter, "_count", 0)
    yield
