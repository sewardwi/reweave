"""Typed environment access.

Replaces ``django-environ``: a dependency we would have carried mainly to save these thirty
lines, at the cost of an untyped surface running through every setting.

The important behavior is ``required()``. A missing secret raises at import time, so the process
refuses to start rather than booting in a subtly wrong configuration — including in the
environment where someone forgot to set it.
"""

from __future__ import annotations

import os
from urllib.parse import unquote, urlparse

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class MissingSetting(RuntimeError):
    """A required environment variable is absent. Not recoverable; do not catch."""


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        msg = f"{name} is required but not set (see .env.example)"
        raise MissingSetting(msg)
    return value


def optional(name: str, default: str = "") -> str:
    return os.environ.get(name) or default


def boolean(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def csv_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def database(name: str = "DATABASE_URL") -> dict[str, object]:
    """Parse a ``postgres://user:pass@host:port/dbname`` URL into Django's DATABASES entry."""
    url = urlparse(required(name))
    if url.scheme not in {"postgres", "postgresql"}:
        msg = f"{name}: only postgres URLs are supported, got '{url.scheme}' (ADR-0013)"
        raise MissingSetting(msg)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(url.path.lstrip("/")),
        "USER": unquote(url.username or ""),
        "PASSWORD": unquote(url.password or ""),
        "HOST": url.hostname or "",
        "PORT": str(url.port or ""),
        "CONN_MAX_AGE": 60,
    }
