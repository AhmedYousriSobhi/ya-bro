"""Struggle replay eval (ADR-0010, ADR-0016): replay labelled event streams through the detector.

evals/struggle/*.json, one scenario each:
  {"id", "kind", "source": "scripted" | "recorded", "label": "struggle" | "not_struggle",
   "app": "workbench", "duration": seconds, "onset": seconds (struggle only),
   "expect_offers": n (optional: back-off scenarios), "events": [{"t", "kind", "key", "value"}]}
Event kinds are the detector's (content-free: a kind, a short token, a number) plus
  "idle_span": {"t", "value": N} the user is idle for N seconds from t (expanded to 1 s reads, as
               the host reads them), and
  "answer": {"t", "key": "yes|no|never"} the user's reply to the pending offer.
An offer nobody answers fades after 8 s and counts as ignored (ADR-0010 §4). Replay is a second-by-
second loop on a fake clock, so a run is exact and fast. No desktop, no LLM.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ya_bro.struggle import KINDS, Detector, Observation

PRECISION_GATE = 0.6
RECALL_GATE = 0.5
TIME_TO_OFFER_GATE = 45.0  # median seconds from onset
FALSE_OFFERS_PER_HOUR_GATE = 1.0  # in time that was not struggle
FADE = 8.0
EXTRA = {"idle_span", "answer"}


class EvalError(ValueError):
    pass


@dataclass(frozen=True)
class Offered:
    t: float
    app: str
    score: float
    why: str


@dataclass
class Replay:
    id: str
    kind: str
    source: str
    label: str
    onset: float
    duration: float
    expect_offers: int | None
    offers: list[Offered] = field(default_factory=list)

    @property
    def struggle(self) -> bool:
        return self.label == "struggle"

    @property
    def good(self) -> list[Offered]:
        """Offers that came while the user really was struggling."""
        return [o for o in self.offers if self.struggle and o.t >= self.onset]

    @property
    def bad(self) -> list[Offered]:
        return [o for o in self.offers if o not in self.good]

    @property
    def time_to_offer(self) -> float | None:
        return min((o.t - self.onset for o in self.good), default=None)

    @property
    def conforms(self) -> bool | None:
        return None if self.expect_offers is None else len(self.offers) == self.expect_offers


@dataclass
class Report:
    replays: list[Replay] = field(default_factory=list)
    sensitivity: int = 2

    @property
    def offers(self) -> int:
        return sum(len(r.offers) for r in self.replays)

    @property
    def precision(self) -> float:
        n = self.offers
        return sum(len(r.good) for r in self.replays) / n if n else 1.0

    @property
    def recall(self) -> float:
        s = [r for r in self.replays if r.struggle]
        return sum(1 for r in s if r.good) / len(s) if s else 0.0

    def times(self) -> list[float]:
        return [t for r in self.replays if (t := r.time_to_offer) is not None]

    @property
    def median_time_to_offer(self) -> float | None:
        t = self.times()
        return statistics.median(t) if t else None

    @property
    def false_offers_per_hour(self) -> float:
        calm = sum(r.duration for r in self.replays if not r.struggle)
        calm += sum(r.onset for r in self.replays if r.struggle)  # the minutes before it started
        bad = sum(len(r.bad) for r in self.replays)
        return bad / (calm / 3600) if calm else 0.0

    @property
    def backoff(self) -> tuple[int, int]:
        c = [r.conforms for r in self.replays if r.conforms is not None]
        return sum(c), len(c)

    @property
    def passes(self) -> bool:
        med = self.median_time_to_offer
        return (
            bool(self.replays)
            and self.precision >= PRECISION_GATE
            and self.recall >= RECALL_GATE
            and med is not None
            and med <= TIME_TO_OFFER_GATE
            and self.false_offers_per_hour <= FALSE_OFFERS_PER_HOUR_GATE
            and self.backoff[0] == self.backoff[1]
        )

    def by_kind(self) -> dict[str, tuple[int, int]]:
        """(right, total) per kind: right means offered if struggling, quiet if not."""
        out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in self.replays:
            right = bool(r.good) if r.struggle else not r.offers
            if r.conforms is not None:
                right = right and r.conforms
            out[r.kind][0] += right
            out[r.kind][1] += 1
        return {k: (v[0], v[1]) for k, v in sorted(out.items())}

    def text(self, verbose: bool = False) -> str:
        pct = lambda x: f"{100 * x:.0f}%"  # noqa: E731
        med = self.median_time_to_offer
        times = sorted(self.times())
        p90 = times[int(0.9 * (len(times) - 1))] if times else None
        ok, n = self.backoff
        struggle = sum(r.struggle for r in self.replays)
        lines = [
            f"scenarios: {len(self.replays)} ({struggle} struggle, {len(self.replays) - struggle} "
            f"not), sensitivity {self.sensitivity}, offers {self.offers}",
            f"precision: {pct(self.precision)} (gate {pct(PRECISION_GATE)})",
            f"recall: {pct(self.recall)} (gate {pct(RECALL_GATE)})",
            "time to offer: "
            + ("n/a" if med is None else f"median {med:.0f} s, p90 {p90:.0f} s")
            + f" (gate {TIME_TO_OFFER_GATE:.0f} s)",
            f"false offers per hour of calm: {self.false_offers_per_hour:.2f} "
            f"(gate {FALSE_OFFERS_PER_HOUR_GATE:.0f})",
            f"back-off scenarios as expected: {ok}/{n}",
            "by kind: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in self.by_kind().items()),
            f"by source: {self._by_source()}",
        ]
        if verbose:
            for r in self.replays:
                if r.struggle and not r.good:
                    lines.append(f"missed {r.id} ({r.kind}): no offer after onset {r.onset:.0f} s")
                for o in r.bad:
                    lines.append(f"false offer {r.id} ({r.kind}) at {o.t:.0f} s: {o.why}")
                if r.conforms is False:
                    lines.append(
                        f"back-off {r.id}: expected {r.expect_offers}, got {len(r.offers)}"
                    )
        lines.append("PASS" if self.passes else "FAIL")
        return "\n".join(lines)

    def _by_source(self) -> str:
        c: dict[str, int] = defaultdict(int)
        for r in self.replays:
            c[r.source] += 1
        return ", ".join(f"{k} {v}" for k, v in sorted(c.items()))


def _check(data: dict, path: Path) -> None:
    for key in ("id", "kind", "label", "app", "duration", "events"):
        if key not in data:
            raise EvalError(f"{path}: missing {key}")
    if data["label"] not in ("struggle", "not_struggle"):
        raise EvalError(f"{path}: label must be struggle or not_struggle")
    if data["label"] == "struggle" and "onset" not in data:
        raise EvalError(f"{path}: a struggle scenario needs an onset")
    for e in data["events"]:
        if e.get("kind") not in KINDS | EXTRA or not isinstance(e.get("t"), (int, float)):
            raise EvalError(f"{path}: bad event {e!r}")


def _expand(events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        if e["kind"] == "idle_span":
            out += [
                {"t": e["t"] + s, "kind": "idle", "value": s} for s in range(0, int(e["value"]) + 1)
            ]
        else:
            out.append(e)
    return sorted(out, key=lambda e: e["t"])


def replay(data: dict, sensitivity: int = 2) -> Replay:
    """One scenario through a fresh detector, one simulated second at a time."""
    now = [0.0]
    det = Detector(lambda: now[0], sensitivity=sensitivity)
    app = data["app"]
    det.opt_in(app)
    r = Replay(
        data["id"], data["kind"], data.get("source", "scripted"), data["label"],
        float(data.get("onset", 0.0)), float(data["duration"]), data.get("expect_offers"),
    )  # fmt: skip
    events = _expand(data["events"])
    i, pending, shown_at = 0, None, 0.0
    t = 0.0
    while t <= r.duration:
        now[0] = t
        while i < len(events) and events[i]["t"] <= t:
            e = events[i]
            i += 1
            if e["kind"] == "answer":
                if pending is not None:
                    det.answer(pending, e.get("key", "no"))
                    pending = None
                continue
            det.observe(
                Observation(
                    t, e.get("app", app), e["kind"], e.get("key", ""), int(e.get("value", 0))
                )
            )
        if pending is not None and t - shown_at >= FADE:
            det.answer(pending, "ignored")  # the bubble faded
            pending = None
        if pending is None:
            offer = det.poll()
            if offer is not None:
                pending, shown_at = offer, t
                r.offers.append(Offered(t, offer.app, offer.score, offer.why))
        t += 1.0
    return r


def load(directory: Path) -> list[dict]:
    files = sorted(Path(directory).glob("*.json"))
    if not files:
        raise EvalError(f"no scenarios in {directory}")
    out = []
    for path in files:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise EvalError(f"cannot read {path}: {e}") from e
        _check(data, path)
        out.append(data)
    return out


def run(directory: Path, sensitivity: int = 2) -> Report:
    return Report([replay(d, sensitivity) for d in load(directory)], sensitivity)
