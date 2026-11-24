import ast

from ya_bro import doctor
from ya_bro.cli import main
from ya_bro.platform import desktop_apps
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


def _quiet(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setattr(ls, "extension_target", lambda: tmp_path / "ext")
    monkeypatch.setattr(ls, "extension_source", lambda: None)


def test_setup_steps_default_to_yes_and_n_skips(tmp_path, monkeypatch):
    _quiet(monkeypatch, tmp_path)
    runner = fake({})
    out = []
    # consent: no, then nothing chosen, accessibility: Enter (yes), extension: n
    answers = iter(["", "", "", "n"])
    doctor.setup(ask=lambda _: next(answers), runner=runner, say=out.append, apps=[], tools=[])
    assert ["gsettings", "set", ls.SCHEMA_IFACE, "toolkit-accessibility", "true"] in runner.calls
    assert sum(x.startswith("skipped") for x in out) == 1


def test_setup_yes_flag_takes_the_two_steps_but_still_asks_consent(tmp_path, monkeypatch):
    _quiet(monkeypatch, tmp_path)
    runner = fake({"set org.gnome.desktop.interface": (0, "")})
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return ""

    doctor.setup(ask=ask, runner=runner, say=lambda _: None, apps=[], tools=[], assume_yes=True)
    assert any("sending that to Claude" in p for p in asked)  # privacy stays a question
    assert not any(p.startswith("Do this") for p in asked)
    assert ["gsettings", "set", ls.SCHEMA_IFACE, "toolkit-accessibility", "true"] in runner.calls


def test_setup_privacy_answers_still_default_to_no(tmp_path, monkeypatch):
    from ya_bro import privacy

    _quiet(monkeypatch, tmp_path)
    doctor.setup(ask=lambda _: "", runner=fake({}), say=lambda _: None, apps=[], tools=[])
    c = privacy.load_consent()
    assert c.given and not c.send_to_llm and not c.screenshots


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
    _quiet(monkeypatch, tmp_path)
    runner = fake({"set org.gnome.shell.extensions.ya-bro": (0, "")})
    out = []
    gimp = desktop_apps.DesktopApp("org.gimp.GIMP", "GIMP", "")
    # consent n; "1" = an installed app; GIMP is in the list; two steps default yes
    answers = iter(["", "1", "1", "", ""])
    doctor.setup(ask=lambda _: next(answers), runner=runner, say=out.append, apps=[gimp], tools=[])
    assert any("see: org.gimp.GIMP" in x for x in out)
    assert any("1. GIMP" in x for x in out)  # the list is shown without typing a search first


def test_app_list_pages_filters_and_skips():
    apps = [desktop_apps.DesktopApp(f"org.x.App{n}", f"App {n:02}", "") for n in range(40)]
    out = []
    answers = iter(["", "", "q"])  # next page, next page, skip
    assert doctor.choose_app(lambda _: next(answers), out.append, apps) == ""
    assert any("App 15" in x for x in out) and any("App 30" in x for x in out)
    out.clear()
    answers = iter(["app 3", "2"])  # filter, then the second hit
    assert doctor.choose_app(lambda _: next(answers), out.append, apps) == "org.x.App31"


def test_a_browser_needs_a_second_yes_and_points_at_the_tool_route():
    ff = desktop_apps.DesktopApp("firefox_firefox", "Firefox", "")
    out = []
    answers = iter(["1", "n", "q"])  # pick Firefox, refuse the warning, leave
    assert doctor.choose_app(lambda _: next(answers), out.append, [ff]) == ""
    assert any("EVERY Firefox window" in x and "tool" in x for x in out)
    answers = iter(["1", "y"])
    assert doctor.choose_app(lambda _: next(answers), out.append, [ff]) == "firefox_firefox"


def test_a_tool_is_allowed_as_a_target_not_an_app(tmp_path, monkeypatch):
    from ya_bro import targets

    _quiet(monkeypatch, tmp_path)
    runner = fake({})
    out = []
    wb = doctor.Tool("workbench", "workbench", ("benchctl",))
    # consent n; pick the tool (1); web page; accessibility and extension default yes
    answers = iter(["", "1", "http://127.0.0.1:8080", "", "", ""])  # web page, folder: none
    doctor.setup(ask=lambda _: next(answers), runner=runner, say=out.append, apps=[], tools=[wb])
    t = targets.load_all()[0]
    assert (t.id, t.origins, t.commands) == ("workbench", ("http://127.0.0.1:8080",), ("benchctl",))
    assert not any(
        c[:3] == ["gsettings", "set", "org.gnome.shell.extensions.ya-bro"] for c in runner.calls
    )


def test_a_bad_tool_address_is_refused_without_saving(tmp_path, monkeypatch):
    from ya_bro import targets

    _quiet(monkeypatch, tmp_path)
    out = []
    wb = doctor.Tool("workbench", "workbench", ("benchctl",))
    answers = iter(["", "1", "http://x/path?secret=1", "", "", ""])
    doctor.setup(ask=lambda _: next(answers), runner=fake({}), say=out.append, apps=[], tools=[wb])
    assert targets.load_all() == [] and any("not saved" in x for x in out)


def test_real_packs_offer_workbench_as_a_tool():
    t = {x.id: x for x in doctor.tool_packs()}
    assert t["workbench"].commands == ("benchctl",)


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


APPS = [
    desktop_apps.DesktopApp("org.gimp.GIMP", "GIMP"),
    desktop_apps.DesktopApp("chromium_chromium", "Chromium", "chromium-browser"),
    desktop_apps.DesktopApp("org.gnome.Calculator", "Calculator"),
]


def run_picker(answers, apps=APPS):
    it, out = iter(answers), []
    return doctor.choose_app(lambda _: next(it), out.append, apps), out


def test_picker_search_and_pick_by_number():
    app, out = run_picker(["gimp", "1"])
    assert app == "org.gimp.GIMP" and any("GIMP" in x for x in out)


def test_picker_uses_window_class_when_present():
    assert run_picker(["chrom", "1", "y"])[0] == "chromium-browser"  # a browser: second yes


def test_picker_q_skips_and_a_bad_number_asks_again():
    assert run_picker(["q"])[0] == ""
    app, out = run_picker(["calc", "9", "1"])
    assert app == "org.gnome.Calculator" and any("not on this page" in x for x in out)


def test_picker_no_match_then_trusts_typed_id():
    app, out = run_picker(["zzzz", "org.example.Known"])
    assert app == "org.example.Known" and any("no installed app" in x for x in out)


def test_picker_enter_on_the_last_page_starts_over_instead_of_picking():
    app, out = run_picker(["gimp", "", "1"])
    assert app == "org.gimp.GIMP" and sum("GIMP" in x for x in out) >= 2


def test_hotload_snippet_is_one_line_and_names_the_extension():
    assert "\n" not in ls.HOTLOAD_SNIPPET and ls.EXT_UUID in ls.HOTLOAD_SNIPPET
    assert "loadExtension" in ls.HOTLOAD_SNIPPET


def test_broctl_load_is_noop_when_loaded(monkeypatch, capsys):
    monkeypatch.setattr(ls, "run", fake({"GetExtensionInfo": (0, "({'state': <1.0>},)")}))
    monkeypatch.setattr(ls, "extension_code_check", lambda _r: ls.Check("extension code", "ok", ""))
    assert main(["load"]) == 0
    assert "already loaded" in capsys.readouterr().out


# ---- a stale extension is noticed (#120) ----


def _tree(root, files):
    for name, text in files.items():
        f = root / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    return root


def _shell(age):
    return fake({"pgrep": (0, "123\n"), "etimes=": (0, f"{age}\n")})


def test_an_installed_copy_that_differs_from_the_checkout_is_reported(tmp_path):
    src = _tree(tmp_path / "src", {"overlay.js": "new", "schemas/a.xml": "x"})
    dst = _tree(tmp_path / "dst", {"overlay.js": "old", "schemas/a.xml": "x"})
    c = ls.extension_code_check(_shell(10), src, dst)
    assert c.status == "warn" and "differs" in c.detail and "broctl setup" in c.fix


def test_a_file_missing_from_the_installed_copy_is_reported(tmp_path):
    src = _tree(tmp_path / "src", {"overlay.js": "a", "assets/bro.svg": "b"})
    dst = _tree(tmp_path / "dst", {"overlay.js": "a"})
    assert ls.extension_code_check(_shell(10), src, dst).status == "warn"


def test_code_installed_after_the_shell_started_needs_a_login(tmp_path):
    src = _tree(tmp_path / "src", {"overlay.js": "a"})
    dst = _tree(tmp_path / "dst", {"overlay.js": "a"})
    c = ls.extension_code_check(_shell(1_000_000), src, dst)  # shell older than the files
    assert c.status == "warn" and "log out" in c.fix


def test_a_current_copy_older_than_the_shell_is_ok(tmp_path):
    src = _tree(tmp_path / "src", {"overlay.js": "a"})
    dst = _tree(tmp_path / "dst", {"overlay.js": "a"})
    c = ls.extension_code_check(_shell(5), src, dst, now=lambda: dst.stat().st_ctime + 1000)
    assert c.status == "ok"


def test_not_installed_says_run_setup(tmp_path):
    c = ls.extension_code_check(_shell(5), tmp_path / "src", tmp_path / "missing")
    assert c.status == "warn" and "setup" in c.fix


def test_load_says_when_the_loaded_extension_is_old(monkeypatch, capsys):
    from ya_bro import cli

    monkeypatch.setattr(ls, "extension_loaded", lambda _r: True)
    monkeypatch.setattr(
        ls, "extension_code_check", lambda _r: ls.Check("extension code", "warn", "old", "log out")
    )
    assert cli._load() == 1
    assert "log out" in capsys.readouterr().out


def test_setup_asks_where_a_tool_runs_and_saves_the_folder(tmp_path, monkeypatch):
    from ya_bro import targets

    _quiet(monkeypatch, tmp_path)
    work = tmp_path / "opti-sim"
    work.mkdir()
    wb = doctor.Tool("workbench", "workbench", ("benchctl",))
    answers = iter(["", "1", "", str(work), "", ""])  # consent n, tool, no web page, folder, steps
    doctor.setup(
        ask=lambda _: next(answers), runner=fake({}), say=lambda _: None, apps=[], tools=[wb]
    )
    assert targets.load_all()[0].dir == str(work)


def test_a_rewritten_copy_with_old_mtimes_is_not_new_code(tmp_path):
    import os

    src = _tree(tmp_path / "src", {"overlay.js": "a"})
    dst = _tree(tmp_path / "dst", {"overlay.js": "a"})
    old = dst.stat().st_mtime - 5000
    os.utime(dst / "overlay.js", (old, old))  # setup copied it again: ctime is new, mtime is not
    assert ls.extension_code_check(_shell(100), src, dst).status == "ok"


def test_terminal_check_tells_a_vte_window_from_an_embedded_terminal():
    assert ls.terminal_check({"VTE_VERSION": "8003"}).status == "ok"
    vs = ls.terminal_check({"VTE_VERSION": "8003", "TERM_PROGRAM": "vscode"})
    assert vs.status == "warn" and "VS Code" in vs.detail and "Ptyxis" in vs.fix
    assert ls.terminal_check({}).status == "warn"
