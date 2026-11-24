import http.client

import pytest

from ya_bro import targets, token_server
from ya_bro.cli import main

ORIGIN = "http://127.0.0.1:8080"


def test_save_load_revoke_roundtrip(tmp_path):
    t = targets.Target("workbench", (ORIGIN + "/",), ("benchctl",))
    targets.save(t, tmp_path)
    assert targets.load_all(tmp_path) == [targets.Target("workbench", (ORIGIN,), ("benchctl",))]
    assert targets.allowed_origins(tmp_path) == {ORIGIN}
    assert targets.remove("workbench", tmp_path) is True
    assert targets.remove("workbench", tmp_path) is False
    assert targets.load_all(tmp_path) == []


@pytest.mark.parametrize(
    "target",
    [
        targets.Target("Bad Id", (ORIGIN,)),
        targets.Target("x", ("http://a.com/path",)),
        targets.Target("x", ("ftp://a.com",)),
        targets.Target("x", (), ("rm -rf",)),
        targets.Target("x"),
    ],
)
def test_invalid_targets_are_refused(tmp_path, target):
    with pytest.raises(targets.TargetError):
        targets.save(target, tmp_path)


def test_malformed_file_is_skipped_not_widened(tmp_path):
    d = tmp_path / "targets"
    d.mkdir()
    (d / "bad.toml").write_text('[target]\nid = "bad"\n[web]\norigins = ["*"]\n')
    (d / "junk.toml").write_text("not toml [[[")
    assert targets.load_all(tmp_path) == []


def _get(srv, path="/token", method="GET", **headers):
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
    conn.request(method, path, headers=headers)
    r = conn.getresponse()
    return r.status, r.read().decode(), r


@pytest.fixture
def server():
    token = token_server.new_token()
    srv = token_server.TokenServer(token, lambda: frozenset({ORIGIN}), port=0)
    srv.start()
    yield srv
    srv.stop()


def test_token_only_for_allowed_origin_with_header(server):
    assert len(server.token) >= 16
    status, body, resp = _get(server, Origin=ORIGIN, **{"X-Scope-Token": "1"})
    assert (status, body) == (200, server.token)
    assert resp.getheader("Access-Control-Allow-Origin") == ORIGIN
    assert _get(server, Origin="http://evil.example", **{"X-Scope-Token": "1"})[0] == 403
    assert _get(server, Origin=ORIGIN)[0] == 403  # no X-Scope-Token header
    assert _get(server, **{"X-Scope-Token": "1"})[0] == 403  # no Origin (curl, a local script)
    assert _get(server, "/other", Origin=ORIGIN, **{"X-Scope-Token": "1"})[0] == 403


def test_preflight_only_for_allowed_origin(server):
    ok = _get(server, method="OPTIONS", Origin=ORIGIN)
    assert ok[0] == 204 and ok[2].getheader("Access-Control-Allow-Headers") == "X-Scope-Token"
    bad = _get(server, method="OPTIONS", Origin="http://evil.example")
    assert bad[0] == 403 and bad[2].getheader("Access-Control-Allow-Origin") is None


def test_dns_rebinding_host_is_refused(server):
    status, _, _ = _get(server, Origin=ORIGIN, Host="evil.example", **{"X-Scope-Token": "1"})
    assert status == 403


def test_revoked_origin_stops_getting_tokens(tmp_path):
    targets.save(targets.Target("w", (ORIGIN,)), tmp_path)
    srv = token_server.TokenServer("yb-x" * 8, lambda: targets.allowed_origins(tmp_path), port=0)
    srv.start()
    try:
        assert _get(srv, Origin=ORIGIN, **{"X-Scope-Token": "1"})[0] == 200
        targets.remove("w", tmp_path)
        assert _get(srv, Origin=ORIGIN, **{"X-Scope-Token": "1"})[0] == 403
    finally:
        srv.stop()


def test_broctl_targets_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert main(["targets", "list"]) == 0
    assert "no targets" in capsys.readouterr().out
    assert main(["targets", "allow", "workbench", "--origin", ORIGIN, "--command", "benchctl"]) == 0
    assert "token endpoint" in capsys.readouterr().out
    assert main(["targets", "list"]) == 0
    assert "workbench" in capsys.readouterr().out
    assert main(["targets", "allow", "x", "--origin", "http://a.com/p"]) == 1
    assert main(["targets", "revoke", "workbench"]) == 0
    assert "revoked" in capsys.readouterr().out


def test_a_tools_folder_roundtrips_and_must_be_absolute_and_exist(tmp_path):
    work = tmp_path / "opti-sim"
    work.mkdir()
    cfg = tmp_path / "cfg"
    targets.save(targets.Target("workbench", (), ("benchctl",), str(work)), cfg)
    (t,) = targets.load_all(cfg)
    assert t.dir == str(work)
    for bad in ("relative/dir", "/does/not/exist", "/tmp/\nx", "/" + "a" * 200):
        with pytest.raises(targets.TargetError):
            targets.save(targets.Target("workbench", (), ("benchctl",), bad), cfg)


def test_a_target_file_with_a_relative_folder_is_skipped(tmp_path):
    d = tmp_path / "targets"
    d.mkdir()
    (d / "x.toml").write_text('[target]\nid = "x"\n[cli]\ncommands = ["c"]\ndir = "relative"\n')
    assert targets.load_all(tmp_path) == []


def test_targets_allow_dir_and_list_show_the_folder(tmp_path, monkeypatch, capsys):
    from ya_bro.cli import main

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    work = tmp_path / "w"
    work.mkdir()
    assert main(["targets", "allow", "wb", "--command", "benchctl", "--dir", str(work)]) == 0
    assert main(["targets", "list"]) == 0
    assert f"dir: {work}" in capsys.readouterr().out
