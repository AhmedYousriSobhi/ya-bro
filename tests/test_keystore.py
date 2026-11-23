"""Where the API key lives (#5, ADR-0008 §9, ADR-0014 §4). A fake store here; the real one is
exercised in test_keyring_real.py against an isolated Secret Service."""

import io
import json
import subprocess
import sys

import pytest

from ya_bro import brain, dirs, keystore, privacy
from ya_bro.cli import main
from ya_bro.platform import keyring

KEY = "sk-ant-api03-SECRETSECRET0123456789"


class FakeStore:
    def __init__(self, value=None, down=False):
        self.value, self.down = value, down

    def _check(self):
        if self.down:
            raise keystore.KeyStoreError("no Secret Service available")

    def get(self):
        self._check()
        return self.value

    def set(self, value):
        self._check()
        self.value = value

    def clear(self):
        self._check()
        had, self.value = self.value is not None, None
        return had


@pytest.fixture
def store(monkeypatch):
    s = FakeStore()
    monkeypatch.setattr(keystore, "default_store", lambda: s)
    return s


# --- lookup order ----------------------------------------------------------------------------


def test_order_is_environment_then_keyring_then_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(f'ANTHROPIC_API_KEY="{KEY}-file"\n')
    s = FakeStore(f"{KEY}-ring")
    assert keystore.find({"ANTHROPIC_API_KEY": f" {KEY}-env "}, env_file, s).source == "environment"
    assert keystore.find({}, env_file, s) == keystore.Found(f"{KEY}-ring", "keyring")
    assert keystore.find({}, env_file, FakeStore()) == keystore.Found(f"{KEY}-file", ".env file")
    assert keystore.find({}, env_file, None).source == ".env file"  # no keyring asked
    assert keystore.find({}, tmp_path / "nope", FakeStore()) is None


def test_an_unreachable_keyring_falls_through_to_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(f"ANTHROPIC_API_KEY={KEY}\n")
    assert brain.load_key({}, env_file, FakeStore(down=True)) == KEY


def test_load_key_uses_the_keyring(tmp_path):
    assert brain.load_key({}, tmp_path / "x", FakeStore(KEY)) == KEY


# --- shape -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["", "   ", "short", "has a space in the middle of it 12345", "x" * 500]
)
def test_odd_shapes_are_refused_without_echoing_them(bad):
    with pytest.raises(keystore.KeyStoreError) as e:
        keystore.check_shape(bad)
    assert bad.strip() == "" or bad not in str(e.value)


def test_shape_is_loose_about_the_prefix():
    assert keystore.check_shape(f"  {KEY}\n") == KEY
    assert keystore.save("not-an-anthropic-key-0123456789", FakeStore()).startswith("note:")
    assert keystore.save(KEY, FakeStore()) == ""


# --- broctl key ------------------------------------------------------------------------------


def run_key(monkeypatch, capsys, verb, stdin=""):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))  # not a tty: one line is read
    code = main(["sent"] if verb == "sent" else ["key", verb])
    out, err = capsys.readouterr()
    return code, out + err


def test_set_status_clear_roundtrip(store, monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env
    assert run_key(monkeypatch, capsys, "status")[1].startswith("no API key")
    code, out = run_key(monkeypatch, capsys, "set", KEY + "\n")
    assert code == 0 and "stored" in out and store.value == KEY
    code, out = run_key(monkeypatch, capsys, "status")
    assert "present, used from the keyring" in out
    assert run_key(monkeypatch, capsys, "clear")[1].startswith("removed")
    assert store.value is None
    assert run_key(monkeypatch, capsys, "clear")[1].startswith("no key")


def test_set_prompts_hidden_on_a_terminal(store, monkeypatch, capsys):
    class Tty(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", Tty())
    monkeypatch.setattr("getpass.getpass", lambda prompt: KEY)
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("a visible prompt was used"))
    assert main(["key", "set"]) == 0 and store.value == KEY


def test_set_refuses_a_key_on_the_command_line(store, capsys):
    with pytest.raises(SystemExit):  # `broctl key set <key>` is not a thing
        main(["key", "set", KEY])
    assert store.value is None


def test_set_with_a_bad_key_stores_nothing(store, monkeypatch, capsys):
    code, out = run_key(monkeypatch, capsys, "set", "bad key here 1234567890123\n")
    assert code == 1 and store.value is None and "bad key" not in out


def test_set_with_no_keyring_says_so(monkeypatch, capsys):
    monkeypatch.setattr(keystore, "default_store", lambda: FakeStore(down=True))
    code, out = run_key(monkeypatch, capsys, "set", KEY)
    assert code == 1 and "no Secret Service" in out and KEY not in out


def test_status_names_where_it_comes_from_and_a_second_copy(store, monkeypatch, capsys, tmp_path):
    store.value = KEY
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f"ANTHROPIC_API_KEY={KEY}\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    out = run_key(monkeypatch, capsys, "status")[1]
    assert "used from the environment (also in: keyring, .env file)" in out and KEY not in out


def test_set_warns_when_the_environment_would_win(store, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    assert "takes precedence" in run_key(monkeypatch, capsys, "set", KEY)[1]


def test_status_says_when_the_keyring_is_unreachable(monkeypatch, capsys):
    monkeypatch.setattr(keystore, "default_store", lambda: FakeStore(down=True))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = run_key(monkeypatch, capsys, "status")[1]
    assert "keyring not reachable" in out and "no API key" in out


# --- doctor and forget -----------------------------------------------------------------------


def test_doctor_reports_presence_and_source_never_the_value(monkeypatch, capsys):
    from ya_bro import doctor
    from ya_bro.platform import linux_setup as ls

    env = {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "GNOME"}
    report, _ = doctor.doctor(env, lambda cmd: (1, ""), FakeStore(KEY))
    assert "api key: present (keyring)" in report and KEY not in report
    report, _ = doctor.doctor(env, lambda cmd: (1, ""), FakeStore())
    assert "api key: missing" in report and "broctl key set" in report
    assert ls.api_key({"ANTHROPIC_API_KEY": KEY}).detail == "present (environment)"


def test_forget_everything_lists_and_removes_the_stored_key(store, tmp_path, monkeypatch, capsys):
    # Private runtime dir and rc file: `--everything` also touches the shell spool and ~/.bashrc.
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("HOME", str(tmp_path))
    store.value = KEY
    monkeypatch.setattr("builtins.input", lambda _p: "")
    assert main(["forget", "--everything"]) == 1
    out = capsys.readouterr().out
    assert "API key stored in your keyring" in out and store.value == KEY  # said no
    monkeypatch.setattr("builtins.input", lambda _p: "y")
    assert main(["forget", "--everything"]) == 0 and store.value is None
    assert KEY not in capsys.readouterr().out


def test_plain_forget_leaves_the_key(store, monkeypatch):
    store.value = KEY
    monkeypatch.setattr("builtins.input", lambda _p: "y")
    main(["forget"])
    assert store.value == KEY


def test_forget_everything_copes_with_no_keyring(tmp_path):
    plan = privacy.forget_plan(
        everything=True, rc=tmp_path / "rc", store=lambda: FakeStore(down=True)
    )
    assert [act() for what, act in plan if "API key" in what] == [False]


# --- the key stays out of everything ---------------------------------------------------------


def test_the_real_backend_refuses_the_live_keyring_under_pytest():
    with pytest.raises(keystore.KeyStoreError, match="real keyring"):
        keyring.SecretServiceBackend().get()


def test_the_backend_passes_the_key_over_stdin_never_argv(monkeypatch):
    calls = []

    def fake_run(argv, **kw):
        calls.append((argv, kw))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    keyring.SecretServiceBackend(env={"PATH": "/usr/bin"}).set(KEY)
    argv, kw = calls[0]
    assert KEY not in " ".join(argv) and kw["input"] == KEY
    assert KEY not in json.dumps({k: v for k, v in kw["env"].items()})  # nor the environment


def test_backend_errors_do_not_carry_the_key(monkeypatch):
    def boom(argv, **kw):
        raise subprocess.TimeoutExpired(argv, 1, output=KEY.encode())

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(keyring.KeyringError) as e:
        keyring.SecretServiceBackend(env={}).set(KEY)
    assert KEY not in str(e.value) and KEY not in repr(e.value)
    assert e.value.__suppress_context__  # no chained exception with the call's arguments


def test_the_key_never_reaches_logs_ledger_output_or_errors(store, monkeypatch, capsys, tmp_path):
    """Set the key, use it for a brain call that fails with the key echoed back, then grep
    everything Bro wrote and printed."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    seen = run_key(monkeypatch, capsys, "set", KEY)[1]
    key = brain.load_key({}, None, store)
    assert key == KEY

    def echo_post(url, headers, body, timeout):
        raise brain._HttpError(400, f"bad header x-api-key: {headers['x-api-key']}")

    import asyncio

    privacy.save_consent(privacy.Consent(privacy.CONSENT_VERSION, True, False))
    b = brain.ClaudeBrain(key, post=echo_post)
    with pytest.raises(brain.BrainError) as e:
        asyncio.run(b.plan("multiply 7 by 6", "org.gnome.Calculator"))
    import traceback

    text = "".join(traceback.format_exception(e.value))
    seen += (
        text + run_key(monkeypatch, capsys, "status")[1] + run_key(monkeypatch, capsys, "sent")[1]
    )
    seen += brain.ClaudeBrain(key, post=echo_post).usage_line()
    for root in (dirs.state_dir(), dirs.config_dir(), dirs.cache_dir(), tmp_path):
        for f in root.rglob("*") if root.exists() else ():
            if f.is_file() and f.stat().st_size < 1_000_000:
                assert KEY.encode() not in f.read_bytes(), f"key found in {f}"
    assert KEY not in seen
