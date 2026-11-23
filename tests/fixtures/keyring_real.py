"""Runs inside the private session of test_keyring_real.py: a real Secret Service, a private bus,
a private HOME. Prints PASS/FAIL lines. Never touches anything outside that session."""

import io
import os
import sys
from pathlib import Path

from ya_bro import brain
from ya_bro.cli import main
from ya_bro.platform import keyring

KEY = "sk-ant-api03-REALKEYRINGTEST0123456789"
results = []


def check(name, ok):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name, flush=True)


def cli(*argv, stdin=""):
    sys.stdin = io.StringIO(stdin)
    out = io.StringIO()
    real, sys.stdout = sys.stdout, out
    try:
        code = main(list(argv))
    finally:
        sys.stdout = real
    return code, out.getvalue()


assert "PYTEST_CURRENT_TEST" not in os.environ
assert os.environ["HOME"] == os.environ["XDG_DATA_HOME"].rsplit("/", 1)[0], "not the private home"
store = keyring.SecretServiceBackend()
check("service reachable", store.available())
check("nothing stored at first", store.get() is None)
check("clear with nothing is False", store.clear() is False)

code, out = cli("key", "set", stdin=KEY + "\n")
check("broctl key set stores it", code == 0 and "stored" in out and KEY not in out)
check("get returns exactly the key", store.get() == KEY)
code, out = cli("key", "status")
check("status says keyring, no value", "used from the keyring" in out and KEY not in out)
check("load_key finds it with no env", brain.load_key({}, None, store) == KEY)
check(
    "environment wins over keyring",
    brain.load_key({"ANTHROPIC_API_KEY": "sk-env-" + "x" * 20}, None, store).startswith("sk-env-"),
)

keyrings = Path(os.environ["XDG_DATA_HOME"]) / "keyrings"
blobs = [f.read_bytes() for f in keyrings.glob("*") if f.is_file()]
check(
    "keyring file exists and is not plaintext", blobs and all(KEY.encode() not in b for b in blobs)
)

from ya_bro import privacy  # noqa: E402

plan = privacy.forget_plan(everything=True, rc=Path(os.environ["HOME"]) / ".bashrc")
(act,) = [a for what, a in plan if "API key" in what]
check("forget --everything removes it", act() is True and store.get() is None)
cli("key", "set", stdin=KEY)
code, out = cli("key", "clear")
check("broctl key clear removes it", code == 0 and store.get() is None and "removed" in out)
code, out = cli("key", "clear")
check("clear again says none", "no key" in out)
check(
    "bad key is refused, nothing stored",
    cli("key", "set", stdin="no way\n")[0] == 1 and store.get() is None,
)
check(
    "no stray copy of the key in the private state",
    all(
        KEY.encode() not in f.read_bytes()
        for root in (
            os.environ["XDG_STATE_HOME"],
            os.environ["XDG_CONFIG_HOME"],
            os.environ["XDG_CACHE_HOME"],
        )
        for f in Path(root).rglob("*")
        if f.is_file()
    ),
)
sys.exit(0 if all(results) else 1)
