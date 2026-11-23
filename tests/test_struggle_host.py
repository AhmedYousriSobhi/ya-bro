import asyncio
import contextlib

import pytest

from tests.fakes import FakeIdleSource, FakeShellHook
from ya_bro import cli, packs, struggle, struggle_host
from ya_bro.platform.gnome_idle import parse_idle
from ya_bro.struggle import Detector, Signal
from ya_bro.targets import Target

CMDS = {"benchctl": "workbench"}


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


def events(*codes, argv0="benchctl"):
    return [{"argv0": argv0, "exit": c, "ms": 5, "ts": 0, "tty": "pts/1"} for c in codes]


async def run_host(host, seconds=0.3):
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(host.run(), seconds)


@pytest.fixture
def det():
    clock = Clock()
    d = Detector(clock)
    d.opt_in("workbench")
    return d, clock


async def test_three_failing_commands_from_the_shell_hook_make_an_offer(det):
    d, clock = det
    offers, log = [], []
    host = struggle_host.StruggleHost(
        d, CMDS, shell=FakeShellHook(events(1, 1, 1)), on_offer=offers.append,
        sink=lambda name, **f: log.append((name, f)), clock=clock,
    )  # fmt: skip
    await run_host(host)
    assert len(offers) == 1 and offers[0].app == "workbench"
    assert ("struggle_signal", {"signal": "failing_commands"}) in log
    assert all(set(f) <= {"signal", "app", "score"} for _n, f in log)  # counts and names only


async def test_commands_nobody_allowed_are_not_even_counted(det):
    d, clock = det
    offers = []
    host = struggle_host.StruggleHost(
        d,
        CMDS,
        shell=FakeShellHook(events(1, 1, 1, argv0="rm")),
        on_offer=offers.append,
        clock=clock,
    )
    await run_host(host)
    assert offers == [] and d.score("workbench") == 0.0


async def test_a_command_of_an_app_that_is_not_opted_in_is_ignored():
    clock = Clock()
    d = Detector(clock)  # nothing opted in
    offers = []
    host = struggle_host.StruggleHost(
        d, CMDS, shell=FakeShellHook(events(1, 1, 1)), on_offer=offers.append, clock=clock
    )
    await run_host(host)
    assert offers == []


async def test_idle_with_something_unfinished_is_a_pause_in_the_focused_app(det):
    d, clock = det
    d.set_sensitivity(4)
    log = []

    async def focused():
        return "workbench"

    class Late(FakeShellHook):
        pass

    host = struggle_host.StruggleHost(
        d, CMDS, shell=Late(events(1)), idle=FakeIdleSource(30), focused_app=focused,
        sink=lambda name, **f: log.append(name), clock=clock,
    )  # fmt: skip
    await run_host(host, 1.5)
    assert "struggle_signal" in log


async def test_idle_is_not_read_without_a_focused_opted_in_app(det):
    d, clock = det

    async def nobody():
        return None

    log = []
    host = struggle_host.StruggleHost(
        d, CMDS, idle=FakeIdleSource(999), focused_app=nobody, sink=lambda n, **f: log.append(n)
    )
    await run_host(host, 0.3)
    assert log == []


def test_command_apps_and_pack_tuning():
    targets = [
        Target("workbench", commands=("benchctl", "wb")),
        Target("web", origins=("http://x",)),
    ]
    assert struggle_host.command_apps(targets) == {"benchctl": "workbench", "wb": "workbench"}
    found, problems = packs.load_all([packs.SHIPPED])
    assert problems == []
    d = Detector(Clock())
    struggle_host.apply_packs(
        d, found, {"workbench": {"argv0": "benchctl"}, "gimp": {"app_id": "x"}}
    )
    assert d._rules["workbench"][Signal.APP_ERROR_CODE].count == 2
    assert "gimp" not in d._rules


def test_pack_signals_are_bounded_at_load(tmp_path):
    root = tmp_path / "demo"
    root.mkdir()
    base = '[pack]\nid="demo"\nname="D"\nversion="1.0.0"\n[match]\nargv0=["x"]\n'
    (root / "pack.toml").write_text(base)
    ok = "[weights]\nfailing_commands = 2\n[counts.undo_loop]\ncount = 5\nwindow = 40\n"
    (root / "signals.toml").write_text(ok)
    p = packs.load(root)
    assert p.signal_weights == {"failing_commands": 2.0} and p.signal_counts == {
        "undo_loop": (5, 40.0)
    }
    for bad in (
        "[weights]\nfailing_commands = 9\n",
        "[weights]\nnonsense = 1\n",
        "[weights]\nundo_loop = true\n",
        "[counts.undo_loop]\ncount = 1\nwindow = 5\n",
        "[counts.undo_loop]\ncount = 3\n",
        "[weights\n",
    ):
        (root / "signals.toml").write_text(bad)
        with pytest.raises(packs.PackError, match="signals.toml"):
            packs.load(root)


def test_idle_reply_parsing():
    assert parse_idle("(uint64 4521,)\n") == 4.521
    assert parse_idle("") is None and parse_idle("(uint64 x,)") is None


def test_broctl_struggle_controls(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert cli.main(["struggle", "status"]) == 0
    assert "watching: nothing" in capsys.readouterr().out
    assert cli.main(["struggle", "enable", "workbench"]) == 0
    assert cli.main(["struggle", "sensitivity", "4"]) == 0
    assert cli.main(["struggle", "sensitivity", "9"]) == 1
    assert cli.main(["struggle", "enable", "not an app!"]) == 1
    capsys.readouterr()
    assert cli.main(["struggle", "status"]) == 0
    out = capsys.readouterr().out
    assert "watching: workbench" in out and "sensitivity: 4 of 4" in out
    assert cli.main(["struggle", "off"]) == 0
    assert (
        cli.main(["struggle", "status"]) == 0 and "proactive mode: off" in capsys.readouterr().out
    )
    assert cli.main(["struggle", "disable", "workbench"]) == 0
    assert (
        struggle.Detector(Clock(), struggle.default_state_path()).is_watching("workbench") is False
    )


def test_broctl_struggle_watch_needs_something_to_watch(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert cli.main(["struggle", "watch", "--seconds", "1"]) == 1
    assert "watching nothing" in capsys.readouterr().out
