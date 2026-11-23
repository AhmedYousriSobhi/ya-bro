"""What the bro says (SPEC persona, #23): plain at humour 0, playful from 1 up.

Lines are templates over short facts (a step number, an expected value, what the screen shows),
never over free text read off the screen beyond a short, cut-down snippet.
"""

from __future__ import annotations

from ya_bro.redact import redact

SNIPPET = 24  # the most characters of screen text we echo back


def snippet(text: str) -> str:
    # Redact before cutting: a cut could leave half a secret that no pattern recognises.
    one = " ".join(redact(text).text.split())
    return one if len(one) <= SNIPPET else one[: SNIPPET - 1] + "…"


class Tone:
    def __init__(self, humour: int = 1) -> None:
        self.humour = max(0, min(3, humour))
        self._mismatches = 0

    def cant_find(self, name: str) -> str:
        if not self.humour:
            return f"I can't find “{name}” here yet. Open the right screen and I'll point at it."
        return f"Where's “{name}” hiding, bro? Open the right screen and I'll point at it."

    def not_yet(self) -> str:
        if not self.humour:
            return "I don't see that yet. Do it and I'll move on. Next again skips."
        return "Nice try, bro, but I don't see it yet. Do it and I'll move on. Next again skips."

    def pre_done(self) -> str:
        if not self.humour:
            return "This already looks done. Press Next to continue."
        return "Already done? Show-off. Press Next to continue."

    def still_here(self) -> str:
        if not self.humour:
            return "Still here. Press Next when you've done it."
        return "Still here, bro. Take your time. Press Next when you've done it."

    def mismatch(self, want: str, got: str) -> str:
        want, got = snippet(want), snippet(got)
        self._mismatches += 1
        if not self.humour:
            return (
                f"That's not what I asked for. I expected “{want}” on screen. "
                "Undo it, or press Next to go on."
            )
        shown = f" and you gave me “{got}”" if got else ""
        lines = [
            f"See?! That's not it, bro. I warned you. I wanted “{want}”{shown}. "
            "Undo it, or press Next to go on.",
            f"Bro... I said “{want}”{shown}. Undo it, or press Next if you're feeling lucky.",
            f"Ha! Wrong one. I wanted “{want}”{shown}. Undo it, then try again.",
        ]
        return lines[(self._mismatches - 1) % len(lines)]

    def why_mismatch(self, want: str, got: str, why: str) -> str:
        want, got = snippet(want), snippet(got)
        seen = f"The screen shows “{got}”" if got else "The screen shows something else"
        head = f"{seen}, but this step needs “{want}”."
        tail = f" {why}" if why else ""
        fix = " Undo it (C or Undo), then press the key I'm pointing at."
        if self.humour:
            head = f"{seen}, bro, but I need “{want}”. That's the mistake."
        return head + tail + fix
