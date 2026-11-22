import pytest

from ya_bro import plans
from ya_bro.types import Risk

GOOD = """
[plan]
goal = "create a job"
app = "org.example.App"
keywords = ["create", "job"]
[[step]]
narration = "Click Create."
target = {role = "button", name = "Create"}
expect = {role = "button", name = "Confirm"}
why = "Starts the wizard."
risk = 1
[[step]]
narration = "Done."
"""


def write(tmp_path, text, name="p.toml"):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_load_builds_steps(tmp_path):
    plan, app, kws = plans.load(write(tmp_path, GOOD))
    assert app == "org.example.App" and kws == ["create", "job"]
    s = plan.steps[0]
    assert s.target.name == "Create" and s.target.app_id == app
    assert s.expect.name == "Confirm" and s.expect.appears and s.risk is Risk.R1
    assert plan.steps[1].target is None


def test_app_override_wins(tmp_path):
    plan, app, _ = plans.load(write(tmp_path, GOOD), "other.App")
    assert app == "other.App" and plan.steps[0].target.app_id == "other.App"


@pytest.mark.parametrize(
    "text",
    [
        "not toml [[[",
        '[plan]\ngoal = ""\n[[step]]\nnarration = "x"',
        '[plan]\ngoal = "g"',
        '[plan]\ngoal = "g"\n[[step]]\nintent = "x"',
        '[plan]\ngoal = "g"\n[[step]]\nnarration = "x"\ntarget = {role = "button"}',
        '[plan]\ngoal = "g"\n[[step]]\nnarration = "x"\nrisk = 9',
    ],
)
def test_malformed_plans_are_refused(tmp_path, text):
    with pytest.raises(plans.PlanError):
        plans.load(write(tmp_path, text))


async def test_scripted_brain_picks_the_best_keyword_match(tmp_path):
    a = write(tmp_path, GOOD, "a.toml")
    b = write(
        tmp_path,
        GOOD.replace('"create a job"', '"delete"').replace('["create", "job"]', '["delete"]'),
        "b.toml",
    )
    brain = plans.ScriptedBrain([a, b])
    assert (await brain.plan("please delete it", "x")).goal == "delete"
    assert (await brain.plan("create a job", "x")).goal == "create a job"
    with pytest.raises(plans.PlanError):
        await brain.plan("fly to the moon", "x")
