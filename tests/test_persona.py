import asyncio
import re

import pytest

from tests.fakes import FakeCompositorBridge, FakeOverlay, FakePerception
from ya_bro import cli, config, persona
from ya_bro.persona import FSI, PDI, Persona, PersonaError, detect_locale, is_rtl
from ya_bro.policy import ShowMePolicy
from ya_bro.steps import StepLoop, Timing
from ya_bro.tone import Tone
from ya_bro.types import ElementRef, Expect, Plan, Rect, Risk, Step, WindowInfo

DATA = persona.load()
FACTS = {"name": "Save", "want": "7", "got": "5", "why": "Because.", "app": "GIMP"}
NO_GOT = {**FACTS, "got": ""}
LOCALES = ("en", "ar")


def texts_at(moment, locale, *levels):
    return {ln.text for ln in DATA.lines[locale][moment] if ln.humour in levels}


def formatted(moment, locale, facts, levels):
    """Every rendering of the lines at these humour levels, so we can tell which one was chosen."""
    p = Persona(locale=locale)
    out = set()
    for ln in DATA.lines[locale][moment]:
        if ln.humour in levels and ln.fits(facts):
            out.add(p._fill(ln, facts, locale))
    return out


# ---- the shipped data ---------------------------------------------------------------------------


def test_the_shipped_persona_is_sound_and_covers_every_moment_in_both_languages():
    assert persona.lint() == []
    for loc in LOCALES:
        assert set(DATA.lines[loc]) == set(DATA.moments)
    assert (
        len(DATA.moments) >= 14
        and sum(len(v) for loc in DATA.lines.values() for v in loc.values()) >= 150
    )


@pytest.mark.parametrize("loc", LOCALES)
def test_no_line_exceeds_its_moments_humour_ceiling(loc):
    for name, lines in DATA.lines[loc].items():
        assert all(ln.humour <= DATA.moments[name].max_humour for ln in lines), name


def test_the_style_guide_carries_the_rules_the_brain_must_follow():
    text = persona.style_guide()
    assert len(text) < 1500
    for must in ("140", "bro", "humour", "never", "risky", "Arabic"):
        assert must.lower() in text.lower(), must


# ---- where humour is allowed (ADR-0013 section 3) ----------------------------------------------


@pytest.mark.parametrize("loc", LOCALES)
@pytest.mark.parametrize("moment", ["cant_find", "unsure", "error_recovered", "risk_confirm"])
def test_no_humour_in_errors_uncertainty_recovery_or_risk_at_any_setting(loc, moment):
    plain = formatted(moment, loc, FACTS, (0,))
    for humour in range(4):
        for frustrated in (False, True):
            p = Persona(humour=humour, locale=loc)
            p.frustrated = frustrated
            for _ in range(6):
                assert p.say(moment, **FACTS) in plain


@pytest.mark.parametrize("loc", LOCALES)
def test_a_sensitive_step_silences_all_humour(loc):
    p = Persona(humour=3, locale=loc)
    p.sensitive = True
    for moment in ("mismatch", "offer_stuck", "task_done", "still_here", "pre_done"):
        for _ in range(4):
            assert p.say(moment, **FACTS) in formatted(moment, loc, FACTS, (0,))
    p.sensitive = False
    assert p.effective_humour("mismatch") == 3


def test_the_setting_is_a_ceiling_per_moment():
    for humour in range(4):
        for moment, spec in DATA.moments.items():
            if spec.max_humour == 0:
                continue
            allowed = formatted(
                moment, "en", FACTS, tuple(range(0, min(humour, spec.max_humour) + 1))
            )
            p = Persona(humour=humour)
            for _ in range(10):
                assert p.say(moment, **FACTS) in allowed, (humour, moment)


def test_humour_zero_is_always_the_plain_line():
    p = Persona(humour=0)
    for moment in DATA.moments:
        assert p.say(moment, **FACTS) in formatted(moment, "en", FACTS, (0,))


def test_the_deterministic_first_line_is_the_one_the_step_loop_always_had():
    assert "I warned you" in Persona(humour=1).say("mismatch", want="7", got="5")
    assert Tone(1).done() == "Done, bro. Told you it'd be easy."
    assert Tone(0).done() == "That's all the steps."
    assert Tone(0).why_mismatch("7", "", "").startswith("The screen shows something else")
    assert Tone(1).not_yet().startswith("Nice try, bro")


def test_frustration_drops_humour_one_level_and_progress_restores_it():
    p = Persona(humour=3)
    assert p.effective_humour("mismatch") == 3
    for _ in range(3):
        p.note_mismatch()
    assert p.frustrated and p.effective_humour("mismatch") == 2
    p.note_progress()
    assert not p.frustrated and p.effective_humour("mismatch") == 3
    q = Persona(humour=1)
    q.frustrated = True
    assert q.effective_humour("mismatch") == 0 and Tone(1).can_tease() is not False
    p.begin_task()
    assert p._mismatches == 0


def test_less_chatty_mutes_optional_moments_and_all_humour():
    p = Persona(humour=3, less_chatty=True)
    assert p.say("greeting") == "" and p.say("step_done") == ""
    for moment in ("task_done", "mismatch", "offer_stuck"):
        assert p.say(moment, **FACTS) in formatted(moment, "en", FACTS, (0,))
    assert Persona(humour=3).say("greeting") != ""


# ---- "bro" once per task, recency, rotation -----------------------------------------------------


def says_bro(text):
    return bool(re.search(r"\bbro\b", text, re.I)) or "برو" in text


def test_bro_is_said_at_most_once_per_task():
    moments = ("greeting", "offer_stuck", "mismatch", "still_here", "not_yet", "task_done")
    for loc in LOCALES:
        p = Persona(humour=3, locale=loc)
        total = 0
        for _task in range(3):
            p.begin_task()
            out = [p.say(m, **FACTS) for m in moments * 3]
            assert sum(says_bro(t) for t in out) <= 1, out
            total += sum(says_bro(t) for t in out)
        assert total >= 2  # it is not banned, only rationed: it comes back in the next task


def test_a_line_does_not_repeat_while_an_unused_one_exists():
    p = Persona(humour=3)
    pool = formatted("mismatch", "en", FACTS, (1, 2, 3))
    bro_lines = [ln for ln in DATA.lines["en"]["mismatch"] if ln.bro and ln.fits(FACTS)]
    usable = len(pool) - (len(bro_lines) - 1)  # after the first "bro" the rest are set aside
    seen = [p.say("mismatch", **FACTS) for _ in range(usable)]
    assert len(set(seen)) == usable  # every usable variant once before any repeats
    q = Persona(humour=1)
    assert len({q.say("offer_stuck", **FACTS) for _ in range(3)}) == 3


def test_facts_pick_the_variant_that_fits():
    with_got = Persona(humour=1).say("mismatch", want="7", got="5")
    without = Persona(humour=1).say("mismatch", want="7", got="")
    assert "5" in with_got and "5" not in without and "7" in without
    assert "Because." in Persona(humour=0).say("why_mismatch", want="7", got="5", why="Because.")
    with pytest.raises(PersonaError):
        Persona().say("mismatch", nonsense="x")
    with pytest.raises(PersonaError):
        Persona().say("no_such_moment")


# ---- languages ---------------------------------------------------------------------------------


def test_arabic_lines_are_used_and_ui_names_are_isolated_for_bidi():
    p = Persona(humour=0, locale="ar")
    line = p.say("cant_find", name="Save")
    assert detect_locale(line) == "ar" and f"{FSI}Save{PDI}" in line
    assert "«" in line and "»" in line
    en = Persona(humour=0, locale="en").say("cant_find", name="Save")
    assert FSI not in en and "“Save”" in en


def test_the_bro_follows_the_users_language():
    p = Persona(humour=0)
    assert p.locale == "en"
    assert p.follow("إزاي أعمل تصدير؟") == "ar" and p.locale == "ar"
    assert detect_locale("how do I export?") == "en"
    assert p.follow("1234 !!") == "ar"  # nothing to go on: stay as it was
    assert p.follow("export as PNG please") == "en"
    assert detect_locale("افتح File menu") == "ar"  # mostly Arabic wins; the English is a name
    assert detect_locale("") == "en" and detect_locale("", "ar") == "ar"
    assert is_rtl("مرحبا") and not is_rtl("hello") and Persona(locale="xx").locale == "en"


# ---- generated lines: the safety filter ----------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Want a hand with this? I can walk you through it.",
        "تحب أساعدك في الخطوة دي؟",
        "Nice. Next.\nOne more.",
    ],
)
def test_vet_accepts_ordinary_short_lines(text):
    out = Persona().vet(text)
    assert out and "\n" not in out


@pytest.mark.parametrize(
    "text",
    [
        "x" * 141,
        "",
        "See https://example.com for more",
        "Run `rm -rf ~` to fix it",
        "Funny joke about death",
        "Tell me your password and I will help",
        "عايز فلوس؟",
        "نكتة عن الموت",
        "Click Delete now to continue",
        "Just send it, no need to check",
        "دوس على حذف الآن",
    ],
)
def test_vet_rejects_banned_topics_links_commands_and_risky_instructions(text):
    assert Persona().vet(text) is None


def test_a_risky_instruction_is_allowed_only_when_the_approved_step_is_risky():
    line = "Press Delete when you are ready."
    assert Persona().vet(line) is None and Persona().vet(line, approved_risk=True) == line


def test_generated_lines_fall_back_to_the_template_and_never_replace_a_sensitive_moment():
    p = Persona(humour=1)
    assert (
        p.generated_or("Fancy a hand with GIMP?", "offer_stuck", app="GIMP")
        == "Fancy a hand with GIMP?"
    )
    bad = p.generated_or("Delete everything and send it", "offer_stuck", app="GIMP")
    assert bad in formatted("offer_stuck", "en", {"app": "GIMP"}, (0, 1))
    risky = p.generated_or("Sure, go ahead and click it!", "risk_confirm", name="Pay")
    assert risky in formatted("risk_confirm", "en", {"name": "Pay"}, (0,))


# ---- through the step loop -----------------------------------------------------------------------

APP = "org.example.App"
BUTTON = ElementRef(APP, "button", "Delete")
DISPLAY = ElementRef(APP, "text", "display")
WIN = WindowInfo("1", APP, "w", Rect(0, 0, 800, 600), focused=True)


async def settle(n=8):
    for _ in range(n):
        await asyncio.sleep(0.02)


async def test_a_risky_step_is_never_joked_about_even_after_a_wrong_action_at_full_humour():
    perception = FakePerception(
        {BUTTON: Rect(1, 1, 5, 5), DISPLAY: Rect(0, 0, 9, 9)}, {DISPLAY: ""}
    )
    overlay = FakeOverlay()
    tone = Tone(3)
    loop = StepLoop(
        perception, overlay, FakeCompositorBridge([WIN]), ShowMePolicy(),
        Timing(poll=0.01, settle=0.05, nudge=30.0), tone=tone,
    )  # fmt: skip
    step = Step(
        "x",
        "Delete the draft.",
        BUTTON,
        risk=Risk.R3,
        expect=Expect("text", "display", text="gone"),
    )
    task = asyncio.create_task(loop.run(Plan("g", [step]), APP))
    await settle()
    shown = overlay.calls[-1][2]
    assert "yourself" in shown or "yours to press" in shown or "your call" in shown
    perception.texts[DISPLAY] = "oops"
    await asyncio.sleep(0.3)
    assert overlay.moods[-1] != "teasing"
    plain = formatted("mismatch", "en", {"want": "gone", "got": "oops"}, (0,)).pop()
    assert overlay.calls[-1][2] == f"(1/1) {plain}"
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert tone.persona.sensitive is False  # and the flag does not leak to the next step


async def test_the_loop_speaks_arabic_when_asked_to():
    perception = FakePerception({BUTTON: Rect(1, 1, 5, 5)})
    overlay = FakeOverlay()
    loop = StepLoop(
        perception, overlay, FakeCompositorBridge([WIN]), ShowMePolicy(),
        Timing(poll=0.01, nudge=30.0), tone=Tone(0, "ar"),
    )  # fmt: skip
    missing = Step("x", "اضغط.", ElementRef(APP, "button", "Nope"))
    task = asyncio.create_task(loop.run(Plan("g", [missing]), APP))
    await settle()
    assert detect_locale(overlay.calls[0][2]) == "ar" and FSI in overlay.calls[0][2]
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


# ---- config and the command ---------------------------------------------------------------------


def test_config_reads_language_and_less_chatty_and_rejects_bad_values(tmp_path):
    (tmp_path / "config.toml").write_text('humour = 2\nlanguage = "ar"\nless_chatty = true\n')
    cfg = config.load(config_dir=tmp_path)
    assert (cfg.humour, cfg.language, cfg.less_chatty) == (2, "ar", True)
    (tmp_path / "config.toml").write_text('language = "fr"\nless_chatty = "yes"\n')
    cfg = config.load(config_dir=tmp_path)
    assert (cfg.language, cfg.less_chatty) == ("auto", False)


def test_broctl_persona(capsys):
    assert cli.main(["persona", "lint"]) == 0 and "persona: ok" in capsys.readouterr().out
    assert cli.main(["persona", "say", "offer_stuck", "--humour", "1", "--fact", "app=GIMP"]) == 0
    assert capsys.readouterr().out.strip() in formatted(
        "offer_stuck", "en", {"app": "GIMP"}, (0, 1)
    )
    assert cli.main(["persona", "say", "greeting", "--humour", "3", "--less-chatty"]) == 0
    assert capsys.readouterr().out.strip() == ""
    assert cli.main(["persona", "say", "nope"]) == 1
    assert cli.main(["persona", "list", "--lang", "ar"]) == 0
    out = capsys.readouterr().out
    assert "[mismatch] max humour 3" in out and "[risk_confirm] max humour 0, sensitive" in out
    assert cli.main(["persona", "style"]) == 0 and "You are Bro" in capsys.readouterr().out


def test_lint_catches_broken_data(monkeypatch):
    from dataclasses import replace

    from ya_bro.persona import Line

    ar = dict(DATA.lines["en"])
    ar["cant_find"] = (
        *DATA.lines["en"]["cant_find"],
        Line("cant_find", 0, "I die laughing {name}"),
    )
    ar["task_done"] = tuple(ln for ln in DATA.lines["en"]["task_done"] if ln.humour == 0)
    broken = replace(DATA, lines={**DATA.lines, "en": ar})
    monkeypatch.setattr(persona, "load", lambda: broken)
    found = persona.lint()
    assert any("banned word" in p for p in found) and any(
        "fewer than 3 playful" in p for p in found
    )
