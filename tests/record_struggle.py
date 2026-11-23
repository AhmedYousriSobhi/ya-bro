"""Record struggle scenarios from a REAL interactive bash with the hook (#24).

Each scenario types real commands into a real bash on a pty; the hook writes the real spool; the
events are read back as the detector sees them and saved as evals/struggle/recorded-<id>.json.
The timings are real but short (seconds, not minutes); the label is what the script was meant to
be. Run:  uv run python -m tests.record_struggle [out_dir]   (default: evals/struggle)
"""

import json
import sys
import tempfile
import time
from pathlib import Path

from tests.test_shell_hook import Bash
from ya_bro.shell_spool import ShellSpool

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ["fakectl", "make", "git"]

F, OK = ("fakectl 1", 1), ("fakectl 0", 1)
LAST = lambda cmd: (cmd, 0)  # noqa: E731  (the last command needs no pause after it)

# id, kind, label, [(command line, real pause after it in seconds)]
SCRIPTS = [
    ("fail-three", "failing_commands", "struggle", [F, F, LAST("fakectl 2")]),
    ("fail-four", "failing_commands", "struggle", [F, F, F, LAST("fakectl 3")]),
    ("fail-three-with-noise", "failing_commands", "struggle",
     [F, ("ls /", 1), F, ("echo hi", 1), LAST("fakectl 1")]),
    ("fail-then-fixed", "failing_commands", "not_struggle", [F, F, LAST("fakectl 0")]),
    ("fail-ok-fail-ok", "failing_commands", "not_struggle",
     [F, OK, F, OK, F, LAST("fakectl 0")]),
    ("different-commands", "failing_commands", "not_struggle",
     [F, ("make 1", 1), LAST("git 1")]),
    ("all-green", "failing_commands", "not_struggle", [OK] * 5 + [LAST("fakectl 0")]),
    ("single-failure", "failing_commands", "not_struggle", [F, LAST("ls /")]),
]  # fmt: skip


def record_one(work: Path, sid: str, kind: str, label: str, steps: list) -> dict:
    runtime = work / f"run-{sid}"
    runtime.mkdir(mode=0o700)
    spool = ShellSpool(runtime / "ya-bro")
    spool.open(COMMANDS)
    shell_dir = work / f"sh-{sid}"
    shell_dir.mkdir()
    sh = Bash(shell_dir, runtime)
    for name in ("make", "git"):  # stand-ins that exit with their first argument
        stub = shell_dir / "bin" / name
        stub.write_text('#!/bin/sh\nexit "${1:-0}"\n')
        stub.chmod(0o755)
    events = []
    try:
        for line, pause in steps:
            sh.run(line)
            events += spool.poll()
            time.sleep(pause)
    finally:
        sh.close()
        spool.close()
    t0 = events[0]["ts"] if events else 0
    out = [
        {"t": round((e["ts"] - t0) / 1000, 1), "kind": "command_exit",
         "key": e["argv0"], "value": e["exit"]}
        for e in events
    ]  # fmt: skip
    data = {
        "id": sid, "kind": kind, "source": "recorded", "label": label, "app": "workbench",
        "duration": round(out[-1]["t"] + 30, 1) if out else 30, "events": out,
    }  # fmt: skip
    if label == "struggle":
        data["onset"] = out[0]["t"] if out else 0
    return data


def record(out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    with tempfile.TemporaryDirectory(prefix="yb-rec-") as tmp:
        for sid, kind, label, steps in SCRIPTS:
            data = record_one(Path(tmp), sid, kind, label, steps)
            (out_dir / f"recorded-{sid}.json").write_text(json.dumps(data, indent=1) + "\n")
            done.append(data)
    return done


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "evals" / "struggle"
    for d in record(target):
        print(f"{d['id']}: {len(d['events'])} events over {d['duration'] - 30:.0f} s")
