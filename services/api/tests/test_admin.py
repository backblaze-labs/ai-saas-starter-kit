"""Tests for the admin slice (B4).

The Supabase PostgREST boundary (repo/supabase_admin) is faked so the routes,
the require_admin gating (401/403), the aggregate overview, and the audited
role-change action are covered hermetically — no network, no service-role key.
"""

import pytest

from app.repo import supabase_admin
from app.types.auth import AuthUser

# --- fake repo -------------------------------------------------------------


class FakeAdminStore:
    """In-memory stand-in for the supabase_admin repo."""

    def __init__(self) -> None:
        self.audit: list[dict] = []
        self.role_calls: list[dict] = []
        self.user_exists = True

    async def count(self, table, filters=None):
        f = filters or {}
        key = f.get("role") or f.get("status")  # e.g. 'eq.admin', 'eq.active'
        return {
            ("profiles", None): 3,
            ("profiles", "eq.admin"): 1,
            ("subscriptions", "eq.active"): 2,
            ("generation_jobs", None): 5,
            ("generation_jobs", "eq.failed"): 1,
            ("files", None): 4,
            ("provider_runs", None): 5,
            ("stripe_events", None): 7,
        }.get((table, key), 0)

    async def sum_storage_bytes(self, limit=10000):
        return 123456

    async def list_users(self, limit=500):
        return [
            {"id": "u1", "email": "a@x.com", "full_name": "A", "role": "admin",
             "avatar_url": None, "created_at": "2026-07-01T00:00:00Z"},
            {"id": "u2", "email": "b@x.com", "full_name": "B", "role": "user",
             "avatar_url": None, "created_at": "2026-07-02T00:00:00Z"},
        ]

    async def list_subscriptions(self, limit=500):
        return [
            {"user_id": "u2", "plan_id": "pro", "status": "active",
             "stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1",
             "current_period_end": None, "cancel_at_period_end": False},
        ]

    async def list_jobs(self, limit=500):
        return [
            {"id": "j1", "user_id": "u2", "prompt": "a cat", "provider": "nvidia",
             "model": "flux", "status": "succeeded", "created_at": "2026-07-03T00:00:00Z",
             "files": [{"b2_key": "generated/u2/x.png", "url": "https://b2/x.png",
                        "media_type": "image/png", "size_bytes": 10}]},
        ]

    async def list_files(self, limit=500):
        return [
            {"id": "f1", "user_id": "u2", "job_id": "j1", "b2_key": "generated/u2/x.png",
             "url": "https://b2/x.png", "media_type": "image/png", "size_bytes": 10,
             "created_at": "2026-07-03T00:00:00Z"},
        ]

    async def list_provider_runs(self, limit=500):
        return [
            {"id": "p1", "job_id": "j1", "provider": "nvidia", "model": "flux",
             "run_id": "run-1", "status": "succeeded", "cost_usd": None,
             "assets_count": 1, "created_at": "2026-07-03T00:00:00Z"},
        ]

    async def list_audit_events(self, limit=500):
        return list(reversed(self.audit))

    async def update_user_role(self, *, user_id, role, access_token):
        self.role_calls.append({"user_id": user_id, "role": role, "token": access_token})
        if not self.user_exists:
            return None
        return {"id": user_id, "email": "b@x.com", "full_name": "B", "role": role,
                "created_at": "2026-07-02T00:00:00Z"}

    async def record_audit_event(self, row):
        self.audit.append(row)


@pytest.fixture
def fake_admin(monkeypatch):
    store = FakeAdminStore()
    for name in (
        "count", "sum_storage_bytes", "list_users", "list_subscriptions",
        "list_jobs", "list_files", "list_provider_runs", "list_audit_events",
        "update_user_role", "record_audit_event",
    ):
        monkeypatch.setattr(supabase_admin, name, getattr(store, name))
    return store


def _auth_as(monkeypatch, *, role: str):
    from app.service import auth as auth_service

    async def fake_user(_token: str):
        return AuthUser(id="admin-1", email="admin@x.com", role=role)

    monkeypatch.setattr(auth_service, "user_from_token", fake_user)


# --- gating ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_401_without_token(client, fake_admin):
    resp = await client.get("/admin/overview")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_overview_403_for_non_admin(client, monkeypatch, fake_admin):
    _auth_as(monkeypatch, role="user")
    resp = await client.get("/admin/overview", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 403


# --- reads -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_ok_for_admin(client, monkeypatch, fake_admin):
    _auth_as(monkeypatch, role="admin")
    resp = await client.get("/admin/overview", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["users"] == 3
    assert body["admins"] == 1
    assert body["active_subscriptions"] == 2
    assert body["failed_jobs"] == 1
    assert body["storage_bytes"] == 123456
    assert body["webhook_events"] == 7


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,expect_len",
    [
        ("/admin/users", 2),
        ("/admin/subscriptions", 1),
        ("/admin/jobs", 1),
        ("/admin/files", 1),
        ("/admin/provider-runs", 1),
    ],
)
async def test_admin_lists(client, monkeypatch, fake_admin, path, expect_len):
    _auth_as(monkeypatch, role="admin")
    resp = await client.get(path, headers={"Authorization": "Bearer x"})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == expect_len


@pytest.mark.asyncio
async def test_admin_jobs_map_files_to_assets(client, monkeypatch, fake_admin):
    _auth_as(monkeypatch, role="admin")
    resp = await client.get("/admin/jobs", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 200
    jobs = resp.json()
    assert jobs[0]["assets"][0]["key"] == "generated/u2/x.png"


# --- role change (audited) -------------------------------------------------


@pytest.mark.asyncio
async def test_set_role_403_for_non_admin(client, monkeypatch, fake_admin):
    _auth_as(monkeypatch, role="user")
    resp = await client.post(
        "/admin/users/u2/role",
        headers={"Authorization": "Bearer x"},
        json={"role": "admin"},
    )
    assert resp.status_code == 403
    assert fake_admin.role_calls == []


@pytest.mark.asyncio
async def test_set_role_rejects_invalid_role(client, monkeypatch, fake_admin):
    _auth_as(monkeypatch, role="admin")
    resp = await client.post(
        "/admin/users/u2/role",
        headers={"Authorization": "Bearer x"},
        json={"role": "superadmin"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_set_role_updates_and_audits(client, monkeypatch, fake_admin):
    _auth_as(monkeypatch, role="admin")
    resp = await client.post(
        "/admin/users/u2/role",
        headers={"Authorization": "Bearer admintoken"},
        json={"role": "admin"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "admin"
    # The PATCH ran with the caller's token (escalation-trigger requirement).
    assert fake_admin.role_calls == [
        {"user_id": "u2", "role": "admin", "token": "admintoken"}
    ]
    # And it left exactly one audit row describing the action.
    assert len(fake_admin.audit) == 1
    event = fake_admin.audit[0]
    assert event["action"] == "update_user_role"
    assert event["target_id"] == "u2"
    assert event["detail"] == {"role": "admin"}
    assert event["actor_id"] == "admin-1"


@pytest.mark.asyncio
async def test_set_role_forbids_changing_own_role(client, monkeypatch, fake_admin):
    # _auth_as mints an admin with id "admin-1"; changing your own role is blocked
    # (self-lockout guard) before any DB write or audit.
    _auth_as(monkeypatch, role="admin")
    resp = await client.post(
        "/admin/users/admin-1/role",
        headers={"Authorization": "Bearer x"},
        json={"role": "user"},
    )
    assert resp.status_code == 400
    assert fake_admin.role_calls == []
    assert fake_admin.audit == []


@pytest.mark.asyncio
async def test_set_role_404_when_user_missing(client, monkeypatch, fake_admin):
    _auth_as(monkeypatch, role="admin")
    fake_admin.user_exists = False
    resp = await client.post(
        "/admin/users/nope/role",
        headers={"Authorization": "Bearer x"},
        json={"role": "admin"},
    )
    assert resp.status_code == 404
    assert fake_admin.audit == []
