"""Shared object-key validation primitives.

Both the file-browser service (key-addressed reads/deletes) and the upload service
(finalize ownership check) must reject path-traversal in a client-supplied B2 key.
Keeping the pattern in one place (AGENTS.md §4 — no duplicated constants) means the
two guards can never drift apart.
"""

import re

# Path-traversal / null-byte patterns that must never appear in an object key.
_TRAVERSAL_RE = re.compile(r"(\.\./|/\.\.|\\|%2e%2e|%00|\x00)")


def has_path_traversal(key: str) -> bool:
    """True if `key` contains a traversal or null-byte pattern (case-insensitive)."""
    return bool(_TRAVERSAL_RE.search(key.lower()))
