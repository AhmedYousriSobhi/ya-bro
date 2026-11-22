"""Policy for Show-me (ADR-0014): the bro only points, so any step may be shown; no Do-it yet."""

from __future__ import annotations

from ya_bro.types import Mode, PolicyDecision, Risk, Step


class ShowMePolicy:
    def check(self, step: Step, mode: Mode) -> PolicyDecision:
        if mode is not Mode.SHOW_ME:
            return PolicyDecision(False, reason="only Show-me is built")
        if step.risk is Risk.R3:
            return PolicyDecision(True, needs_confirmation=True, reason="the user's own click")
        return PolicyDecision(True)
