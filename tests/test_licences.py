import importlib.util
import shutil
from email.message import Message
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_licences", ROOT / "scripts/check_licences.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_the_real_project_passes_the_gate():
    errors, rows = gate.run(ROOT)
    assert errors == [] and len(rows) >= 11
    scopes = {name: scope for name, scope, _l, _c in rows}
    assert scopes["pygobject"] == "optional" and scopes["pycairo"] == "optional"  # transitive
    assert scopes["pytest"] == "dev" and scopes["pluggy"] == "dev"
    assert not any(scope == "runtime" for scope in scopes.values())  # core has no dependencies


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("MIT", "permissive"),
        ("Apache-2.0 OR BSD-2-Clause", "permissive"),
        ("LGPL-2.1-or-later", "weak"),
        ("LGPL-2.1-only OR MPL-1.1", "weak"),
        ("GPL-3.0-or-later", "strong"),
        ("AGPL-3.0-only", "strong"),
        ("GPL-2.0-only OR MIT", "permissive"),  # the user may pick MIT
        ("MIT AND GPL-3.0-only", "strong"),  # all of it applies
        ("GPL-2.0-only WITH Classpath-exception-2.0", "strong"),
        ("Some-Unknown-1.0", "unknown"),
        ("", "unknown"),
    ],
)
def test_licence_expressions(expr, expected):
    assert gate.expression_category(expr) == expected


class FakeDist:
    def __init__(self, **headers):
        self.metadata = Message()
        for k, v in headers.items():
            if isinstance(v, list):
                for item in v:
                    self.metadata[k.replace("_", "-")] = item
            else:
                self.metadata[k.replace("_", "-")] = v


@pytest.mark.parametrize(
    "headers,expected",
    [
        ({"License_Expression": "MIT"}, "permissive"),
        ({"License": "GNU General Public License v3"}, "strong"),
        ({"License": "GNU Affero General Public License"}, "strong"),
        ({"License": "LGPL-2.1-or-later"}, "weak"),
        ({"Classifier": "License :: OSI Approved :: MIT License"}, "permissive"),
        (
            {"Classifier": "License :: OSI Approved :: GNU General Public License v3 (GPLv3)"},
            "strong",
        ),
        ({"License_Expression": "GPL-3.0-only OR MIT"}, "permissive"),
        ({}, None),
    ],
)
def test_what_installed_metadata_says(headers, expected):
    assert gate.metadata_category(FakeDist(**headers)) == expected


# ---- a small project tree we can break --------------------------------------------------------

PYPROJECT = """
[project]
name = "demo"
version = "0.1.0"
license = "MIT"
license-files = ["LICENSE"]
dependencies = []
[project.optional-dependencies]
gi = ["PyGObject>=3.50"]
[dependency-groups]
dev = ["pytest>=8"]
"""
LOCK = """
[[package]]
name = "pygobject"
dependencies = [{ name = "pycairo" }]
[[package]]
name = "pycairo"
[[package]]
name = "pytest"
dependencies = [{ name = "pluggy" }]
[[package]]
name = "pluggy"
[[package]]
name = "demo"
"""
POLICY = """
[packages.pygobject]
license = "LGPL-2.1-or-later"
scope = "optional"
[packages.pycairo]
license = "LGPL-2.1-only OR MPL-1.1"
scope = "optional"
[packages.pytest]
license = "MIT"
scope = "dev"
[packages.pluggy]
license = "MIT"
scope = "dev"
[forbidden]
names = ["piper-tts", "dogtail"]
modules = ["piper", "dogtail"]
"""


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    (tmp_path / "uv.lock").write_text(LOCK)
    (tmp_path / "LICENSE").write_text("MIT License\n\nCopyright (c) 2026\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "licences.toml").write_text(POLICY)
    (tmp_path / "src" / "demo").mkdir(parents=True)
    (tmp_path / "src" / "demo" / "__init__.py").write_text("import os\n")
    pack = tmp_path / "packs" / "p"
    pack.mkdir(parents=True)
    (pack / "pack.toml").write_text('[pack]\nid = "p"\nlicense = "MIT"\n')
    return tmp_path


def errors(tree):
    return gate.run(tree)[0]


def edit(tree, rel, old, new):
    p = tree / rel
    assert old in p.read_text(), (rel, old)
    p.write_text(p.read_text().replace(old, new))


def test_a_clean_tree_passes(tree):
    assert errors(tree) == []


def test_an_unlisted_dependency_fails_closed(tree):
    edit(tree, "pyproject.toml", "dependencies = []", 'dependencies = ["newthing>=1"]')
    edit(
        tree,
        "uv.lock",
        '[[package]]\nname = "demo"',
        '[[package]]\nname = "newthing"\n[[package]]\nname = "demo"',
    )
    assert any("newthing" in e and "not in docs/licences.toml" in e for e in errors(tree))


def test_a_transitive_dependency_is_checked_too(tree):
    edit(
        tree,
        "docs/licences.toml",
        '[packages.pycairo]\nlicense = "LGPL-2.1-only OR MPL-1.1"',
        '[packages.pycairo]\nlicense = "GPL-3.0-only"',
    )
    assert any("pycairo" in e and "strong copyleft" in e for e in errors(tree))


def test_gpl_is_refused_in_the_runtime_closure_but_lgpl_is_fine(tree):
    edit(tree, "pyproject.toml", "dependencies = []", 'dependencies = ["gplthing"]')
    edit(
        tree,
        "uv.lock",
        '[[package]]\nname = "demo"',
        '[[package]]\nname = "gplthing"\n[[package]]\nname = "demo"',
    )
    edit(
        tree,
        "docs/licences.toml",
        "[forbidden]",
        '[packages.gplthing]\nlicense = "GPL-3.0-or-later"\nscope = "runtime"\n[forbidden]',
    )
    assert any("gplthing" in e and "strong copyleft" in e for e in errors(tree))


def test_copyleft_is_allowed_only_for_tests_only_and_never_when_it_ships(tree):
    edit(tree, "pyproject.toml", 'dev = ["pytest>=8"]', 'dev = ["pytest>=8", "dogtail"]')
    edit(
        tree,
        "uv.lock",
        '[[package]]\nname = "demo"',
        '[[package]]\nname = "dogtail"\n[[package]]\nname = "demo"',
    )
    policy = '[packages.dogtail]\nlicense = "GPL-2.0-only"\nscope = "tests-only"\n[forbidden]'
    edit(tree, "docs/licences.toml", "[forbidden]", policy)
    assert errors(tree) == []  # a test helper, never shipped, never imported
    edit(tree, "pyproject.toml", 'gi = ["PyGObject>=3.50"]', 'gi = ["PyGObject>=3.50", "dogtail"]')
    found = errors(tree)
    assert any("dogtail" in e and "forbidden" in e for e in found)
    assert any("dogtail" in e and "tests-only but reachable" in e for e in found)


def test_dev_tools_may_not_be_strong_copyleft_without_saying_so(tree):
    edit(
        tree,
        "docs/licences.toml",
        '[packages.pluggy]\nlicense = "MIT"',
        '[packages.pluggy]\nlicense = "GPL-2.0-only"',
    )
    assert any("pluggy" in e for e in errors(tree))


def test_an_unrecognised_licence_or_scope_is_refused(tree):
    edit(
        tree,
        "docs/licences.toml",
        '[packages.pluggy]\nlicense = "MIT"',
        '[packages.pluggy]\nlicense = "Weird-1.0"',
    )
    assert any("pluggy" in e and "not one this gate recognises" in e for e in errors(tree))
    edit(
        tree,
        "docs/licences.toml",
        'license = "Weird-1.0"\nscope = "dev"',
        'license = "MIT"\nscope = "sometimes"',
    )
    assert any("scope must be one of" in e for e in errors(tree))


def test_installed_metadata_that_disagrees_with_the_policy_is_caught(tree, monkeypatch):
    real = gate.metadata.distribution

    def fake(name):
        if name == "pytest":
            return FakeDist(License_Expression="GPL-3.0-only")
        return real(name)

    monkeypatch.setattr(gate.metadata, "distribution", fake)
    assert any("pytest" in e and "installed metadata says strong" in e for e in errors(tree))


def test_source_files_may_not_import_copyleft_modules(tree):
    (tree / "src" / "demo" / "voice.py").write_text("import piper\nfrom dogtail.tree import root\n")
    found = errors(tree)
    assert any("voice.py:1" in e and "piper" in e for e in found)
    assert any("voice.py:2" in e and "dogtail" in e for e in found)
    (tree / "src" / "demo" / "voice.py").write_text(
        "import subprocess  # piper runs as a process\n"
    )
    assert errors(tree) == []


def test_the_project_licence_must_be_mit_and_present(tree):
    edit(tree, "pyproject.toml", 'license = "MIT"', 'license = "Apache-2.0"')
    assert any("pyproject.toml: license" in e for e in errors(tree))
    edit(tree, "pyproject.toml", 'license = "Apache-2.0"', 'license = "MIT"')
    (tree / "LICENSE").write_text("Some other terms")
    assert any("LICENSE" in e for e in errors(tree))
    (tree / "LICENSE").unlink()
    assert any("LICENSE" in e for e in errors(tree))
    edit(tree, "pyproject.toml", 'license-files = ["LICENSE"]', "")
    assert any("license-files" in e for e in errors(tree))


def test_every_shipped_pack_says_mit(tree):
    (tree / "packs" / "p" / "pack.toml").write_text('[pack]\nid = "p"\n')
    assert any("shipped packs must say" in e for e in errors(tree))
    (tree / "packs" / "p" / "pack.toml").write_text('[pack]\nid = "p"\nlicense = "GPL-3.0-only"\n')
    assert any("shipped packs must say" in e for e in errors(tree))
    shutil.rmtree(tree / "packs")
    assert errors(tree) == []


def test_the_script_runs_and_the_markdown_table_lists_every_package(capsys):
    assert gate.main([]) == 0 and "licence gate: ok" in capsys.readouterr().out
    assert gate.main(["--markdown"]) == 0
    table = capsys.readouterr().out
    assert table.startswith("| Package |") and "pygobject" in table and "LGPL" in table


# ---- pack licences ----------------------------------------------------------------------------


def test_pack_licence_field_is_read_and_validated(tmp_path):
    from ya_bro import packs

    root = tmp_path / "demo"
    root.mkdir()
    base = '[pack]\nid="demo"\nname="D"\nversion="1.0.0"\n{lic}[match]\nargv0=["x"]\n'
    (root / "pack.toml").write_text(base.format(lic='license = "Apache-2.0 OR MIT"\n'))
    assert packs.load(root).license == "Apache-2.0 OR MIT"
    (root / "pack.toml").write_text(base.format(lic=""))
    assert packs.load(root).license == ""
    for bad in ("license = 5\n", 'license = "MIT; rm -rf"\n'):
        (root / "pack.toml").write_text(base.format(lic=bad))
        with pytest.raises(packs.PackError, match="pack.license"):
            packs.load(root)
    found, problems = packs.load_all([packs.SHIPPED])
    assert problems == [] and {p.license for p in found} == {"MIT"}


def test_the_licences_document_lists_exactly_the_current_closure():
    errors_, rows = gate.run(ROOT)
    assert errors_ == []
    doc = (ROOT / "docs" / "LICENCES.md").read_text()
    assert gate.markdown(rows) in doc, (
        "docs/LICENCES.md is stale: run scripts/check_licences.py --markdown"
    )
