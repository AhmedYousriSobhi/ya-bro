import pytest

from ya_bro import dirs, ipc
from ya_bro.cli import main


def test_interface_name():
    assert ipc.interface_name("Overlay") == "io.github.ahmedyousrisobhi.YaBro.Overlay1"
    with pytest.raises(ValueError):
        ipc.interface_name("Nope")
    with pytest.raises(ValueError):
        ipc.interface_name("Core", 0)


def test_dirs_honour_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert dirs.config_dir() == tmp_path / "ya-bro"
    assert dirs.runtime_dir() == tmp_path / "ya-bro"


def test_dirs_ignore_relative_xdg(monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", "relative")
    assert dirs.state_dir().is_absolute()


def test_runtime_dir_requires_env(monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    with pytest.raises(RuntimeError):
        dirs.runtime_dir()


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert "broctl 0.2.0" in capsys.readouterr().out
