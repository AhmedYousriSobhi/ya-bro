"""Scripted plans as data (TOML), and a Brain that serves them until the Claude brain lands (#5).

[plan]
goal = "create a job"
app = "org.example.App"      # optional; broctl show --app overrides
extents_offset = [0, 0]      # optional pixel correction for an app whose AT-SPI extents are off
keywords = ["create", "job"]
[[step]]
narration = "Click Create."
target = {role = "button", name = "Create"}
expect = {role = "button", name = "Confirm"}          # appears by default; appears = false for gone
# or on text: expect = {role = "text", text = "42"}   (the element's text contains it)
why = "Creating starts the wizard."
risk = 0
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from ya_bro import shell_command
from ya_bro.types import ElementRef, Expect, Plan, Risk, Step

MAX_STEPS = 50


class PlanError(ValueError):
    pass


def _element(table: object, where: str) -> tuple[str, str]:
    if not isinstance(table, dict) or not isinstance(table.get("role"), str):
        raise PlanError(f"{where}: needs role and name")
    if not isinstance(table.get("name"), str) or not table["name"]:
        raise PlanError(f"{where}: needs role and name")
    return table["role"], table["name"]


def load(path: Path, app_id: str = "") -> tuple[Plan, str, list[str]]:
    """(plan, app id from the file, keywords). Raises PlanError on anything malformed."""
    try:
        data = tomllib.loads(Path(path).read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise PlanError(f"cannot read plan {path}: {e}") from e
    head = data.get("plan", {})
    goal = head.get("goal")
    if not isinstance(goal, str) or not goal:
        raise PlanError("plan.goal is required")
    app = app_id or head.get("app", "")
    raw = data.get("step", [])
    if not raw or len(raw) > MAX_STEPS:
        raise PlanError(f"a plan needs 1 to {MAX_STEPS} steps")
    steps = []
    for i, s in enumerate(raw, 1):
        where = f"step {i}"
        if not isinstance(s.get("narration"), str) or not s["narration"]:
            raise PlanError(f"{where}: narration is required")
        target = None
        if "target" in s:
            role, name = _element(s["target"], f"{where} target")
            target = ElementRef(app, role, name)
        expect = None
        if "expect" in s:
            e = s["expect"]
            if not isinstance(e, dict) or not isinstance(e.get("role"), str):
                raise PlanError(f"{where} expect: needs a role")
            name, text = e.get("name", ""), e.get("text", "")
            if not isinstance(name, str) or not isinstance(text, str) or not (name or text):
                raise PlanError(f"{where} expect: needs a name or a text")
            expect = Expect(e["role"], name, bool(e.get("appears", True)), text)
        command = s.get("command", "")
        if command and (not isinstance(command, str) or not shell_command.valid(command)):
            raise PlanError(
                f"{where}: command must be one printable line of at most 200 characters"
            )
        try:
            risk = Risk(int(s.get("risk", 0)))
        except ValueError as e:
            raise PlanError(f"{where}: risk must be 0 to 3") from e
        steps.append(
            Step(
                intent=str(s.get("intent", s["narration"][:40])),
                narration=s["narration"],
                target=target,
                expected=str(s.get("expected", "")),
                risk=risk,
                expect=expect,
                why=str(s.get("why", "")),
                command=command,
            )
        )
    keywords = [k.lower() for k in head.get("keywords", []) if isinstance(k, str)]
    offset = head.get("extents_offset", [0, 0])
    if not (
        isinstance(offset, list)
        and len(offset) == 2
        and all(isinstance(v, int) and abs(v) <= 100 for v in offset)
    ):
        raise PlanError("plan.extents_offset must be [dx, dy], whole pixels within 100")
    return Plan(goal=goal, steps=steps, extents_offset=(offset[0], offset[1])), app, keywords


class ScriptedBrain:
    """Brain over a directory of plan files: the plan whose keywords match the goal best."""

    def __init__(self, paths: list[Path]) -> None:
        self._paths = paths

    async def plan(self, goal: str, app_id: str) -> Plan:
        words = set(goal.lower().split())
        best: tuple[int, Plan] | None = None
        for path in self._paths:
            plan, _app, keywords = load(path, app_id)
            score = len(words & set(keywords))
            if score and (best is None or score > best[0]):
                best = (score, plan)
        if best is None:
            raise PlanError(f"no scripted plan matches {goal!r}")
        return best[1]


def rebind(plan: Plan, app_id: str) -> Plan:
    """Same plan with every target's app id set (a plan file may leave the app to the caller)."""
    from dataclasses import replace

    steps = [
        replace(s, target=replace(s.target, app_id=app_id)) if s.target else s for s in plan.steps
    ]
    return Plan(plan.goal, steps, plan.extents_offset)
