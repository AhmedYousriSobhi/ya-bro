"""Struggle offers from real signals: a real bash with the hook, the real spool, the real host."""

import asyncio
import contextlib
import shutil
import time

import pytest

from tests.test_shell_hook import Bash
from ya_bro.shell_spool import ShellSpool
from ya_bro.struggle import Detector
from ya_bro.struggle_host import StruggleHost

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")


@pytest.fixture
def world(tmp_path):
    runtime = tmp_path / "run"
    runtime.mkdir(mode=0o700)
    spool = ShellSpool(runtime / "ya-bro")
    spool.open(["fakectl"])
    det = Detector(time.time)
    det.opt_in("workbench")
    offers = []
    host = StruggleHost(det, {"fakectl": "workbench"}, shell=spool, on_offer=offers.append)
    (tmp_path / "sh").mkdir()
    sh = Bash(tmp_path / "sh", runtime)
    yield det, host, offers, sh
    sh.close()
    spool.close()


async def type_commands(sh, *lines):
    for line in lines:
        await asyncio.to_thread(sh.run, line)
        await asyncio.sleep(0.05)


async def until(pred, limit=5.0):
    end = time.monotonic() + limit
    while time.monotonic() < end and not pred():
        await asyncio.sleep(0.05)
    return pred()


async def test_three_real_failures_make_one_offer_with_a_plain_reason(world):
    det, host, offers, sh = world
    task = asyncio.create_task(host.run())
    try:
        await type_commands(sh, "fakectl 1", "ls /", "fakectl 2")
        assert offers == []  # two failures (and a command nobody allowed) are not a loop
        await type_commands(sh, "fakectl 1")
        assert await until(lambda: offers)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert len(offers) == 1 and offers[0].app == "workbench"
    assert offers[0].why == "In workbench I saw 3 failed commands of the same name."


async def test_a_success_in_between_means_no_offer(world):
    det, host, offers, sh = world
    task = asyncio.create_task(host.run())
    try:
        await type_commands(sh, "fakectl 1", "fakectl 1", "fakectl 0", "fakectl 1")
        await asyncio.sleep(1.5)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert offers == []


async def test_a_no_then_the_same_loop_stays_quiet_until_something_works(world):
    det, host, offers, sh = world
    task = asyncio.create_task(host.run())
    try:
        await type_commands(sh, "fakectl 1", "fakectl 1", "fakectl 1")
        assert await until(lambda: offers)
        det.answer(offers[0], "no")
        await type_commands(sh, "fakectl 1", "fakectl 1", "fakectl 1")
        await asyncio.sleep(1.5)
        assert len(offers) == 1  # same signal, same context, and the cooldown
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
