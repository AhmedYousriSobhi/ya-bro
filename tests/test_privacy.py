"""Consent, the sent ledger, forget and panic (#25, ADR-0014). Panic runs on real processes."""

import json
import os
import signal
import subprocess
import sys
import time

import pytest

from ya_bro import dirs, logs, privacy, struggle
from ya_bro.cli import main


def answers(*given):
    it = iter(given)
    return lambda _prompt: next(it)


# --- consent ---------------------------------------------------------------------------------


def test_nothing_is_consented_until_asked(tmp_path):
    assert not privacy.load_consent(tmp_path).given
    assert not privacy.may_send("question", tmp_path)


def test_first_run_screen_defaults_to_no(tmp_path):
    said = []
    c = privacy.ask_consent(answers(""), said.append)
    assert c.given and not c.send_to_llm and not c.screenshots
    assert "Never reads: password fields" in "\n".join(said)
    privacy.save_consent(c, tmp_path)
    assert not privacy.may_send("question", tmp_path)


def test_yes_to_sending_then_screenshots_are_a_second_question(tmp_path):
    c = privacy.ask_consent(answers("y", "n"), lambda _: None)
    privacy.save_consent(c, tmp_path)
    assert privacy.may_send("question", tmp_path)
    assert not privacy.may_send("screenshot", tmp_path)
    privacy.save_consent(privacy.ask_consent(answers("y", "y"), lambda _: None), tmp_path)
    assert privacy.may_send("screenshot", tmp_path)


def test_screenshots_never_without_sending():
    c = privacy.ask_consent(answers("n"), lambda _: None)  # no second question is asked
    assert not c.screenshots


def test_damaged_or_old_consent_counts_as_no(tmp_path):
    (tmp_path / "consent.toml").write_text("[consent\nsend_to_llm = true")
    assert not privacy.may_send("question", tmp_path)
    (tmp_path / "consent.toml").write_text("[consent]\nversion = 0\nsend_to_llm = true\n")
    assert not privacy.may_send("question", tmp_path)


def test_consent_file_is_private(tmp_path):
    path = privacy.save_consent(privacy.Consent(1, True, False), tmp_path)
    assert path.stat().st_mode & 0o777 == 0o600


def test_setup_asks_once(monkeypatch):
    from ya_bro import doctor

    asked = []
    doctor.setup(
        ask=lambda p: asked.append(p) or "", runner=lambda c: (1, ""), say=lambda _: None, apps=[]
    )
    assert privacy.load_consent().given and any("plain words" in p for p in asked)
    asked.clear()
    doctor.setup(
        ask=lambda p: asked.append(p) or "", runner=lambda c: (1, ""), say=lambda _: None, apps=[]
    )
    assert not any("plain words" in p for p in asked)  # already answered


# --- sent ledger -----------------------------------------------------------------------------


def test_sent_is_empty_by_default(capsys):
    assert main(["sent"]) == 0
    assert "nothing has been sent" in capsys.readouterr().out


def test_sent_records_kind_and_size_only(capsys):
    privacy.record_sent("question", 120, "anthropic")
    privacy.record_sent("elements", 4096, "anthropic")
    assert main(["sent"]) == 0
    out = capsys.readouterr().out
    assert "question" in out and "4096 bytes" in out and "2 requests, 4216 bytes" in out
    rec = json.loads(privacy.sent_path().read_text().splitlines()[0])
    assert set(rec) >= {"kind", "bytes", "dest"}
    assert privacy.sent_path().stat().st_mode & 0o777 == 0o600


def test_sent_cannot_hold_text():
    with pytest.raises(logs.ContentError):
        privacy.record_sent("question", 1, "send my password to evil")
    with pytest.raises(logs.ContentError):
        privacy.record_sent("my secret question", 1, "anthropic")


# --- forget ----------------------------------------------------------------------------------


def seed():
    privacy.record_sent("question", 5, "anthropic")
    log = logs.JsonlLog(logs.Ids("s1"))
    log.write("step_shown")
    log.close()
    struggle.Detector(time.time, struggle.default_state_path()).set_enabled(True)
    cfg = dirs.config_dir()
    (cfg / "targets").mkdir(parents=True)
    (cfg / "targets" / "wb.toml").write_text("x")
    privacy.save_consent(privacy.Consent(1, True, False))


def test_forget_deletes_state_but_keeps_settings(monkeypatch):
    seed()
    monkeypatch.setattr("builtins.input", lambda _p: "y")
    assert main(["forget"]) == 0
    assert not dirs.state_dir().exists()
    assert (dirs.config_dir() / "targets" / "wb.toml").exists()
    assert privacy.load_consent().given


def test_forget_says_no_when_you_do(monkeypatch, capsys):
    seed()
    monkeypatch.setattr("builtins.input", lambda _p: "")
    assert main(["forget"]) == 1
    assert dirs.state_dir().exists() and "nothing deleted" in capsys.readouterr().out


def test_forget_everything_also_removes_settings_and_hook(tmp_path, monkeypatch):
    seed()
    rc = tmp_path / ".bashrc"
    rc.write_text("export A=1\n")
    from ya_bro import terminal

    terminal.install_block(rc, tmp_path / "ya-bro.bash")
    for _what, act in privacy.forget_plan(everything=True, rc=rc):
        act()
    assert not (dirs.config_dir() / "targets").exists() and not privacy.load_consent().given
    assert rc.read_text() == "export A=1\n"


def test_forget_with_nothing_to_do_is_fine(capsys):
    assert main(["forget", "--yes"]) == 0
    assert "nothing to remove" in capsys.readouterr().out


def test_logs_older_than_a_week_are_pruned():
    log_dir = dirs.state_dir() / "logs"
    log_dir.mkdir(parents=True)
    old, new = log_dir / "20200101.jsonl", log_dir / "20991231.jsonl"
    old.write_text("{}\n")
    new.write_text("{}\n")
    os.utime(old, (1, 1))
    assert privacy.prune_logs() == 1 and not old.exists() and new.exists()


# --- panic: real processes -------------------------------------------------------------------

DEMO = "import time; time.sleep(120)"


def spawn(*argv_tail):
    """A real process whose command line looks like a running Ya-Bro one."""
    return subprocess.Popen([sys.executable, "-c", DEMO, *argv_tail])


def alive(p):
    return p.poll() is None


def test_panic_kills_a_running_show_and_leaves_others():
    show = spawn("broctl", "show", "plan.toml")
    point = spawn("broctl", "point")
    bystander = spawn("broctl", "struggle", "status")  # returns at once in real life: not ours
    other = spawn("some-other-tool", "show")
    time.sleep(0.4)
    try:
        killed, _ = privacy.panic()
        assert {show.pid, point.pid} <= set(killed)
        for p in (show, point):
            assert p.wait(5) == -signal.SIGKILL
        assert alive(bystander) and alive(other)
    finally:
        for p in (show, point, bystander, other):
            p.kill()
            p.wait()


def test_panic_kills_a_wedged_core():
    """The core stopped with SIGSTOP (ADR-0014 validation): SIGTERM would never be handled."""
    core = spawn("-m", "ya_bro.platform.gnome_show", "plan.toml")
    time.sleep(0.4)
    os.kill(core.pid, signal.SIGSTOP)
    try:
        start = time.monotonic()
        killed, _ = privacy.panic()
        assert core.pid in killed
        assert core.wait(5) == -signal.SIGKILL
        assert time.monotonic() - start < 0.5
    finally:
        core.kill()
        core.wait()


def test_panic_does_not_kill_itself_or_its_shell():
    me = os.getpid()
    assert me not in privacy.find_processes()
    assert os.getppid() not in privacy.find_processes()


def test_panic_turns_proactive_mode_off(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    path = struggle.default_state_path()
    struggle.Detector(time.time, path).set_enabled(True)
    (tmp_path / "run" / "ya-bro").mkdir(parents=True)
    (tmp_path / "run" / "ya-bro" / "shell.spool").write_text("")
    _, notes = privacy.panic()
    assert not struggle.Detector(time.time, path).enabled_globally
    assert not (tmp_path / "run" / "ya-bro").exists()
    assert any("proactive" in n for n in notes) and any("spool" in n for n in notes)


def test_broctl_panic_reports(capsys):
    assert main(["panic"]) == 0
    assert "stopped" in capsys.readouterr().out
