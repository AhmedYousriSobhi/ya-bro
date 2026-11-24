"""Local policy engine (ADR-0014 §4, ADR-0009 §5): every step passes here; the model only proposes.

The effective risk of a step is the highest of what the planner said, what the pack says about
the element, and local heuristics (a bilingual deny-list on the element name, a destructive
command list). Nothing from screen text can lower it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ya_bro.packs import Pack
from ya_bro.redact import redact
from ya_bro.types import Mode, PolicyDecision, Risk, Step

# Whole words (lower-case, Arabic letters folded): exact forms, not stems, so `Payload` and
# `Position` stay R0. A miss only costs a missed warning; a pack can still declare the element.
_R3_WORDS = frozenset(
    """
    delete deletes deleting deleted remove removes removing removed erase erasing wipe wiping
    destroy purge trash discard terminate revoke uninstall
    send sends sending sent reply forward publish publishing post submit share
    buy buying purchase purchasing pay paying payment payments checkout subscribe donate
    transfer withdraw sudo
    حذف احذف ازاله مسح امسح ارسال ارسل رد نشر انشر شراء اشتري دفع ادفع تحويل سحب اشتراك
    """.split()
)
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


def _variants(word: str) -> set[str]:
    """The word, and it without Arabic's article or conjunction (`الحذف`, `والحذف`)."""
    out = {word}
    for prefix in ("وال", "ال", "و"):
        if word.startswith(prefix) and len(word) > len(prefix) + 1:
            out.add(word[len(prefix) :])
    return out


def name_risk(role: str, name: str) -> Risk:
    """Risk from an element's role and name alone."""
    if role.lower() in _SECRET_ROLES:
        return Risk.R3
    words = _WORD.findall(name.lower().translate(_FOLD))
    return Risk.R3 if any(v in _R3_WORDS for w in words for v in _variants(w)) else Risk.R0


def command_risk(command: str) -> Risk:
    """R0 for nothing, R3 for a destructive or privileged command, R2 for any other command."""
    if not command.strip():
        return Risk.R0
    return Risk.R3 if any(p.search(command) for p in _DESTRUCTIVE) else Risk.R2


def effective_risk(step: Step, pack_risk: Risk = Risk.R0, command: str = "") -> Risk:
    risk = max(step.risk, pack_risk, command_risk(command))
    if step.text:
        risk = max(risk, Risk.R2)  # typing into the user's app is confirmed in this step (#27)
    if step.target is not None:
        risk = max(risk, name_risk(step.target.role, step.target.name))
    return Risk(risk)


class LocalPolicy:
    """Decides each step. `do_it` is on only when the caller has an actuator and the app allows it.

    `packs` may raise an element's risk or mark it secret; they never lower anything (ADR-0012 §9).
    """

    def __init__(self, do_it: bool = False, packs: Iterable[Pack] = ()) -> None:
        self._do_it = do_it
        self._packs = tuple(packs)

    def _from_packs(self, step: Step) -> tuple[Risk, bool]:
        t = step.target
        if t is None:
            return Risk.R0, False
        risk, secret = Risk.R0, False
        for pack in self._packs:
            if pack.matches(app_id=t.app_id):
                risk = max(risk, pack.risk_of(t.role, t.name))
                secret = secret or pack.is_secret(t.role, t.name)
        return Risk(risk), secret

    def check(self, step: Step, mode: Mode) -> PolicyDecision:
        pack_risk, pack_secret = self._from_packs(step)
        risk = effective_risk(step, Risk.R3 if pack_secret else pack_risk)
        secret = (
            pack_secret
            or (step.target is not None and step.target.role.lower() in _SECRET_ROLES)
            or redact(step.text).changed  # a key or password is never typed for the user
        )
        if mode is Mode.SHOW_ME:
            if risk is Risk.R3:
                return PolicyDecision(True, needs_confirmation=True, reason="the user's own click")
            return PolicyDecision(True)
        if not self._do_it:
            return PolicyDecision(False, reason="Do-it is off")
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
    """The Show-me loop's policy: Do-it off."""
