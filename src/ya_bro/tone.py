"""What the bro says while it walks you through a plan: a thin face over the persona (ADR-0013).

Lines are templates over short facts (a step number, an expected value, what the screen shows),
never over free text read off the screen beyond a short, cut-down snippet. The words, the languages
and the humour rules live in `ya_bro.persona`; this class only shapes the facts and keeps the
step loop's calls the same.
"""

from __future__ import annotations

from ya_bro.persona import Persona
from ya_bro.redact import redact

SNIPPET = 24  # the most characters of screen text we echo back


def snippet(text: str) -> str:
    # Redact before cutting: a cut could leave half a secret that no pattern recognises.
    one = " ".join(redact(text).text.split())
    return one if len(one) <= SNIPPET else one[: SNIPPET - 1] + "…"


class Tone:
    def __init__(self, humour: int = 1, locale: str = "en", less_chatty: bool = False) -> None:
        self.persona = Persona(humour=humour, locale=locale, less_chatty=less_chatty)

    @property
    def humour(self) -> int:
        return self.persona.humour

    # ---- the task's state, kept by the step loop --------------------------------------------

    def begin_task(self) -> None:
        self.persona.begin_task()

    def note_progress(self) -> None:
        self.persona.note_progress()

    def set_sensitive(self, on: bool) -> None:
        """A risky or private step: no humour at all while it is on screen."""
        self.persona.sensitive = on

    def can_tease(self) -> bool:
        """The teasing face (and its lines) only when humour allows it right now."""
        return self.persona.effective_humour("mismatch") >= 1

    # ---- lines -----------------------------------------------------------------------------

    def cant_find(self, name: str) -> str:
        return self.persona.say("cant_find", name=name)

    def unsure(self, name: str) -> str:
        return self.persona.say("unsure", name=name)

    def not_yet(self) -> str:
        return self.persona.say("not_yet")

    def pre_done(self) -> str:
        return self.persona.say("pre_done")

    def done(self) -> str:
        return self.persona.say("task_done")

    def plan_preview(self, count: int, first: str) -> str:
        return self.persona.say("plan_preview", count=str(count), first=first[:90])

    def replanning(self) -> str:
        return self.persona.say("replanning")

    def still_here(self) -> str:
        return self.persona.say("still_here")

    def greeting(self) -> str:
        return self.persona.say("greeting")

    def step_done(self) -> str:
        return self.persona.say("step_done")

    def risky(self, name: str = "") -> str:
        """Before a step the user must take themselves (R3): never humorous."""
        return self.persona.say("risk_confirm", name=snippet(name))

    def act_confirm(self, name: str = "") -> str:
        """Before pressing an R2 control for the user (Do-it): asks, never jokes."""
        return self.persona.say("act_confirm", name=snippet(name))

    def act_failed(self) -> str:
        return self.persona.say("act_failed")

    def mismatch(self, want: str, got: str) -> str:
        self.persona.note_mismatch()
        return self.persona.say("mismatch", want=snippet(want), got=snippet(got))

    def why_mismatch(self, want: str, got: str, why: str) -> str:
        return self.persona.say("why_mismatch", want=snippet(want), got=snippet(got), why=why)

    # ---- the struggle offer (ADR-0010 §4) ----------------------------------------------------

    def offer(self, app: str) -> str:
        return self.persona.say("offer_stuck", app=app)

    def declined(self) -> str:
        return self.persona.say("offer_declined")

    def back_off(self) -> str:
        return self.persona.say("back_off_long")

    def recovered(self) -> str:
        return self.persona.say("error_recovered")
