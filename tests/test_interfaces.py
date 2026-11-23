import pytest

from tests import fakes
from ya_bro import interfaces as i

PAIRS = [
    (i.Perception, fakes.FakePerception),
    (i.CompositorBridge, fakes.FakeCompositorBridge),
    (i.Overlay, fakes.FakeOverlay),
    (i.Actuator, fakes.FakeActuator),
    (i.Capture, fakes.FakeCapture),
    (i.IdleSource, fakes.FakeIdleSource),
    (i.UiEventSource, fakes.FakeUiEvents),
    (i.Hotkeys, fakes.FakeHotkeys),
    (i.ShellHook, fakes.FakeShellHook),
    (i.Voice, fakes.FakeVoice),
    (i.SecretStore, fakes.FakeSecretStore),
    (i.Policy, fakes.FakePolicy),
    (i.Brain, fakes.FakeBrain),
]


@pytest.mark.parametrize(("protocol", "fake"), PAIRS, ids=lambda p: p.__name__)
def test_fake_satisfies_protocol(protocol, fake):
    assert isinstance(fake(), protocol)
