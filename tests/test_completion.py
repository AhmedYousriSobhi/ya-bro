"""Tab completion for broctl (#124): generated from the parser and exercised in a real bash."""

import shutil
import subprocess

import pytest

from ya_bro import completion
from ya_bro.cli import build_parser, main

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")


def complete(tmp_path, *words):
    """What bash's completion offers after `words` (the last one is the word being typed)."""
    script = tmp_path / "bc.bash"
    script.write_text(completion.bash_script(build_parser()))
    probe = (
        f'. {script}; COMP_WORDS=("$@"); COMP_CWORD=$(( ${{#COMP_WORDS[@]}} - 1 )); '
        'COMPREPLY=(); _broctl; printf "%s\\n" "${COMPREPLY[@]}"'
    )
    r = subprocess.run(["bash", "-c", probe, "x", "broctl", *words], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def test_the_script_is_valid_bash_for_both_shells(tmp_path, capsys):
    for shell in ("bash", "zsh"):
        assert main(["completion", shell]) == 0
        f = tmp_path / f"{shell}.sh"
        f.write_text(capsys.readouterr().out)
        if shell == "bash":
            assert subprocess.run(["bash", "-n", str(f)]).returncode == 0
    assert "bashcompinit" in f.read_text()


def test_every_command_the_parser_has_is_offered(tmp_path):
    parser = build_parser()
    names = set(next(a for a in parser._actions if a.dest == "noun").choices)
    assert names <= set(complete(tmp_path, ""))
    assert {"setup", "ask", "targets", "completion"} <= names


def test_prefix_filters_and_nested_commands_complete(tmp_path):
    assert complete(tmp_path, "se") == ["sent", "setup"]
    assert set(complete(tmp_path, "targets", "")) >= {"allow", "list", "revoke"}
    assert set(complete(tmp_path, "persona", "")) >= {"lint", "list", "say", "style"}


def test_flags_complete_after_an_argument_and_for_a_leaf(tmp_path):
    assert "--pack" in complete(tmp_path, "ask", "start the cluster", "--")
    assert set(complete(tmp_path, "targets", "allow", "--")) >= {"--origin", "--command"}
    assert "--yes" in complete(tmp_path, "setup", "--")


def test_choices_complete_and_unknown_commands_offer_nothing(tmp_path):
    assert set(complete(tmp_path, "completion", "")) >= {"bash", "zsh"}
    assert complete(tmp_path, "nosuchcommand", "") == []


def test_install_writes_where_bash_completion_loads_it(tmp_path):
    path = completion.install(
        build_parser(), tmp_path / "bash-completion" / "completions" / "broctl"
    )
    assert path.read_text().startswith("# bash completion for broctl")
    assert "complete -F _broctl broctl" in path.read_text()


def test_setup_installs_completion_unless_declined(tmp_path, monkeypatch):
    from ya_bro import doctor
    from ya_bro.platform import linux_setup as ls

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(ls, "extension_source", lambda: None)
    monkeypatch.setattr(ls, "extension_target", lambda: tmp_path / "ext")
    target = completion.target()
    assert target == tmp_path / "data" / "bash-completion" / "completions" / "broctl"
    assert not target.exists()
    runner = lambda cmd: (0, "")  # noqa: E731
    answers = iter(["", "", "", "", "n"])  # consent, nothing chosen, two steps, completion: no
    doctor.setup(ask=lambda _: next(answers), runner=runner, say=lambda _: None, apps=[], tools=[])
    assert not target.exists()
    answers = iter(["", "", "", ""])  # completion: Enter = yes
    doctor.setup(ask=lambda _: next(answers), runner=runner, say=lambda _: None, apps=[], tools=[])
    assert target.is_file()
