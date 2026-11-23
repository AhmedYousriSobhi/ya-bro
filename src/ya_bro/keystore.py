"""Where the Anthropic API key lives and how it is found (ADR-0008 §9, ADR-0014 §4).

Lookup order: the environment, then the system keyring (Secret Service), then a `.env` file. The
key is never returned by a status call, never put in an error message, and never passed on a
command line: the keyring helper takes it over a pipe. Core code only; the libsecret part is
`platform/keyring.py`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

VAR = "ANTHROPIC_API_KEY"
MIN_LEN, MAX_LEN = 20, 400
SHAPE = re.compile(r"[\x21-\x7e]+")  # printable ASCII, no spaces or control characters
EXPECTED_PREFIX = "sk-ant-"


class KeyStoreError(RuntimeError):
    """A failure the user can be told about in one line. Never carries the key."""


class Backend(Protocol):
    def get(self) -> str | None: ...
    def set(self, value: str) -> None: ...
    def clear(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class Found:
    value: str
    source: str  # "environment", "keyring" or ".env file"


def default_store() -> Backend:
    from ya_bro.platform import keyring

    return keyring.SecretServiceBackend()


def check_shape(raw: str) -> str:
    """The key, stripped, or KeyStoreError. Loose on purpose: formats change, typos do not."""
    key = raw.strip()
    if not key:
        raise KeyStoreError("no key entered")
    if not SHAPE.fullmatch(key):
        raise KeyStoreError("that does not look like an API key (spaces or odd characters)")
    if not MIN_LEN <= len(key) <= MAX_LEN:
        raise KeyStoreError(
            f"that does not look like an API key (length is not {MIN_LEN}-{MAX_LEN})"
        )
    return key


def from_env(env: dict[str, str] | None = None) -> str:
    return (os.environ if env is None else env).get(VAR, "").strip()


def from_dotenv(dotenv: Path | None = None) -> str:
    try:
        for line in (dotenv or Path(".env")).read_text().splitlines():
            name, _, value = line.strip().partition("=")
            if name.strip() == VAR and value.strip():
                return value.strip().strip("\"'")
    except OSError:
        pass
    return ""


def from_store(store: Backend | None) -> str:
    """The stored key; empty when there is none or the keyring cannot be reached."""
    if store is None:
        return ""
    try:
        return store.get() or ""
    except KeyStoreError:  # no Secret Service here is the same as no stored key
        return ""


def _candidates(env, dotenv, store, first_only: bool = False) -> list[Found]:
    """The places a key is set, in lookup order. Lazy, so a key in the environment means the
    keyring (a subprocess, maybe an unlock prompt) is never asked; `status` wants them all."""
    getters = (
        ("environment", lambda: from_env(env)),
        ("keyring", lambda: from_store(store)),
        (".env file", lambda: from_dotenv(dotenv)),
    )
    found = []
    for source, get in getters:
        if value := get():
            found.append(Found(value, source))
            if first_only:
                break
    return found


def find(
    env: dict[str, str] | None = None,
    dotenv: Path | None = None,
    store: Backend | None = None,
) -> Found | None:
    """The key that wins, and where it came from. `store=None` skips the keyring."""
    found = _candidates(env, dotenv, store, first_only=True)
    return found[0] if found else None


def save(raw: str, store: Backend) -> str:
    """Validate and store a key; returns a note to show (may be empty). Never echoes the key."""
    key = check_shape(raw)
    store.set(key)
    return format_note(key)


def status_text(
    env: dict[str, str] | None = None,
    dotenv: Path | None = None,
    store: Backend | None = None,
) -> str:
    """One line for `broctl key status`: present or not and where. Never the value."""
    where = [f.source for f in _candidates(env, dotenv, store)]
    if not where:
        return "no API key set (run `broctl key set`)"
    extra = f" (also in: {', '.join(where[1:])})" if len(where) > 1 else ""
    return f"API key present, used from the {where[0]}{extra}"


def format_note(key: str) -> str:
    return (
        ""
        if key.startswith(EXPECTED_PREFIX)
        else f"note: Anthropic keys usually start with {EXPECTED_PREFIX}; stored anyway"
    )
