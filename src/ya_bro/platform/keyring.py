"""Host side of the keyring: runs the Secret Service helper under the system python3.

The core venv has no PyGObject, so (like the GNOME bridge) the helper runs as a child of the system
python3 with the source tree on its path. The key travels over a pipe only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ya_bro.keystore import KeyStoreError
from ya_bro.platform import secret_service as helper

TIMEOUT = 20.0  # a locked keyring may show an unlock prompt and wait for the person


class KeyringError(KeyStoreError):
    """The keyring could not be used. The message never carries the key."""


class SecretServiceBackend:
    """`keystore.Backend` over libsecret (the GNOME keyring, KWallet's Secret Service, ...)."""

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self._env = env

    def _call(self, verb: str, stdin: str = "") -> tuple[int, str]:
        if self._env is None and "PYTEST_CURRENT_TEST" in os.environ:
            raise KeyringError("refusing to touch the real keyring from a test")
        py = shutil.which("python3", path="/usr/bin:/usr/local/bin")
        if not py:
            raise KeyringError("no system python3 with PyGObject (sudo apt install python3-gi)")
        env = {**(os.environ if self._env is None else self._env)}
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        try:
            r = subprocess.run(
                [py, "-m", "ya_bro.platform.secret_service", verb],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise KeyringError("the keyring did not answer in time (is it locked?)") from None
        except OSError as e:
            raise KeyringError(f"cannot start the keyring helper ({type(e).__name__})") from None
        if r.returncode == helper.EXIT_UNAVAILABLE:
            raise KeyringError("no Secret Service available (is a keyring running and unlocked?)")
        return r.returncode, r.stdout

    def available(self) -> bool:
        try:
            return self._call("ping")[0] == helper.EXIT_OK
        except KeyringError:
            return False

    def get(self) -> str | None:
        rc, out = self._call("get")
        return out.strip() or None if rc == helper.EXIT_OK else None

    def set(self, value: str) -> None:
        self._call("set", value)

    def clear(self) -> bool:
        return self._call("clear")[0] == helper.EXIT_OK
