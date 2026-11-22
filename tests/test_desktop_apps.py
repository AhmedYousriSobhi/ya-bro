from ya_bro.cli import main
from ya_bro.platform import desktop_apps


def write(root, name, body):
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(body)


def test_available_parses_and_filters(tmp_path):
    user, system = tmp_path / "u", tmp_path / "s"
    write(user, "org.gimp.GIMP.desktop", "[Desktop Entry]\nType=Application\nName=GIMP\n")
    write(system, "org.gimp.GIMP.desktop", "[Desktop Entry]\nType=Application\nName=Shadowed\n")
    write(
        system,
        "chromium.desktop",
        "[Desktop Entry]\nType=Application\nName=Chromium\nStartupWMClass=chromium-browser\n",
    )
    write(system, "hidden.desktop", "[Desktop Entry]\nType=Application\nName=H\nNoDisplay=true\n")
    write(system, "link.desktop", "[Desktop Entry]\nType=Link\nName=L\n")
    apps = desktop_apps.available([user, system, tmp_path / "missing"])
    assert [a.app_id for a in apps] == ["chromium", "org.gimp.GIMP"]
    assert apps[1].name == "GIMP"
    assert apps[0].wm_class == "chromium-browser"


def test_cli_available(monkeypatch, capsys):
    monkeypatch.setattr(
        desktop_apps, "available", lambda: [desktop_apps.DesktopApp("a.b", "AB", "abc")]
    )
    assert main(["apps", "available"]) == 0
    assert "a.b\tAB  (window class: abc)" in capsys.readouterr().out
