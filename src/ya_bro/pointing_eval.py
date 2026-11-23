"""Pointing eval harness (ADR-0007, ADR-0016): score `grounding.point` on labelled snapshots.

evals/pointing/*.json, one per app and locale:
  {"app": ..., "locale": "en", "source": "synthetic" | "recorded",
   "elements": [{"id", "role", "name", "rect": [x, y, w, h]}],
   "cases": [{"id", "kind", "role", "name", "truth": "<element id>" | null}]}
`truth` null means the right answer is "not here": the bro must say nothing rather than point.
No LLM and no desktop: AT-SPI-tier pointing only, so every run is deterministic.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ya_bro import grounding
from ya_bro.grounding import Tier
from ya_bro.types import ElementRef, Rect

CORRECT_GATE = 0.80  # SPEC §8
CONFIDENTLY_WRONG_GATE = 0.02  # ADR-0007
CONFIDENTLY_WRONG_BLOCK = 0.05  # above this the release is blocked whatever the rest


class EvalError(ValueError):
    pass


class SnapshotPerception:
    """A recorded or built element list behind the Perception interface."""

    def __init__(self, app: str, elements: list[dict]) -> None:
        self._app = app
        self._rects = {e["id"]: Rect(*e["rect"]) for e in elements}
        self._refs = [ElementRef(app, e["role"], e["name"], e["id"]) for e in elements]

    async def find(
        self, app_id: str, role: str, name: str = "", text: str = ""
    ) -> list[ElementRef]:
        return [r for r in self._refs if app_id == self._app and r.role == role]

    async def locate(self, ref: ElementRef) -> Rect | None:
        return self._rects.get(ref.path)

    async def read_text(self, ref: ElementRef) -> str:
        return ""


@dataclass(frozen=True)
class Result:
    case: str
    app: str
    locale: str
    kind: str
    tier: Tier
    picked: str | None
    truth: str | None
    correct: bool
    ms: float

    @property
    def confidently_wrong(self) -> bool:
        return self.tier is Tier.HIGH and not self.correct


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    def _rate(self, n: int) -> float:
        return n / self.total if self.total else 0.0

    @property
    def correct_rate(self) -> float:
        return self._rate(sum(r.correct for r in self.results))

    @property
    def confidently_wrong_rate(self) -> float:
        return self._rate(sum(r.confidently_wrong for r in self.results))

    @property
    def medium_precision(self) -> float | None:
        medium = [r for r in self.results if r.tier is Tier.MEDIUM]
        return sum(r.correct for r in medium) / len(medium) if medium else None

    def latency_ms(self) -> dict[str, float]:
        by: dict[str, list[float]] = defaultdict(list)
        for r in self.results:
            by[r.tier.value].append(r.ms)
        return {t: sum(v) / len(v) for t, v in by.items()}

    def by(self, attr: str) -> dict[str, tuple[int, int]]:
        """(correct, total) per kind, app or locale."""
        out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in self.results:
            out[getattr(r, attr)][0] += r.correct
            out[getattr(r, attr)][1] += 1
        return {k: (v[0], v[1]) for k, v in sorted(out.items())}

    @property
    def passes(self) -> bool:
        return (
            self.total > 0
            and self.correct_rate >= CORRECT_GATE
            and self.confidently_wrong_rate <= CONFIDENTLY_WRONG_GATE
        )

    @property
    def blocks_release(self) -> bool:
        return self.confidently_wrong_rate > CONFIDENTLY_WRONG_BLOCK

    def text(self, verbose: bool = False) -> str:
        pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
        mp = self.medium_precision
        lines = [
            f"cases: {self.total}",
            f"pointed-correct: {pct(self.correct_rate)} (gate {pct(CORRECT_GATE)})",
            f"confidently-wrong: {pct(self.confidently_wrong_rate)} "
            f"(gate {pct(CONFIDENTLY_WRONG_GATE)}, "
            f"blocks release above {pct(CONFIDENTLY_WRONG_BLOCK)})",
            f"medium precision: {'n/a' if mp is None else pct(mp)}",
            "mean ms per tier: "
            + ", ".join(f"{t} {ms:.3f}" for t, ms in sorted(self.latency_ms().items())),
        ]
        for attr in ("kind", "locale", "app"):
            lines.append(
                f"by {attr}: " + ", ".join(f"{k} {c}/{n}" for k, (c, n) in self.by(attr).items())
            )
        if verbose:
            lines += [
                f"miss {r.app}/{r.locale}/{r.case} ({r.kind}): {r.tier.value}, "
                f"picked {r.picked}, truth {r.truth}"
                for r in self.results
                if not r.correct
            ]
        lines.append(
            "RELEASE BLOCKED" if self.blocks_release else ("PASS" if self.passes else "FAIL")
        )
        return "\n".join(lines)


def _check(data: dict, path: Path) -> None:
    ids = {e.get("id") for e in data.get("elements", [])}
    if not data.get("app") or not data.get("elements") or not data.get("cases"):
        raise EvalError(f"{path}: needs app, elements and cases")
    if len(ids) != len(data["elements"]):
        raise EvalError(f"{path}: element ids must be unique")
    for c in data["cases"]:
        if "role" not in c or "name" not in c or "truth" not in c:
            raise EvalError(f"{path}: case {c.get('id')!r} needs role, name and truth")
        if c["truth"] is not None and c["truth"] not in ids:
            raise EvalError(f"{path}: case {c['id']!r} truth is not an element")


async def _run_file(path: Path) -> list[Result]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise EvalError(f"cannot read {path}: {e}") from e
    _check(data, path)
    perception = SnapshotPerception(data["app"], data["elements"])
    out = []
    for c in data["cases"]:
        start = time.perf_counter()
        p = await grounding.point(perception, data["app"], c["role"], c["name"])
        ms = (time.perf_counter() - start) * 1000
        picked = p.ref.path if p.ref else None
        # Wrong target is wrong; no target is right only when nothing is there.
        correct = picked == c["truth"] if p.tier is not Tier.NONE else c["truth"] is None
        out.append(
            Result(
                c["id"], data["app"], data.get("locale", "en"), c.get("kind", ""),
                p.tier, picked, c["truth"], correct, ms,
            )
        )  # fmt: skip
    return out


def run(directory: Path, pattern: str = "*.json") -> Report:
    files = sorted(Path(directory).glob(pattern))
    if not files:
        raise EvalError(f"no snapshots matching {pattern} in {directory}")
    report = Report()
    for path in files:
        report.results += asyncio.run(_run_file(path))
    return report
