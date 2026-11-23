"""Redaction (ADR-0014 §2): secret-shaped text is replaced before it leaves the machine.

Regex only, so it misses new formats; it is the last gate, not the only one (password fields
are never read at all). Replacements name the kind, never any part of the value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S
        ),
    ),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")),
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("api-key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}")),
    ("bearer", re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{16,}")),
    (
        "credential",
        re.compile(
            r"(?i)\b([A-Za-z0-9_.-]*(?:password|passwd|secret|token|api[_-]?key)[A-Za-z0-9_.-]*)"
            r"(\s*[=:]\s*)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s\"']+)"
        ),
    ),
    ("url-password", re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@/]+(@)")),
)


@dataclass(frozen=True)
class Redacted:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return bool(self.counts)


def redact(text: str) -> Redacted:
    """The text with secret-shaped parts replaced by `[redacted:kind]`, and a count per kind."""
    counts: dict[str, int] = {}

    def swap(kind: str):
        def repl(m: re.Match[str]) -> str:
            counts[kind] = counts.get(kind, 0) + 1
            if kind == "credential":  # keep the name and separator: it is context, not the secret
                return f"{m.group(1)}{m.group(2)}[redacted:{kind}]"
            if kind == "url-password":
                return f"{m.group(1)}[redacted:{kind}]{m.group(2)}"
            if kind == "bearer":
                return f"{m.group(1)} [redacted:{kind}]"
            return f"[redacted:{kind}]"

        return repl

    for kind, pattern in _RULES:
        text = pattern.sub(swap(kind), text)
    return Redacted(text, counts)
