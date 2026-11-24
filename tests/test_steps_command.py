"""A step with a command (ADR-0029): snippet, Copy, Write it, and moving on when it has run."""

import asyncio

from tests.fakes import FakeCompositorBridge, FakeOverlay, FakePerception, FakePolicy
from ya_bro.command_watch import CommandWatch
from ya_bro.steps import Outcome, StepLoop, Timing
from ya_bro.terminal_write import WriteResult
from ya_bro.tone import Tone
from ya_bro.types import Plan, Rect, Step, WindowInfo

WIN = WindowInfo("1", "terminal", "t", Rect(0, 0, 800, 600), focused=True)
TIMING = Timing(poll=0.01, nudge=30.0)


class Spool:
    def __init__(self):
        self.pending = []

    def poll(self):
        out, self.pending = self.pending, []
        return out


class Writer:
    def __init__(self, ok=True, reason=""):
        self.ok, self.reason, self.written = ok, reason, []

    def can_write(self, command):
        return WriteResult(True)

    def write(self, command):
        self.written.append(command)
        return WriteResult(self.ok, self.reason)


def build(writer=None):
    overlay, spool = FakeOverlay(), Spool()
    loop = StepLoop(
        FakePerception(),
        overlay,
        FakeCompositorBridge([WIN]),
        FakePolicy(),
        TIMING,
        tone=Tone(0),
        writer=writer,
        commands=CommandWatch(spool),
    )
    step = Step(intent="x", narration="Run this.", command="./scripts/benchctl plan")
    return overlay, spool, loop, Plan("g", [step])


def texts(overlay):
    return [c[2] for c in overlay.calls if c[0] == "show_step"]


async def test_the_command_is_shown_as_a_snippet_with_copy_and_write():
    overlay, _spool, loop, plan = build(Writer())
    task = asyncio.create_task(loop.run(plan, "terminal"))
    await asyncio.sleep(0.1)
    assert overlay.snippets[0] == "./scripts/benchctl plan"
    assert overlay.buttons[0] == ("copy", "write", "next", "why", "stop")
    overlay.push("stop")
    assert await asyncio.wait_for(task, 2) is Outcome.STOPPED


async def test_without_a_writer_there_is_no_write_button():
    overlay, _spool, loop, plan = build(None)
    task = asyncio.create_task(loop.run(plan, "terminal"))
    await asyncio.sleep(0.1)
    assert overlay.buttons[0] == ("copy", "next", "why", "stop")
    task.cancel()


async def test_write_sends_exactly_the_command_and_says_so():
    writer = Writer()
    overlay, _spool, loop, plan = build(writer)
    task = asyncio.create_task(loop.run(plan, "terminal"))
    await asyncio.sleep(0.05)
    overlay.push("write")
    await asyncio.sleep(0.15)
    assert writer.written == ["./scripts/benchctl plan"]
    assert "press Enter" in texts(overlay)[-1]
    task.cancel()


async def test_a_refused_write_says_why_and_nothing_else_happens():
    writer = Writer(False, "there is already text at your prompt; clear it first")
    overlay, _spool, loop, plan = build(writer)
    task = asyncio.create_task(loop.run(plan, "terminal"))
    await asyncio.sleep(0.05)
    overlay.push("write")
    await asyncio.sleep(0.15)
    assert "already text" in texts(overlay)[-1] and not task.done()
    task.cancel()


async def test_the_step_moves_on_by_itself_when_the_command_ran_ok():
    overlay, spool, loop, plan = build(Writer())
    task = asyncio.create_task(loop.run(plan, "terminal"))
    await asyncio.sleep(0.05)
    spool.pending = [{"argv0": "benchctl", "exit": 0}]
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


async def test_a_failed_run_does_not_advance_and_a_rerun_does():
    overlay, spool, loop, plan = build(Writer())
    task = asyncio.create_task(loop.run(plan, "terminal"))
    await asyncio.sleep(0.05)
    spool.pending = [{"argv0": "benchctl", "exit": 2}]
    await asyncio.sleep(0.15)
    assert not task.done() and "error" in texts(overlay)[-1] or "code 2" in texts(overlay)[-1]
    spool.pending = [{"argv0": "benchctl", "exit": 0}]
    assert await asyncio.wait_for(task, 2) is Outcome.DONE


async def test_another_command_finishing_does_not_advance():
    overlay, spool, loop, plan = build(Writer())
    task = asyncio.create_task(loop.run(plan, "terminal"))
    await asyncio.sleep(0.05)
    spool.pending = [{"argv0": "ls", "exit": 0}]
    await asyncio.sleep(0.2)
    assert not task.done()
    task.cancel()
