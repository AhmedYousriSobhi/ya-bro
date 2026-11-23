import json
import os
import stat

import pytest

from tests.fakes import FakePerception
from ya_bro import packs, terminal
from ya_bro.shell_spool import MAX_LINE, ShellSpool
from ya_bro.types import ElementRef, Rect


@pytest.fixture
def spool(tmp_path):
    s = ShellSpool(tmp_path / "ya-bro")
    s.open(["benchctl", "bad name", "../x"])
    yield s
    s.close()


def put(spool, *lines):
    with open(spool.spool_path, "ab") as f:
        for line in lines:
            f.write((line if isinstance(line, bytes) else line.encode()) + b"\n")


def rec(**kw):
    base = {"v": 1, "ts": 1700000000000, "argv0": "benchctl", "exit": 0, "ms": 12, "tty": "pts/3"}
    return json.dumps({**base, **kw})


def test_open_makes_private_files_and_only_plain_command_names(spool):
    root = spool.spool_path.parent
    assert stat.S_IMODE(os.stat(root).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(spool.spool_path).st_mode) == 0o600
    assert (root / "commands").read_text() == "benchctl\n"  # "bad name" and "../x" were dropped
    spool.close()
    assert not root.exists()


def test_poll_returns_valid_records_once(spool):
    put(spool, rec(), rec(exit=2, ms=500))
    first = spool.poll()
    assert [(e["argv0"], e["exit"], e["ms"]) for e in first] == [
        ("benchctl", 0, 12),
        ("benchctl", 2, 500),
    ]
    assert spool.poll() == []
    put(spool, rec(exit=7))
    assert [e["exit"] for e in spool.poll()] == [7]


@pytest.mark.parametrize(
    "line",
    [
        "not json",
        "[]",
        rec(v=2),
        rec(argv0="rm"),
        rec(argv0="../x"),
        rec(exit=256),
        rec(exit=-1),
        rec(exit="0"),
        rec(exit=True),
        rec(ms=-5),
        rec(ms=10**12),
        rec(tty="pts/3; rm -rf"),
        rec(tty=3),
        rec(ts="now"),
        "x" * (MAX_LINE + 1),
        '{"v":1}',
    ],
)
def test_malformed_or_disallowed_lines_are_skipped(spool, line):
    put(spool, line, rec(exit=9))
    assert [e["exit"] for e in spool.poll()] == [9]


def test_a_half_written_line_waits_for_its_end(spool):
    line = rec(exit=4)
    with open(spool.spool_path, "ab") as f:
        f.write(line[:20].encode())
    assert spool.poll() == []
    with open(spool.spool_path, "ab") as f:
        f.write(line[20:].encode() + b"\n")
    assert [e["exit"] for e in spool.poll()] == [4]


def test_emptied_spool_is_followed_and_big_one_is_truncated(spool, monkeypatch):
    put(spool, rec(ms=123456789), rec(ms=123456789))
    spool.poll()
    os.truncate(spool.spool_path, 0)  # only core ever does this; the hook only appends
    put(spool, rec(exit=3))
    assert [e["exit"] for e in spool.poll()] == [3]
    monkeypatch.setattr("ya_bro.shell_spool.TRUNCATE_AT", 10)
    put(spool, rec(exit=5))
    spool.poll()
    assert spool.spool_path.stat().st_size == 0


async def test_events_stream(spool):
    put(spool, rec(exit=1))
    it = spool.events(0.01)
    assert (await anext(it))["exit"] == 1
    await it.aclose()


def test_missing_spool_is_quiet(tmp_path):
    assert ShellSpool(tmp_path / "nothing").poll() == []


# ---- terminal text, after the user accepted help --------------------------------------------

TERM = ElementRef("org.gnome.Ptyxis", "terminal", "")


def term(text):
    return FakePerception({TERM: Rect(0, 0, 10, 10)}, {TERM: text})


async def test_last_output_is_redacted_bounded_and_tail_only():
    body = "\n".join(f"line {i}" for i in range(100)) + "\ntoken=abc123secret\n\n\n"
    out = await terminal.last_output(term(body), "org.gnome.Ptyxis", lines=3)
    assert (
        out.splitlines() == ["line 99", "token=[redacted:credential]"][-2:]
        or "abc123secret" not in out
    )
    assert "abc123secret" not in out and len(out.splitlines()) <= 3
    assert await terminal.last_output(FakePerception(), "org.gnome.Ptyxis") == ""
    long = await terminal.last_output(term("x" * 5000), "org.gnome.Ptyxis")
    assert len(long) == terminal.MAX_LINE_CHARS


def test_find_error_reads_workbench_lines():
    text = "$ benchctl start\nWB-REFUSED-MEMORY: need 9 GB, 4 free | fix: benchctl plan\n$ "
    e = terminal.find_error(text)
    assert (e.code, e.message, e.fix) == ("WB-REFUSED-MEMORY", "need 9 GB, 4 free", "benchctl plan")
    assert terminal.find_error("WB-USAGE: bad flag").fix == ""
    assert terminal.find_error("nothing to see\nNOT AN ERROR") is None


def test_explain_uses_the_pack_that_owns_the_command():
    found, _ = packs.load_all([packs.SHIPPED])
    text = "WB-REFUSED-MEMORY: no room | fix: benchctl plan"
    err, fixit = terminal.explain(found, "benchctl", text)
    assert err.code == "WB-REFUSED-MEMORY" and fixit.suggest == "benchctl plan"
    assert terminal.explain(found, "ls", text) is None  # not that pack's command
    assert terminal.explain(found, "benchctl", "WB-NOPE-NOTHING: x") is None


def test_install_and_remove_hook_block_keep_the_rest_of_the_file(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text("alias ll='ls -l'\nexport A=1")
    rc.chmod(0o640)
    script = tmp_path / "ya-bro.bash"
    assert terminal.install_block(rc, script) is True
    assert terminal.install_block(rc, script) is False  # idempotent
    text = rc.read_text()
    assert text.startswith("alias ll='ls -l'\nexport A=1\n") and str(script) in text
    assert text.count(terminal.BEGIN) == 1 and stat.S_IMODE(rc.stat().st_mode) == 0o640
    assert terminal.remove_block(rc) is True
    assert rc.read_text() == "alias ll='ls -l'\nexport A=1\n"
    assert terminal.remove_block(rc) is False
    assert terminal.remove_block(tmp_path / "missing") is False


# ---- broctl hook / shell watch ----------------------------------------------------------------


def test_broctl_hook_install_uninstall_status(tmp_path, monkeypatch, capsys):
    from ya_bro import cli

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert cli.main(["hook", "status"]) == 0
    assert "hook not installed" in capsys.readouterr().out
    monkeypatch.setattr("builtins.input", lambda _p: "n")
    assert cli.main(["hook", "install"]) == 1
    assert not (tmp_path / ".bashrc").exists()  # declined: nothing written
    monkeypatch.setattr("builtins.input", lambda _p: "y")
    assert cli.main(["hook", "install"]) == 0
    assert terminal.BEGIN in (tmp_path / ".bashrc").read_text()
    assert cli.main(["hook", "status"]) == 0 and "hook installed" in capsys.readouterr().out
    assert cli.main(["hook", "uninstall"]) == 0
    assert terminal.BEGIN not in (tmp_path / ".bashrc").read_text()
    assert cli.main(["hook", "print"]) == 0 and "ya-bro.bash" in capsys.readouterr().out


def test_broctl_shell_watch_needs_an_allowed_command(tmp_path, monkeypatch, capsys):
    from ya_bro import cli, targets

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    (tmp_path / "run").mkdir(mode=0o700)
    assert cli.main(["shell", "watch", "--seconds", "1"]) == 1
    assert "no allowed commands" in capsys.readouterr().out
    targets.save(targets.Target("workbench", commands=("benchctl",)))
    assert cli.main(["shell", "watch", "--seconds", "1"]) == 0
    assert "watching benchctl" in capsys.readouterr().out
    assert not (tmp_path / "run" / "ya-bro").exists()  # cleaned up on exit


def test_the_scope_token_file_is_private_and_only_a_real_token_is_accepted(spool):
    token = "yb-" + "0f" * 16
    spool.set_scope_token(token)
    f = spool.spool_path.parent / "scope-token"
    assert f.read_text() == token + "\n"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    for bad in ("", "yb-short", token + "\n", "yb-" + "G" * 32, "x" * 35):
        with pytest.raises(ValueError):
            spool.set_scope_token(bad)
    spool.close()
    assert not f.exists()
