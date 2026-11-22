from tests.fakes import FakeActuator, FakeHotkeys, FakePerception, FakePolicy, FakeSecretStore
from ya_bro.types import ElementRef, Mode, Rect, Risk, Step


async def test_perception_find_and_locate():
    ref = ElementRef("gimp", "menu item", "Export As…")
    p = FakePerception({ref: Rect(1, 2, 30, 40)})
    assert await p.find("gimp", "menu item", "Export As…") == [ref]
    assert await p.locate(ref) == Rect(1, 2, 30, 40)
    assert await p.find("gimp", "button", "x") == []


async def test_abort_stops_actuation():
    a = FakeActuator()
    step = Step("click", "Click it")
    assert await a.act(step)
    await a.abort()
    assert not await a.act(step)
    assert a.acted == [step]


def test_policy_blocks_r3_in_do_it():
    pol = FakePolicy()
    r3 = Step("delete", "Delete", risk=Risk.R3)
    assert not pol.check(r3, Mode.DO_IT).allowed
    assert pol.check(r3, Mode.SHOW_ME).allowed


async def test_secret_roundtrip_and_hotkeys():
    s = FakeSecretStore()
    await s.put("k", "v")
    assert await s.get("k") == "v"
    assert [e async for e in FakeHotkeys(["stop"]).events()] == ["stop"]


def test_rect_center():
    assert Rect(0, 0, 10, 20).center == (5, 10)
