import ast

from ya_bro import doctor
from ya_bro.cli import main
from ya_bro.platform import linux_setup as ls

GNOME = {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}


def fake(answers):
    calls = []

    def runner(cmd):
        calls.append(cmd)
        for key, val in answers.items():
            if key in " ".join(cmd):
                return val
        return 1, ""

    runner.calls = calls
    return runner


HEALTHY = {
    "get org.gnome.desktop.interface": (0, "true"),
    "org.a11y.Status": (0, "(<true>,)"),
    "GetExtensionInfo": (0, "({'uuid': <'x'>, 'state': <1.0>},)"),
    "allowed-apps": (0, "['org.gimp.GIMP']"),
}


def test_healthy_report():
    report, code = doctor.doctor({**GNOME, "ANTHROPIC_API_KEY": "sk-secret"}, fake(HEALTHY))
    assert code == 0 and "WARN" not in report and "FAIL" not in report
    assert "sk-secret" not in report


def test_problems_have_fixes():
    report, code = doctor.doctor({"XDG_SESSION_TYPE": "x11"}, fake({}))
    assert code == 1
    assert "FAIL" in report and "fix:" in report and "missing" in report


def test_extension_error_state():
    c = ls.extension_state(fake({"GetExtensionInfo": (0, "({'state': <3.0>},)")}))
    assert c.status == "warn" and c.detail == "ERROR"


def test_setup_requires_explicit_yes(tmp_path):
    runner = fake({})
    out = []
    doctor.setup(ask=lambda _: "", runner=runner, say=out.append)
    assert runner.calls == []
    assert sum(x.startswith("skipped") for x in out) == 2


def test_setup_enables_a11y_on_yes():
    runner = fake({"set org.gnome.desktop.interface": (0, "")})
    answers = iter(["", "y", "n"])
    doctor.setup(ask=lambda _: next(answers), runner=runner, say=lambda _: None)
    assert ["gsettings", "set", ls.SCHEMA_IFACE, "toolkit-accessibility", "true"] in runner.calls


def test_install_extension_copies_and_enables(tmp_path):
    src = tmp_path / "src"
    (src / "schemas").mkdir(parents=True)
    (src / "metadata.json").write_text("{}")
    target = tmp_path / "dest"
    runner = fake({"get org.gnome.shell": (0, "['a@b']")})
    msg = ls.install_extension(runner, src, target)
    assert (target / "metadata.json").is_file() and "log out" in msg
    set_call = [c for c in runner.calls if c[:2] == ["gsettings", "set"]][0]
    assert set_call[-1] == str(["a@b", ls.EXT_UUID])


def test_install_extension_idempotent(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "metadata.json").write_text("{}")
    runner = fake({"get org.gnome.shell": (0, f"['{ls.EXT_UUID}']")})
    ls.install_extension(runner, src, tmp_path / "d")
    assert not [c for c in runner.calls if c[:2] == ["gsettings", "set"]]


def test_cli_doctor_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(ls, "run", lambda cmd: (1, ""))
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["doctor"]) == 0
    assert "session" in capsys.readouterr().out


def test_allow_app_writes_allowlist_and_app_config(tmp_path):
    runner = fake({"set org.gnome.shell.extensions.ya-bro": (0, "")})
    msg = ls.allow_app(runner, "org.gimp.GIMP", tmp_path / "ext", tmp_path / "cfg")
    assert "see: org.gimp.GIMP" in msg
    assert runner.calls[0][-1] == "['org.gimp.GIMP']"
    assert (tmp_path / "cfg" / "apps" / "org.gimp.GIMP.toml").read_text().startswith("[capture]")


def test_allow_app_rejects_bad_ids(tmp_path):
    runner = fake({})
    for bad in ["", "../x", "a b", ".hidden", "x" * 200]:
        assert "invalid" in ls.allow_app(runner, bad, tmp_path, tmp_path)
    assert runner.calls == []


def test_setup_names_app_after_extension_install(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "extension_target", lambda: tmp_path / "ext")
    monkeypatch.setattr(ls, "extension_source", lambda: None)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    runner = fake({"set org.gnome.shell.extensions.ya-bro": (0, "")})
    out = []
    answers = iter(["org.gimp.GIMP", "n", "y"])
    doctor.setup(ask=lambda _: next(answers), runner=runner, say=out.append)
    assert any("see: org.gimp.GIMP" in x for x in out)


def test_doctor_warns_when_no_app_allowed(tmp_path):
    c = ls.allowed_apps_check(
        fake({"get org.gnome.shell.extensions.ya-bro": (0, "@as []")}), tmp_path
    )
    assert c.status == "warn" and "no app" in c.detail
    ok = ls.allowed_apps_check(fake({"allowed-apps": (0, "['org.gimp.GIMP']")}), tmp_path)
    assert ok.status == "ok"


def stateful(initial):
    state = {"apps": list(initial)}

    def runner(cmd):
        if "get" in cmd:
            return 0, str(state["apps"])
        state["apps"] = ast.literal_eval(cmd[-1])
        return 0, ""

    runner.state = state
    return runner


def test_allow_adds_and_revoke_removes(tmp_path):
    r = stateful(["a.b"])
    ls.allow_app(r, "c.d", tmp_path, tmp_path, replace=False)
    ls.allow_app(r, "c.d", tmp_path, tmp_path, replace=False)  # idempotent
    assert r.state["apps"] == ["a.b", "c.d"]
    assert ls.revoke_app(r, "a.b", tmp_path, tmp_path) == "revoked a.b"
    assert r.state["apps"] == ["c.d"]
    assert (tmp_path / "apps" / "a.b.toml").read_text().endswith("false\n")
    assert "was not allowed" in ls.revoke_app(r, "zzz", tmp_path, tmp_path)


def test_broctl_apps_cli(monkeypatch, capsys):
    r = stateful([])
    monkeypatch.setattr(ls, "run", r)
    assert main(["apps", "list"]) == 0
    assert "sees nothing" in capsys.readouterr().out
    assert main(["version"]) == 0
