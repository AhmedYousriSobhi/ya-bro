"""The persona (ADR-0013): what the bro says, in which language, at which humour level.

Data first: `persona.toml` (moments and their humour ceilings, banned topics),
`lines/<locale>.toml` (templated lines per moment, tagged with the lowest humour setting that may
use them), `style.md` (the tone guide for the Brain's prompt). Frequent moments are templates,
chosen by locale, humour and recency, so they work offline and cost nothing; `Persona.vet` is the
deterministic filter a generated line must pass before it may be shown, and a failed line falls
back to a template.

Rules this module enforces (ADR-0013 section 3): humour never in errors, uncertainty or recovery;
never in a risk or privacy moment (`sensitive`); the user's setting is a ceiling per moment; it
drops one level when the user seems frustrated; "less chatty" mutes optional moments and humour;
"bro" at most once per task; the same line does not repeat within the last 10.
"""

from __future__ import annotations

import re
import tomllib
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any

from ya_bro import policy
from ya_bro.types import Risk

LOCALES = ("en", "ar")
HUMOUR_MAX = 3
FSI, PDI = "⁨", "⁩"  # first-strong isolate, pop isolate (ADR-0019)
_ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")
_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_FIELD = re.compile(r"\{(\w+)\}")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
FACTS = ("name", "want", "got", "why", "app", "count", "first")


class PersonaError(ValueError):
    pass


@dataclass(frozen=True)
class Moment:
    name: str
    max_humour: int
    optional: bool = False
    sensitive: bool = False


@dataclass(frozen=True)
class Line:
    moment: str
    humour: int
    text: str
    bro: bool = False
    requires: tuple[str, ...] = ()
    forbids: tuple[str, ...] = ()

    def fits(self, facts: dict[str, str]) -> bool:
        return all(facts.get(k) for k in self.requires) and not any(
            facts.get(k) for k in self.forbids
        )


@dataclass(frozen=True)
class Data:
    name: str
    max_chars: int
    recency: int
    bro_once: bool
    moments: dict[str, Moment]
    lines: dict[str, dict[str, tuple[Line, ...]]]  # locale -> moment -> lines in file order
    banned: dict[str, frozenset[str]]
    style: str


def _load_toml(*parts: str) -> dict[str, Any]:
    ref = resources.files("ya_bro.persona")
    for p in parts:
        ref = ref / p
    try:
        return tomllib.loads(ref.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise PersonaError(f"cannot read persona data {'/'.join(parts)}: {e}") from e


def _parse(doc: dict[str, Any]) -> tuple[dict[str, Moment], dict[str, frozenset[str]], dict]:
    head = doc.get("persona", {})
    moments = {}
    for name, m in doc.get("moments", {}).items():
        cap = m.get("max_humour")
        if not isinstance(cap, int) or not 0 <= cap <= HUMOUR_MAX:
            raise PersonaError(f"moment {name}: max_humour must be 0 to {HUMOUR_MAX}")
        moments[name] = Moment(name, cap, bool(m.get("optional")), bool(m.get("sensitive")))
        if moments[name].sensitive and cap != 0:
            raise PersonaError(f"moment {name}: a sensitive moment must have max_humour 0")
    banned = {
        loc: frozenset(w.lower() for w in words) for loc, words in doc.get("banned", {}).items()
    }
    return moments, banned, head


def _lines(
    locale: str, doc: dict[str, Any], moments: dict[str, Moment]
) -> dict[str, tuple[Line, ...]]:
    out: dict[str, list[Line]] = {}
    for i, raw in enumerate(doc.get("line", []), 1):
        where = f"{locale} line {i}"
        moment, humour, text = raw.get("moment"), raw.get("humour"), raw.get("text")
        if moment not in moments:
            raise PersonaError(f"{where}: unknown moment {moment!r}")
        if not isinstance(humour, int) or not 0 <= humour <= HUMOUR_MAX:
            raise PersonaError(f"{where}: humour must be 0 to {HUMOUR_MAX}")
        if humour > moments[moment].max_humour:
            raise PersonaError(
                f"{where}: {moment} allows humour up to {moments[moment].max_humour}"
            )
        if not isinstance(text, str) or not text.strip():
            raise PersonaError(f"{where}: text is required")
        for f in _FIELD.findall(text):
            if f not in FACTS:
                raise PersonaError(f"{where}: unknown placeholder {{{f}}}")
        req, forb = tuple(raw.get("requires", ())), tuple(raw.get("forbids", ()))
        if any(k not in FACTS for k in (*req, *forb)):
            raise PersonaError(f"{where}: requires/forbids must name known facts")
        out.setdefault(moment, []).append(
            Line(moment, humour, text, bool(raw.get("bro")), req, forb)
        )
    return {k: tuple(v) for k, v in out.items()}


@lru_cache(maxsize=1)
def load() -> Data:
    moments, banned, head = _parse(_load_toml("persona.toml"))
    lines = {loc: _lines(loc, _load_toml("lines", f"{loc}.toml"), moments) for loc in LOCALES}
    style = (resources.files("ya_bro.persona") / "style.md").read_text(encoding="utf-8")
    return Data(
        name=str(head.get("name", "Bro")),
        max_chars=int(head.get("max_chars", 140)),
        recency=int(head.get("recency", 10)),
        bro_once=bool(head.get("bro_once_per_task", True)),
        moments=moments,
        lines=lines,
        banned=banned,
        style=style,
    )


def _variants(word: str) -> set[str]:
    """The word, and it without Arabic's article or conjunction, for matching (`الموت`)."""
    out = {word}
    for prefix in ("وال", "بال", "ال", "و"):
        if word.startswith(prefix) and len(word) > len(prefix) + 1:
            out.add(word[len(prefix) :])
    return out


def style_guide() -> str:
    """The tone guide that rides in the Brain's frozen system prompt (ADR-0008)."""
    return load().style


def detect_locale(text: str, default: str = "en") -> str:
    """Follow the user's language: "ar" when a third of the letters are Arabic, else "en"."""
    letters = _LETTER.findall(text)
    if not letters:
        return default
    return "ar" if sum(1 for c in letters if _ARABIC.match(c)) * 3 >= len(letters) else "en"


def is_rtl(text: str) -> bool:
    return detect_locale(text) == "ar"


def isolate(text: str) -> str:
    """Wrap a UI name so its direction cannot flip the sentence around it (ADR-0019)."""
    return f"{FSI}{text}{PDI}" if text else text


@dataclass
class Persona:
    humour: int = 1
    locale: str = "en"
    less_chatty: bool = False
    sensitive: bool = False  # set by the host for the duration of a risky or private step
    frustrated: bool = False
    data: Data = field(default_factory=load, repr=False)
    _recent: deque = field(default_factory=deque, repr=False)
    _cursor: dict = field(default_factory=dict, repr=False)
    _bro_used: bool = field(default=False, repr=False)
    _mismatches: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        self.humour = max(0, min(HUMOUR_MAX, self.humour))
        if self.locale not in LOCALES:
            self.locale = "en"

    # ---- the user's state ------------------------------------------------------------------

    def follow(self, user_text: str) -> str:
        """Switch to the language the user last wrote in; returns the locale now in use."""
        self.locale = detect_locale(user_text, self.locale)
        return self.locale

    def begin_task(self) -> None:
        self._bro_used = False
        self._mismatches = 0
        self.frustrated = False

    def note_mismatch(self) -> None:
        self._mismatches += 1
        if self._mismatches >= 3:  # three wrong actions in a row: stop teasing a level
            self.frustrated = True

    def note_progress(self) -> None:
        self._mismatches = 0
        self.frustrated = False

    def effective_humour(self, moment: str | None = None) -> int:
        """The humour this moment may use now: the setting, one lower when frustrated, capped."""
        if self.less_chatty or self.sensitive:
            return 0
        h = max(0, self.humour - 1) if self.frustrated else self.humour
        if moment is not None:
            spec = self.data.moments[moment]
            if spec.sensitive:
                return 0
            h = min(h, spec.max_humour)
        return h

    # ---- saying things ---------------------------------------------------------------------

    def say(self, moment: str, **facts: str) -> str:
        """A line for this moment, "" when it is optional and the user wants less chatter."""
        spec = self.data.moments.get(moment)
        if spec is None:
            raise PersonaError(f"unknown moment {moment!r}")
        if spec.optional and self.less_chatty:
            return ""
        unknown = set(facts) - set(FACTS)
        if unknown:
            raise PersonaError(f"unknown facts {sorted(unknown)}")
        facts = {k: str(v) for k, v in facts.items()}
        locale = self.locale
        line = self._choose(moment, locale, facts) or self._choose(moment, "en", facts)
        if line is None:
            raise PersonaError(f"no {moment} line fits these facts")
        self._remember(moment, locale, line)
        return self._fill(line, facts, locale)

    def _pool(self, moment: str, locale: str, facts: dict[str, str]) -> list[Line]:
        h = self.effective_humour(moment)
        every = [ln for ln in self.data.lines.get(locale, {}).get(moment, ()) if ln.fits(facts)]
        pool = [ln for ln in every if 1 <= ln.humour <= h] if h else []
        return pool or [ln for ln in every if ln.humour == 0]

    def _choose(self, moment: str, locale: str, facts: dict[str, str]) -> Line | None:
        pool = self._pool(moment, locale, facts)
        if not pool:
            return None
        if self.data.bro_once and self._bro_used:
            pool = [ln for ln in pool if not ln.bro] or pool
        fresh = [ln for ln in pool if (locale, ln.text) not in self._recent] or pool
        index = self._cursor.get((moment, locale), 0)
        pick = fresh[index % len(fresh)]
        self._cursor[(moment, locale)] = index + 1
        return pick

    def _remember(self, moment: str, locale: str, line: Line) -> None:
        self._recent.append((locale, line.text))
        while len(self._recent) > self.data.recency:
            self._recent.popleft()
        if line.bro:
            self._bro_used = True

    def _fill(self, line: Line, facts: dict[str, str], locale: str) -> str:
        names = {"name", "want", "got", "app", "first"}
        shown = {k: (isolate(v) if k in names and locale == "ar" else v) for k, v in facts.items()}
        shown.setdefault("why", "")
        # {why} is an optional sentence: " text" when there is one.
        if shown["why"]:
            shown["why"] = " " + shown["why"]
        return line.text.format_map(_Safe(shown))

    # ---- generated lines -------------------------------------------------------------------

    def vet(self, text: str, approved_risk: bool = False) -> str | None:
        """A generated line if it may be shown, else None (the caller falls back to a template).

        One line, short, no banned topic in English or Arabic, no link or command, and no
        instruction to do something risky unless the policy-approved step itself is risky.
        """
        line = " ".join(text.split())
        if not line or len(line) > self.data.max_chars or "http" in line.lower() or "`" in line:
            return None
        words = {v for w in _WORD.findall(line) for v in _variants(w.lower())}
        if any(words & self.data.banned.get(loc, frozenset()) for loc in LOCALES):
            return None
        if not approved_risk and policy.name_risk("text", line) is Risk.R3:
            return None
        return line

    def generated_or(self, generated: str | None, moment: str, **facts: str) -> str:
        """The generated line when it passes `vet`, else the template for this moment."""
        if generated is not None and not self.data.moments[moment].sensitive:
            ok = self.vet(generated)
            if ok:
                return ok
        return self.say(moment, **facts)


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return ""


SHORT_MOMENTS = (
    "greeting",
    "offer_stuck",
    "offer_declined",
    "back_off_long",
    "step_done",
    "task_done",
)


def lint() -> list[str]:
    """Problems with the shipped persona data, empty when sound (`broctl persona lint`)."""
    data = load()
    problems: list[str] = []
    banned = frozenset().union(*data.banned.values())
    sample = {"name": "Save", "want": "7", "got": "5", "why": "Because.", "app": "GIMP"} | {
        "count": "3",
        "first": "Press 7.",
    }
    for loc in LOCALES:
        by_moment = data.lines.get(loc, {})
        for name, spec in data.moments.items():
            lines = by_moment.get(name, ())
            if not any(ln.humour == 0 for ln in lines):
                problems.append(f"{loc}/{name}: no plain (humour 0) line")
            if spec.max_humour >= 1 and sum(1 for ln in lines if ln.humour >= 1) < 3:
                problems.append(f"{loc}/{name}: fewer than 3 playful lines")
            for with_got in (True, False):
                facts = dict(sample if with_got else {**sample, "got": ""})
                for h in range(HUMOUR_MAX + 1):
                    for frustrated in (False, True):
                        p = Persona(humour=h, locale=loc)
                        p.frustrated = frustrated
                        try:
                            p.say(name, **facts)
                        except PersonaError as e:
                            problems.append(f"{loc}/{name} humour {h} got={with_got}: {e}")
            for ln in lines:
                words = {w.lower() for w in _WORD.findall(ln.text)}
                if words & banned:
                    problems.append(f"{loc}/{name}: banned word in {ln.text!r}")
                says_bro = bool({"bro", "برو"} & words)
                if says_bro != ln.bro:
                    problems.append(f"{loc}/{name}: bro flag does not match {ln.text!r}")
                has_ar = bool(_ARABIC.search(ln.text))
                if has_ar != (loc == "ar"):
                    problems.append(f"{loc}/{name}: wrong script in {ln.text!r}")
                if name in SHORT_MOMENTS and len(ln.text) > data.max_chars:
                    problems.append(f"{loc}/{name}: over {data.max_chars} characters: {ln.text!r}")
                if name in ("risk_confirm", "cant_find", "unsure") and ln.humour:
                    problems.append(f"{loc}/{name}: a sensitive or uncertain moment has humour")
    return problems
