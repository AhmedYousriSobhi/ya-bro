import json
import logging

import pytest

from ya_bro import config, logs


def test_defaults_when_missing(tmp_path):
    cfg = config.load(config_dir=tmp_path)
    assert cfg == config.Config()
    assert cfg.proactive.enabled is False


def test_load_global_and_app_override(tmp_path):
    (tmp_path / "config.toml").write_text(
        'humour = 2\n[proactive]\nenabled = true\nsensitivity = "high"\n'
    )
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "gimp.toml").write_text("[proactive]\nenabled = false\n")
    assert config.load(config_dir=tmp_path).proactive.enabled is True
    app = config.load("gimp", config_dir=tmp_path)
    assert app.proactive.enabled is False
    assert app.proactive.sensitivity == "high"
    assert app.humour == 2


def test_unknown_and_bad_values_warn(tmp_path, caplog):
    (tmp_path / "config.toml").write_text(
        'bogus = 1\nhumour = 9\n[capture]\nallowed = "yes"\nnope = true\n[do_it]\nallowed = true\n'
    )
    with caplog.at_level(logging.WARNING):
        cfg = config.load(config_dir=tmp_path)
    text = caplog.text
    assert "bogus" in text and "humour" in text and "capture.allowed" in text
    assert "capture.nope" in text
    assert cfg.humour == 1 and cfg.capture.allowed is False and cfg.do_it.allowed is True


def test_broken_toml_is_ignored(tmp_path, caplog):
    (tmp_path / "config.toml").write_text("this is = = not toml")
    with caplog.at_level(logging.WARNING):
        assert config.load(config_dir=tmp_path) == config.Config()
    assert "cannot read" in caplog.text


def test_app_id_cannot_escape(tmp_path):
    with pytest.raises(ValueError):
        config.load("../x", config_dir=tmp_path)


def test_loads_from_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "ya-bro").mkdir()
    (tmp_path / "ya-bro" / "config.toml").write_text("humour = 3\n")
    assert config.load().humour == 3


IDS = logs.Ids(session_id="s1", task_id="t1", step_id="st1", corr_id="c1")


def test_record_has_ids_and_typed_fields():
    r = logs.make_record("step.done", IDS, latency_ms=812, ok=True, tier="T1", err="KeyError")
    assert r["session_id"] == "s1" and r["corr_id"] == "c1"
    assert r["latency_ms"] == 812 and r["ok"] is True


@pytest.mark.parametrize(
    "value",
    ["hello world, my password is hunter2", "x" * 65, "line\nbreak", "", b"bytes", ["a"], None],
)
def test_free_text_and_odd_types_rejected(value):
    with pytest.raises(logs.ContentError):
        logs.make_record("step.done", IDS, detail=value)


@pytest.mark.parametrize("event", ["Has Space", "", "1abc"])
def test_bad_event_rejected(event):
    with pytest.raises(logs.ContentError):
        logs.make_record(event, IDS)


def test_cannot_shadow_reserved_keys():
    with pytest.raises(logs.ContentError):
        logs.make_record("e", IDS, ts=1)


def test_bad_id_rejected():
    with pytest.raises(logs.ContentError):
        logs.make_record("e", logs.Ids(session_id="typed text here"))


def test_jsonl_file_written_private(tmp_path):
    log = logs.JsonlLog(IDS, path=tmp_path / "logs" / "a.jsonl")
    log.write("offer.shown", count=1)
    log.write("offer.refused", count=2)
    log.close()
    lines = (tmp_path / "logs" / "a.jsonl").read_text().splitlines()
    assert [json.loads(x)["event"] for x in lines] == ["offer.shown", "offer.refused"]
    assert (tmp_path / "logs" / "a.jsonl").stat().st_mode & 0o777 == 0o600
