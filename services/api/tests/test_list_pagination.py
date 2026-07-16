"""Repo-level tests: object listing paginates past the 1000-key S3 cap.

`list_objects_v2` returns at most 1000 keys per response. These tests use a
fake client that reports `IsTruncated` so we verify the continuation token is
followed and every page is collected — the bug where stats/listings silently
capped at the first page.
"""

from datetime import UTC, datetime

from app.repo import b2_client


class _FakePaginatedS3:
    """Fake S3 client that serves pages keyed by their continuation token."""

    def __init__(self, pages_by_token: dict):
        self._pages = pages_by_token
        self.calls = 0

    def list_objects_v2(self, **kwargs):
        self.calls += 1
        # First request carries no token; subsequent ones echo NextContinuationToken.
        return self._pages[kwargs.get("ContinuationToken")]


def _obj(key: str, size: int = 10) -> dict:
    return {"Key": key, "Size": size, "LastModified": datetime.now(UTC)}


def _install_fake_client(monkeypatch) -> _FakePaginatedS3:
    pages = {
        None: {
            "Contents": [_obj("uploads/a.txt"), _obj("uploads/b.txt")],
            "IsTruncated": True,
            "NextContinuationToken": "page-2",
        },
        "page-2": {
            "Contents": [_obj("uploads/c.txt")],
            "IsTruncated": False,
        },
    }
    client = _FakePaginatedS3(pages)
    monkeypatch.setattr(b2_client, "get_s3_client", lambda: client)
    return client


def test_list_files_follows_continuation_token(monkeypatch):
    client = _install_fake_client(monkeypatch)

    files = b2_client.list_files()

    assert {f.key for f in files} == {
        "uploads/a.txt",
        "uploads/b.txt",
        "uploads/c.txt",
    }
    assert client.calls == 2  # both pages fetched, not just the first


def test_upload_stats_counts_all_pages(monkeypatch):
    _install_fake_client(monkeypatch)

    stats = b2_client.get_upload_stats()

    assert stats["total_files"] == 3
    assert stats["total_size_bytes"] == 30


def test_empty_prefix_listing_is_cached(monkeypatch):
    client = _install_fake_client(monkeypatch)

    b2_client.list_files()
    b2_client.list_files()

    # Second call is served from cache — only the first scan hit B2 (2 pages).
    assert client.calls == 2


def test_nonempty_prefix_is_not_cached(monkeypatch):
    client = _install_fake_client(monkeypatch)

    b2_client.list_files("folder/")
    b2_client.list_files("folder/")

    # Arbitrary client-supplied prefixes bypass the cache, so both calls scan.
    assert client.calls == 4


def test_mutation_invalidates_cache(monkeypatch):
    client = _install_fake_client(monkeypatch)

    b2_client.list_files()  # scan + cache (2 pages)
    b2_client._invalidate_list_cache()
    b2_client.list_files()  # cache voided → rescan (2 more)

    assert client.calls == 4
