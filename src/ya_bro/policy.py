"""Local policy engine (ADR-0014 §4, ADR-0009 §5): every step passes here; the model only proposes.

The effective risk of a step is the highest of what the planner said, what the pack says about
the element, and local heuristics (a bilingual deny-list on the element name, a destructive
command list). Nothing from screen text can lower it.
"""

from __future__ import annotations

import re

from ya_bro.types import Mode, PolicyDecision, Risk, Step

# Stems, matched at the start of a word after lower-casing and Arabic letter folding.
_R3_STEMS = (
    "delet", "remov", "erase", "wipe", "send", "publish", "buy", "purchas", "pay",
    "checkout", "sudo", "uninstall", "factory",
    "حذف", "ازال", "مسح", "ارسال", "نشر", "شراء", "دفع", "شري",
)  # fmt: skip
_SECRET_ROLES = frozenset({"password text", "password_text"})
_FOLD = str.maketrans({"إ": "ا", "أ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"})
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# R3 shell patterns: irreversible or privileged. Anything else that runs is R2 (ADR-0009).
_DESTRUCTIVE = tuple(
    re.compile(p, re.I)
    for p in (
        r"(?:^|[\s;&|])sudo\b",
        r"(?:^|[\s;&|])rm\s",
        r"\bdd\s+if=",
        r"\bmkfs\b",
        r">\s*/dev/(?:sd|nvme|disk)",
        r"\bchmod\s+-R\b",
        r"\bchown\s+-R\b",
        r"\bgit\s+push\b.*--force",
        r"\bgit\s+reset\s+--hard",
        r"\bdrop\s+(?:table|database)\b",
        r"(?:curl|wget)\b.*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b",
    )
)


def name_risk(role: str, name: str) -> Risk:
    """Risk from an element's role and name alone."""
    if role.lower() in _SECRET_ROLES:
        return Risk.R3
    words = _WORD.findall(name.lower().translate(_FOLD))
    return Risk.R3 if any(w.startswith(s) for w in words for s in _R3_STEMS) else Risk.R0


def command_risk(command: str) -> Risk:
    """R0 for nothing, R3 for a destructive or privileged command, R2 for any other command."""
    if not command.strip():
        return Risk.R0
    return Risk.R3 if any(p.search(command) for p in _DESTRUCTIVE) else Risk.R2


def effective_risk(step: Step, pack_risk: Risk = Risk.R0, command: str = "") -> Risk:
    risk = max(step.risk, pack_risk, command_risk(command))
    if step.target is not None:
        risk = max(risk, name_risk(step.target.role, step.target.name))
    return Risk(risk)


class LocalPolicy:
    """Decides each step. `do_it` stays off until the actuator exists (#27)."""

    def __init__(self, do_it: bool = False) -> None:
        self._do_it = do_it

    def check(self, step: Step, mode: Mode, pack_risk: Risk = Risk.R0) -> PolicyDecision:
        risk = effective_risk(step, pack_risk)
        secret = step.target is not None and step.target.role.lower() in _SECRET_ROLES
        if mode is Mode.SHOW_ME:
            if risk is Risk.R3:
                return PolicyDecision(True, needs_confirmation=True, reason="the user's own click")
            return PolicyDecision(True)
        if not self._do_it:
            return PolicyDecision(False, reason="only Show-me is built")
        if secret:
            return PolicyDecision(False, reason="the bro never acts on a password field")
        if risk is Risk.R3:
            return PolicyDecision(
                False, needs_confirmation=True, reason="R3 is the user's own click: pointing only"
            )
        if risk is Risk.R2:
            return PolicyDecision(True, needs_confirmation=True, reason="confirm in this step")
        return PolicyDecision(True)


class ShowMePolicy(LocalPolicy):
    """The Show-me loop's policy: Do-it stays off."""
