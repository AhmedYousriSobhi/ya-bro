"""The bash hook, in a real interactive bash on a pty (isolated runtime dir; no live session)."""

import os
import pty
import select
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest

from ya_bro.shell_spool import ShellSpool

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "shell" / "ya-bro.bash"
PROMPT = "YBP$ "
pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")


class Bash:
    """An interactive bash behind a pty. `run` types one line and returns what it printed."""

    def __init__(self, tmp: Path, runtime: Path, rc: str = "", hook: bool = True) -> None:
        self.tmp = tmp
        bindir = tmp / "bin"
        bindir.mkdir(exist_ok=True)
        fake = bindir / "fakectl"
        fake.write_text(
            '#!/bin/sh\n[ "$1" = nap ] && sleep 0.15\n[ "$1" = nap ] && exit 0\nexit "${1:-0}"\n'
        )
        fake.chmod(0o755)
        rcfile = tmp / "rc"
        rcfile.write_text(f"PS1='{PROMPT}'\n{rc}\n" + (f'. "{HOOK}"\n' if hook else ""))
        env = {
            "PATH": f"{bindir}:/usr/bin:/bin",
            "HOME": str(tmp),
            "XDG_RUNTIME_DIR": str(runtime),
            "TERM": "dumb",
        }
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(tmp)
            os.execve("/usr/bin/bash", ["bash", "--noprofile", "--rcfile", str(rcfile), "-i"], env)
        self.out = ""
        self.read_until_prompt()

    def read_until_prompt(self, timeout: float = 10.0) -> str:
        end = time.monotonic() + timeout
        buf = ""
        while not buf.endswith(PROMPT):
            if time.monotonic() > end:
                raise TimeoutError(f"no prompt; got {buf!r}")
            if select.select([self.fd], [], [], 0.1)[0]:
                try:
                    buf += os.read(self.fd, 4096).decode(errors="replace")
                except OSError:
                    break
        return buf

    def run(self, line: str) -> str:
        os.write(self.fd, (line + "\n").encode())
        return self.read_until_prompt()

    def close(self) -> None:
        try:
            os.write(self.fd, b"exit\n")
            os.waitpid(self.pid, 0)
        except OSError:
            pass
        os.close(self.fd)


@pytest.fixture
def runtime(tmp_path):
    d = tmp_path / "run"
    d.mkdir(mode=0o700)
    return d


@pytest.fixture
def spool(runtime):
    s = ShellSpool(runtime / "ya-bro")
    s.open(["fakectl"])
    yield s
    s.close()


def test_the_hook_script_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(HOOK)]).returncode == 0


def test_100_commands_record_exact_exit_codes_and_durations(tmp_path, runtime, spool):
    sh = Bash(tmp_path, runtime)
    try:
        for i in range(100):
            sh.run(f"fakectl {i % 7}")
        sh.run("fakectl nap")
    finally:
        sh.close()
    events = spool.poll()
    assert [e["exit"] for e in events[:100]] == [i % 7 for i in range(100)]
    assert all(e["argv0"] == "fakectl" and str(e["tty"]).startswith("pts/") for e in events)
    nap = events[100]
    assert 120 <= nap["ms"] < 1500 and nap["exit"] == 0
    assert len(events) == 101


def test_only_name_exit_and_duration_are_written_never_arguments(tmp_path, runtime, spool):
    sh = Bash(tmp_path, runtime)
    try:
        sh.run("fakectl 3 --token hunter2 --password swordfish")
        sh.run("export API_KEY=abc123secret")
    finally:
        sh.close()
    raw = spool.spool_path.read_text()
    assert "hunter2" not in raw and "swordfish" not in raw and "abc123secret" not in raw
    assert set(__import__("json").loads(raw.splitlines()[0])) == {
        "v",
        "ts",
        "argv0",
        "exit",
        "ms",
        "tty",
    }


def test_commands_that_are_not_allowed_are_never_written(tmp_path, runtime, spool):
    sh = Bash(tmp_path, runtime)
    try:
        for line in ("ls /", "echo hello", "false", "cd /tmp", "fakectl 2"):
            sh.run(line)
    finally:
        sh.close()
    assert [e["argv0"] for e in spool.poll()] == ["fakectl"]
    assert "ls" not in spool.spool_path.read_text()


def test_allowlist_changes_apply_to_the_next_command(tmp_path, runtime, spool):
    sh = Bash(tmp_path, runtime)
    seen = []
    try:
        sh.run("ls /")
        seen += spool.poll()
        spool.set_commands(["fakectl", "ls"])
        sh.run("ls /")
        seen += spool.poll()
        spool.set_commands([])
        sh.run("fakectl 1")
        seen += spool.poll()
    finally:
        sh.close()
    assert [e["argv0"] for e in seen] == ["ls"]  # only while it was allowed


def test_core_checks_the_allowlist_again_when_it_reads(tmp_path, runtime, spool):
    sh = Bash(tmp_path, runtime)
    try:
        sh.run("fakectl 1")
        spool.set_commands([])  # revoked before core got round to reading
    finally:
        sh.close()
    assert spool.poll() == []


def test_silent_and_spool_free_when_ya_bro_is_not_running(tmp_path, runtime):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    with_hook = Bash(tmp_path / "a", runtime)
    try:
        out_with = [with_hook.run(c) for c in ("fakectl 5", "echo hi", "false")]
    finally:
        with_hook.close()
    plain = Bash(tmp_path / "b", runtime, hook=False)
    try:
        out_plain = [plain.run(c) for c in ("fakectl 5", "echo hi", "false")]
    finally:
        plain.close()
    assert out_with == out_plain  # not one extra byte on the terminal
    assert list(runtime.iterdir()) == []  # and nothing was created


def test_a_spool_that_core_removed_stops_recording(tmp_path, runtime, spool):
    sh = Bash(tmp_path, runtime)
    try:
        sh.run("fakectl 1")
        spool.close()
        assert "ya-bro" not in os.listdir(runtime)
        out = sh.run("fakectl 2")
    finally:
        sh.close()
    assert out.count("\n") <= 2 and not (runtime / "ya-bro").exists()


def test_existing_prompt_command_and_debug_trap_still_work(tmp_path, runtime, spool):
    rc = "PROMPT_COMMAND='echo PC-RAN'\ntrap 'echo TRAP-RAN' DEBUG\n"
    sh = Bash(tmp_path, runtime, rc=rc)
    try:
        out = sh.run("fakectl 4")
    finally:
        sh.close()
    assert "PC-RAN" in out and "TRAP-RAN" in out
    assert [e["exit"] for e in spool.poll()] == [4]


def test_prompt_command_array_and_exit_status_survive(tmp_path, runtime, spool):
    rc = "PROMPT_COMMAND=('echo ARR-1' 'echo st=$?')\n"
    sh = Bash(tmp_path, runtime, rc=rc)
    try:
        out = sh.run("fakectl 9")
    finally:
        sh.close()
    assert "ARR-1" in out and "st=9" in out  # the user's own commands still see the real status
    assert [e["exit"] for e in spool.poll()] == [9]


def test_hook_does_nothing_in_a_non_interactive_shell(tmp_path, runtime, spool):
    r = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", f'. "{HOOK}"; echo "${{_YB_HOOK:-unset}}"'],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": str(runtime)},
    )
    assert r.stdout.strip() == "unset" and r.stderr == ""


def test_hook_adds_under_five_milliseconds_per_command(tmp_path, runtime, spool):
    def per_command(sh, n=200):
        sh.run(":")
        t0 = time.perf_counter()
        for _ in range(n):
            sh.run(":")  # a builtin: the whole cost is the shell and the hook
        return (time.perf_counter() - t0) / n * 1000

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = Bash(tmp_path / "a", runtime)
    b = Bash(tmp_path / "b", runtime, hook=False)
    try:
        # Interleave so machine noise hits both alike; compare the best of three.
        with_hook = min(per_command(a) for _ in range(3))
        without = min(per_command(b) for _ in range(3))
    finally:
        a.close()
        b.close()
    assert with_hook - without < 5.0, f"{with_hook:.2f} ms vs {without:.2f} ms"


def test_spool_files_are_private(runtime, spool):
    assert stat.S_IMODE(os.stat(runtime / "ya-bro").st_mode) == 0o700
    for name in ("shell.spool", "commands"):
        assert stat.S_IMODE(os.stat(runtime / "ya-bro" / name).st_mode) == 0o600
