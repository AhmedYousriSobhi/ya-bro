import pytest

from ya_bro import cli, packs

PACK = """
[pack]
id = "demo"
name = "Demo"
version = "1.0.0"
[match]
desktop_ids = ["org.example.Demo"]
window_classes = ["Demo"]
argv0 = ["democtl"]
urls = ["http://127.0.0.1:*/"]
[sources]
agents_md = "https://example.org/AGENTS.md"
mcp = ["democtl", "serve", "mcp"]
"""

TASK = """
[plan]
goal = "do it"
[[step]]
narration = "Click."
target = {role = "button", name = "Go"}
"""


def make(tmp_path, pack_toml=PACK, name="demo", tasks=None, knowledge=None):
    root = tmp_path / name
    (root / "tasks").mkdir(parents=True)
    (root / "pack.toml").write_text(pack_toml)
    for n, body in (tasks or {}).items():
        (root / "tasks" / f"{n}.toml").write_text(body)
    if knowledge is not None:
        (root / "knowledge.md").write_text(knowledge)
    return root


def test_loads_everything(tmp_path):
    p = packs.load(make(tmp_path, tasks={"go": TASK}, knowledge="hello"))
    assert (p.id, p.version, p.trust, p.locales) == ("demo", "1.0.0", "data-only", ("en",))
    assert p.knowledge == "hello" and list(p.tasks) == ["go"]
    assert p.sources["mcp"] == ("democtl", "serve", "mcp")
    assert p.sources["agents_md"] == ("https://example.org/AGENTS.md",)


def test_matching_is_exact(tmp_path):
    p = packs.load(make(tmp_path))
    assert p.matches(app_id="org.example.Demo")
    assert p.matches(window_class="demo")
    assert p.matches(argv0="democtl")
    assert p.matches(url="http://127.0.0.1:8080/")
    assert not p.matches(app_id="org.example.Demo2")
    assert not p.matches(url="http://evil.example/")
    assert not p.matches()


@pytest.mark.parametrize(
    "old,new,msg",
    [
        ('id = "demo"', 'id = "Demo!"', "pack.id"),
        ('id = "demo"', 'id = "other"', "directory name"),
        ('version = "1.0.0"', 'version = "1"', "version"),
        ("[match]", 'trust = "root"\n[match]', "trust"),
        ('argv0 = ["democtl"]', 'cmdline = ["x"]', "unknown matcher"),
        ('desktop_ids = ["org.example.Demo"]', "desktop_ids = []", "ok-never"),
    ],
)
def test_rejects_bad_metadata(tmp_path, old, new, msg):
    text = PACK.replace(old, new)
    if msg == "ok-never":  # other matchers remain, so this one stays valid
        packs.load(make(tmp_path, text))
        return
    with pytest.raises(packs.PackError, match=msg):
        packs.load(make(tmp_path, text))


def test_needs_a_matcher(tmp_path):
    text = '[pack]\nid = "demo"\nname = "Demo"\nversion = "1.0.0"\n'
    with pytest.raises(packs.PackError, match="matcher"):
        packs.load(make(tmp_path, text))


def test_rejects_bad_task_and_big_knowledge(tmp_path):
    with pytest.raises(packs.PackError, match=r"tasks/bad\.toml"):
        packs.load(make(tmp_path, tasks={"bad": "[plan]\n"}))
    with pytest.raises(packs.PackError, match="knowledge.md"):
        packs.load(make(tmp_path / "k", knowledge="x" * (packs.MAX_KNOWLEDGE_CHARS + 1)))


def test_task_symlink_out_of_pack_is_refused(tmp_path):
    root = make(tmp_path)
    outside = tmp_path / "outside.toml"
    outside.write_text(TASK)
    (root / "tasks" / "link.toml").symlink_to(outside)
    with pytest.raises(packs.PackError, match="links"):
        packs.load(root)


def test_load_all_skips_broken_and_user_pack_wins(tmp_path):
    shipped, user = tmp_path / "shipped", tmp_path / "user"
    make(shipped, name="demo")
    make(shipped, PACK.replace("demo", "broken").replace('"1.0.0"', '"x"'), name="broken")
    make(user, PACK.replace('"1.0.0"', '"2.0.0"'), name="demo")
    found, problems = packs.load_all([shipped, user, tmp_path / "missing"])
    assert [(p.id, p.version) for p in found] == [("demo", "2.0.0")]
    assert len(problems) == 1 and "broken" in problems[0]
    assert [p.id for p in packs.resolve(found, app_id="org.example.Demo")] == ["demo"]
    assert packs.resolve(found, app_id="nothing") == []


def test_shipped_calculator_pack_is_valid():
    found, problems = packs.load_all([packs.SHIPPED])
    assert problems == []
    calc = packs.resolve(found, app_id="org.gnome.Calculator")
    assert [p.id for p in calc] == ["gnome-calculator"]
    assert "multiply" in calc[0].tasks and calc[0].knowledge


def test_broctl_pack(tmp_path, capsys, monkeypatch):
    root = make(tmp_path, tasks={"go": TASK})
    assert cli.main(["pack", "check", str(root)]) == 0
    assert "demo 1.0.0: ok (1 tasks" in capsys.readouterr().out
    (root / "pack.toml").write_text("nope =")
    assert cli.main(["pack", "check", str(root)]) == 1
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert cli.main(["pack", "list"]) == 0
    assert "gnome-calculator" in capsys.readouterr().out


FIXITS = """
[[fixit]]
code = "DM-REFUSED-MEMORY"
meaning = "No room."
suggest = "democtl plan"
[[fixit]]
code = "DM-NEEDS-YES"
meaning = "Needs --yes."
hint = "repeat with --yes"
"""


def test_fixits_load(tmp_path):
    root = make(tmp_path)
    (root / "fixits.toml").write_text(FIXITS)
    p = packs.load(root)
    assert p.fixits["DM-REFUSED-MEMORY"].suggest == "democtl plan"
    assert p.fixits["DM-NEEDS-YES"].hint == "repeat with --yes"


@pytest.mark.parametrize(
    "body,msg",
    [
        ('[[fixit]]\ncode = "bad code"\nmeaning = "x"\n', "needs a code"),
        ('[[fixit]]\ncode = "DM-A"\nmeaning = "x"\nsuggest = "rm -rf /"\n', "own commands"),
        (
            '[[fixit]]\ncode = "DM-A"\nmeaning = "x"\n[[fixit]]\ncode = "DM-A"\nmeaning = "y"\n',
            "dup",
        ),
        ("[[fixit]\n", "cannot read"),
    ],
)
def test_bad_fixits(tmp_path, body, msg):
    root = make(tmp_path)
    (root / "fixits.toml").write_text(body)
    with pytest.raises(packs.PackError, match=msg):
        packs.load(root)


def test_shipped_workbench_pack():
    found, problems = packs.load_all([packs.SHIPPED])
    assert problems == []
    (wb,) = packs.resolve(found, argv0="benchctl")
    assert wb.id == "workbench" and wb.trust == "data-only"
    assert {"start-cluster", "run-scenario", "clear-faults", "export-test-report"} <= set(wb.tasks)
    assert wb.fixits["WB-REFUSED-MEMORY"].suggest == "benchctl plan"
    assert "REFUSED" in wb.knowledge
    assert packs.resolve(found, argv0="ls") == []
