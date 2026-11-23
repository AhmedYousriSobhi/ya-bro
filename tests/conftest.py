import pytest


@pytest.fixture(autouse=True)
def _private_dirs(tmp_path, monkeypatch):
    """No test may read or write the maintainer's real config, state or cache."""
    for var, name in (("CONFIG", "cfg"), ("STATE", "state"), ("CACHE", "cache")):
        monkeypatch.setenv(f"XDG_{var}_HOME", str(tmp_path / f"xdg-{name}"))
