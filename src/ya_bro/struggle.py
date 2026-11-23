"""Struggle detector (ADR-0010): "you stuck, bro?", with the back-off that keeps it polite.

Pure logic over content-free observations (a kind, a short token, a number); no I/O except the
small state file, and time comes from an injected clock, so every scenario replays exactly.
Observations are types and counts only: a command *name*, an exit code, a menu or dialog id. Never
typed text, command lines, output or screen content (SPEC §7).

Flow: sources call `observe`; the host calls `poll` (after observations and on a timer); a returned
`Offer` is shown once, and the user's answer goes to `answer`. Nothing here ever acts for the user.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from ya_bro import dirs

HALF_LIFE = 90.0  # seconds for a signal's weight to halve
BREAKPOINT_WINDOW = 5.0  # an offer must come within this long after a breakpoint
IDLE_BREAKPOINT = 5.0
TYPING_QUIET = 3.0  # no offer within this long of typing
OFFER_COOLDOWN = 120.0
QUIET_AFTER_TWO_NOS = 30 * 60.0
LEARN_WINDOW = 7 * 24 * 3600.0
MAX_PER_HOUR, MAX_PER_DAY = 3, 10
SENSITIVITY_THETA = {1: 2.5, 2: 1.4, 3: 1.0, 4: 0.6}  # the "volume": 1 quiet .. 4 eager
DEFAULT_SENSITIVITY = 2
_TOKEN = re.compile(r"[A-Za-z0-9_.:/-]{0,64}")
_APP = re.compile(r"[A-Za-z0-9_.-]{1,64}")


class Signal(StrEnum):
    FAILING_COMMANDS = "failing_commands"
    APP_ERROR_CODE = "app_error_code"
    ERROR_LOOP = "error_loop"
    DIALOG_BOUNCE = "dialog_bounce"
    MENU_THRASH = "menu_thrash"
    FOCUS_PINGPONG = "focus_pingpong"
    UNDO_LOOP = "undo_loop"
    HELP_SEEKING = "help_seeking"
    IDLE_IN_CONTEXT = "idle_in_context"


@dataclass(frozen=True)
class Rule:
    """`count` matching observations within `window` seconds make the signal fire once."""

    signal: Signal
    weight: float
    count: int
    window: float
    plain: str  # the offer's explanation of this signal; {n} is how many were seen


RULES: dict[Signal, Rule] = {
    r.signal: r
    for r in (
        Rule(Signal.FAILING_COMMANDS, 1.5, 3, 300.0, "{n} failed commands of the same name"),
        Rule(Signal.APP_ERROR_CODE, 1.5, 2, 300.0, "the same error code {n} times"),
        Rule(Signal.ERROR_LOOP, 1.5, 2, 300.0, "{n} error dialogs"),
        Rule(Signal.DIALOG_BOUNCE, 1.2, 2, 60.0, "{n} dialogs opened and cancelled at once"),
        Rule(Signal.MENU_THRASH, 1.0, 3, 20.0, "the same menu opened and closed {n} times"),
        Rule(Signal.FOCUS_PINGPONG, 0.8, 6, 60.0, "{n} jumps between the same two windows"),
        Rule(Signal.UNDO_LOOP, 0.6, 4, 30.0, "{n} undos"),
        Rule(Signal.HELP_SEEKING, 0.8, 1, 60.0, "help opened (x{n})"),
        Rule(Signal.IDLE_IN_CONTEXT, 1.0, 1, 60.0, "a pause in the middle of something (x{n})"),
    )
}
IDLE_SECONDS = 20.0  # no input this long, with something unfinished, is a pause


class ContentError(ValueError):
    """Raised for anything that is not a short token: free text never enters the detector."""


@dataclass(frozen=True, slots=True)
class Observation:
    """What a source saw. `kind` is one of KINDS; `key` a short token; `value` a number."""

    t: float
    app: str
    kind: str
    key: str = ""
    value: int = 0


KINDS = frozenset(
    {
        "command_exit",  # key argv0, value exit code
        "error_code",  # key = the app's own error code
        "menu_shown", "menu_hidden", "menu_activated",  # key = menu id
        "dialog_opened", "dialog_cancelled", "dialog_closed",  # key = dialog id
        "alert",  # key = alert id
        "focus",  # key = window id
        "undo", "help_opened", "typing",
        "idle",  # value = seconds without input
        "context",  # the task or screen changed: earlier "no" answers no longer apply
    }
)  # fmt: skip


@dataclass(frozen=True)
class Offer:
    app: str
    signals: dict[str, int]  # signal name -> times seen
    score: float
    t: float
    why: str


@dataclass
class _AppState:
    events: deque[Observation] = field(default_factory=lambda: deque(maxlen=400))
    hits: list[tuple[float, float, Signal]] = field(default_factory=list)  # (t, weight, signal)
    breakpoint: float = -1e9
    last_typing: float = -1e9
    last_failed: float = -1e9
    open_dialogs: int = 0
    idle_armed: bool = True
    suppressed: set[Signal] = field(default_factory=set)
    nos_in_a_row: int = 0
    quiet_until: float = 0.0


class Detector:
    def __init__(
        self,
        clock: Callable[[], float],
        state_path: Path | None = None,
        sensitivity: int = DEFAULT_SENSITIVITY,
    ) -> None:
        self._clock = clock
        self._path = state_path
        self.sensitivity = sensitivity
        self.enabled_globally = True
        self.fullscreen = False
        self.do_not_disturb = False
        self._apps: dict[str, _AppState] = defaultdict(_AppState)
        self._rules: dict[str, dict[Signal, Rule]] = {}  # per-app overrides
        self._offers: deque[float] = deque()
        self._last_offer = -1e9
        self._pending: Offer | None = None
        # Persisted: opt-in, user "never", the 7-day "no" log, halved weights, outcome counts.
        self._opted_in: set[str] = set()
        self._never: set[str] = set()
        self._nos: dict[str, list[float]] = {}  # "app|signal" -> times
        self._halved: set[str] = set()
        self._outcomes: dict[str, int] = {"yes": 0, "no": 0, "ignored": 0, "never": 0}
        self._load()

    # ---- settings ------------------------------------------------------------------------

    @property
    def theta(self) -> float:
        return SENSITIVITY_THETA[self.sensitivity]

    def set_sensitivity(self, step: int) -> None:
        if step not in SENSITIVITY_THETA:
            raise ValueError("sensitivity is 1 to 4")
        self.sensitivity = step
        self._save()

    def set_enabled(self, on: bool) -> None:
        """The global switch for proactive mode."""
        self.enabled_globally = on
        self._save()

    def opt_in(self, app: str) -> None:
        self._app(app)
        self._opted_in.add(app)
        self._never.discard(app)
        self._save()

    def opt_out(self, app: str) -> None:
        self._opted_in.discard(app)
        self._save()

    def is_watching(self, app: str) -> bool:
        return self.enabled_globally and app in self._opted_in and app not in self._never

    def tune(self, app: str, weights: dict[str, float] | None = None,
             counts: dict[str, tuple[int, float]] | None = None) -> None:  # fmt: skip
        """Per-app overrides (a pack's signals.toml). Bounded: a pack can tune, not force offers."""
        rules = dict(RULES)
        for name, w in (weights or {}).items():
            sig = Signal(name)
            if not 0.0 <= w <= 3.0:
                raise ValueError(f"weight for {name} must be 0 to 3")
            rules[sig] = _replace(rules[sig], weight=w)
        for name, (count, window) in (counts or {}).items():
            sig = Signal(name)
            if not (2 <= count <= 50 and 1.0 <= window <= 3600.0):
                raise ValueError(f"count and window for {name} out of range")
            rules[sig] = _replace(rules[sig], count=count, window=window)
        self._rules[app] = rules

    def reset_learning(self, app: str, signal: Signal | None = None) -> None:
        """Undo the "halved weight" learning (reversible from settings, ADR-0010 §5)."""
        for key in [k for k in self._nos if k.startswith(f"{app}|")]:
            if signal is None or key.endswith(f"|{signal.value}"):
                self._nos.pop(key, None)
                self._halved.discard(key)
        self._save()

    def weight(self, app: str, signal: Signal) -> float:
        rule = self._rules.get(app, RULES)[signal]
        return rule.weight / 2 if f"{app}|{signal.value}" in self._halved else rule.weight

    # ---- observing -----------------------------------------------------------------------

    def observe(self, obs: Observation) -> list[Signal]:
        """Take one observation; the signals it completed (already added to the score)."""
        if obs.kind not in KINDS:
            raise ContentError(f"unknown observation kind {obs.kind!r}")
        if not _APP.fullmatch(obs.app) or not _TOKEN.fullmatch(obs.key):
            raise ContentError("an app id and a key must be short tokens, never text")
        if not self.is_watching(obs.app):
            return []  # not opted in: nothing is even remembered
        st = self._app(obs.app)
        st.events.append(obs)
        fired = list(self._update(obs, st))
        for sig in fired:
            st.hits.append((obs.t, self.weight(obs.app, sig), sig))
        return fired

    def _update(self, o: Observation, st: _AppState):
        k = o.kind
        if k == "typing":
            st.last_typing = o.t
        if k == "context":
            st.suppressed.clear()
        if k == "command_exit":
            if o.value != 0:
                st.last_failed = o.t
            else:  # it worked: the failing loop for this app is over
                st.suppressed.discard(Signal.FAILING_COMMANDS)
                st.last_failed = -1e9
                st.events = deque((e for e in st.events if not _same(e, o)), maxlen=400)
        if k == "dialog_opened":
            st.open_dialogs += 1
        if k in ("dialog_closed", "dialog_cancelled"):
            st.open_dialogs = max(0, st.open_dialogs - 1)
        if k in ("dialog_closed", "dialog_cancelled", "alert", "command_exit"):
            st.breakpoint = o.t  # a natural pause: the right moment to ask
        if k == "idle":
            if o.value < min(IDLE_BREAKPOINT, IDLE_SECONDS / 2):
                st.idle_armed = True  # the user came back
            else:
                st.breakpoint = o.t
        if k == "command_exit" and o.value != 0:
            if self._count(o, st, lambda e: e.kind == "command_exit" and e.value != 0
                           and e.key == o.key, Signal.FAILING_COMMANDS):  # fmt: skip
                yield Signal.FAILING_COMMANDS
        elif k == "error_code":
            if self._count(o, st, lambda e: e.kind == "error_code" and e.key == o.key,
                           Signal.APP_ERROR_CODE):  # fmt: skip
                yield Signal.APP_ERROR_CODE
        elif k == "alert":
            if self._count(o, st, lambda e: e.kind == "alert", Signal.ERROR_LOOP):
                yield Signal.ERROR_LOOP
        elif k == "dialog_cancelled":
            quick = _recent(st, o, lambda e: e.kind == "dialog_opened" and e.key == o.key, 3.0)
            if quick and self._count(o, st, lambda e: e.kind == "dialog_cancelled"
                                     and e.key == o.key, Signal.DIALOG_BOUNCE):  # fmt: skip
                yield Signal.DIALOG_BOUNCE
        elif k == "menu_hidden":
            shown = _recent(st, o, lambda e: e.kind == "menu_shown" and e.key == o.key, 5.0)
            activated = _recent(st, o, lambda e: e.kind == "menu_activated" and e.key == o.key, 1.0)
            if (
                shown
                and not activated
                and self._count(
                    o, st, lambda e: e.kind == "menu_hidden" and e.key == o.key, Signal.MENU_THRASH
                )
            ):
                yield Signal.MENU_THRASH
        elif k == "focus":
            if self._pingpong(o, st):
                yield Signal.FOCUS_PINGPONG
        elif k == "undo":
            if self._count(o, st, lambda e: e.kind == "undo", Signal.UNDO_LOOP):
                yield Signal.UNDO_LOOP
        elif k == "help_opened":
            if self._count(o, st, lambda e: e.kind == "help_opened", Signal.HELP_SEEKING):
                yield Signal.HELP_SEEKING
        elif k == "idle" and o.value >= IDLE_SECONDS and st.idle_armed:
            unfinished = st.open_dialogs > 0 or o.t - st.last_failed <= 600.0
            if unfinished:
                st.idle_armed = False  # once per pause
                yield Signal.IDLE_IN_CONTEXT

    def _count(self, o: Observation, st: _AppState, match, signal: Signal) -> bool:
        rule = self._rules.get(o.app, RULES)[signal]
        seen = [e for e in st.events if match(e) and o.t - e.t <= rule.window]
        if len(seen) < rule.count:
            return False
        # Fired: consume what made it, so the same three failures are not counted again.
        st.events = deque((e for e in st.events if e not in seen), maxlen=400)
        return True

    def _pingpong(self, o: Observation, st: _AppState) -> bool:
        rule = self._rules.get(o.app, RULES)[Signal.FOCUS_PINGPONG]
        recent = [e for e in st.events if e.kind == "focus" and o.t - e.t <= rule.window]
        keys = {e.key for e in recent}
        if len(keys) != 2 or len(recent) < rule.count:
            return False
        alternations = sum(1 for a, b in zip(recent, recent[1:], strict=False) if a.key != b.key)
        if alternations < rule.count - 1:
            return False
        st.events = deque((e for e in st.events if e not in recent), maxlen=400)
        return True

    # ---- offering ------------------------------------------------------------------------

    def score(self, app: str, now: float | None = None) -> float:
        now = self._clock() if now is None else now
        st = self._apps.get(app)
        if st is None:
            return 0.0
        live = [h for h in st.hits if h[2] not in st.suppressed]
        return sum(w * 0.5 ** ((now - t) / HALF_LIFE) for t, w, _ in live)

    def poll(self) -> Offer | None:
        """An offer, if one is due now. At most one is pending until it is answered."""
        if self._pending is not None or not self.enabled_globally:
            return None
        now = self._clock()
        if self.fullscreen or self.do_not_disturb:
            return None
        if now - self._last_offer < OFFER_COOLDOWN:
            return None
        while self._offers and now - self._offers[0] > 86400:
            self._offers.popleft()
        if len(self._offers) >= MAX_PER_DAY:
            return None
        if sum(1 for t in self._offers if now - t <= 3600) >= MAX_PER_HOUR:
            return None
        best: tuple[float, str] | None = None
        for app, st in self._apps.items():
            if not self.is_watching(app) or now < st.quiet_until:
                continue
            if now - st.last_typing < TYPING_QUIET or now - st.breakpoint > BREAKPOINT_WINDOW:
                continue
            s = self.score(app, now)
            if s >= self.theta and (best is None or s > best[0]):
                best = (s, app)
        if best is None:
            return None
        score, app = best
        st = self._apps[app]
        rules = self._rules.get(app, RULES)
        counts: dict[str, int] = defaultdict(int)
        for t, _w, sig in st.hits:
            if sig not in st.suppressed and now - t <= 4 * HALF_LIFE:
                counts[sig.value] += rules[sig].count  # what was seen, not how often it fired
        offer = Offer(app, dict(counts), score, now, _why(app, counts, rules))
        self._pending = offer
        self._last_offer = now
        self._offers.append(now)
        return offer

    def answer(self, offer: Offer, outcome: str) -> None:
        """outcome: yes, no, ignored (the bubble faded), never (the "not for this app" button)."""
        if outcome not in self._outcomes:
            raise ValueError("outcome is yes, no, ignored or never")
        if offer is not self._pending:
            return
        self._pending = None
        now = self._clock()
        st = self._app(offer.app)
        self._outcomes[outcome] += 1
        sigs = [Signal(s) for s in offer.signals]
        if outcome == "yes":
            st.nos_in_a_row = 0
            st.hits.clear()
        elif outcome == "never":
            self._never.add(offer.app)
            self._opted_in.discard(offer.app)
        else:  # "no" and "ignored" are the same soft refusal
            st.nos_in_a_row += 1
            st.suppressed.update(sigs)  # not again until the context changes
            if st.nos_in_a_row >= 2:
                st.quiet_until = now + QUIET_AFTER_TWO_NOS
                st.nos_in_a_row = 0
            for sig in sigs:
                key = f"{offer.app}|{sig.value}"
                log = [t for t in self._nos.get(key, []) if now - t <= LEARN_WINDOW] + [now]
                self._nos[key] = log
                if len(log) >= 3:
                    self._halved.add(key)  # it learns this one is a false alarm here
        self._save()

    def stats(self) -> dict[str, int]:
        """Local outcome counts (dogfood metrics: acceptance rate, "never" rate)."""
        return dict(self._outcomes)

    # ---- state ---------------------------------------------------------------------------

    def _app(self, app: str) -> _AppState:
        if not _APP.fullmatch(app):
            raise ContentError("an app id must be a short token")
        return self._apps[app]

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._opted_in = {a for a in data["opted_in"] if _APP.fullmatch(a)}
            self._never = {a for a in data["never"] if _APP.fullmatch(a)}
            self._nos = {k: [float(t) for t in v] for k, v in data["nos"].items()}
            self._halved = set(data["halved"])
            if data.get("sensitivity") in SENSITIVITY_THETA:
                self.sensitivity = data["sensitivity"]
            self.enabled_globally = bool(data.get("enabled", True))
            self._outcomes.update({k: int(v) for k, v in data["outcomes"].items()
                                   if k in self._outcomes})  # fmt: skip
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            self._opted_in, self._never, self._nos, self._halved = set(), set(), {}, set()

    def _save(self) -> None:
        if self._path is None:
            return
        data = {
            "opted_in": sorted(self._opted_in),
            "never": sorted(self._never),
            "nos": self._nos,
            "halved": sorted(self._halved),
            "outcomes": self._outcomes,
            "sensitivity": self.sensitivity,
            "enabled": self.enabled_globally,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".struggle-")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._path)


def default_state_path() -> Path:
    return dirs.state_dir() / "struggle.json"


def _replace(rule: Rule, **kw) -> Rule:
    from dataclasses import replace

    return replace(rule, **kw)


def _same(e: Observation, o: Observation) -> bool:
    return e.kind == "command_exit" and e.key == o.key


def _recent(st: _AppState, o: Observation, match, within: float) -> bool:
    return any(match(e) and 0 <= o.t - e.t <= within for e in st.events)


def _why(app: str, counts: dict[str, int], rules: dict[Signal, Rule]) -> str:
    """The offer's explanation in plain words: signal names and counts, nothing else."""
    parts = [rules[Signal(s)].plain.format(n=n) for s, n in sorted(counts.items())]
    return f"In {app} I saw " + " and ".join(parts) + "."
