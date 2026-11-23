"""The Secret Service (libsecret) side of key storage (ADR-0014 §4, ADR-0018 `SecretStore`).

Runs under the system python3, which has PyGObject; the core venv does not. It is a tiny filter:
`python3 -m ya_bro.platform.secret_service get|set|clear|ping`. The key is read from stdin on `set`
and written to stdout on `get`, so it never sits in an argument list, an environment or a log.
Exit codes: 0 done, 1 nothing stored, 2 the Secret Service is not reachable or refused.
"""

from __future__ import annotations

import sys

SCHEMA_NAME = "de.yousri.YaBro.ApiKey"
ATTRS = {"service": "anthropic"}
LABEL = "Bro: Anthropic API key"

EXIT_OK, EXIT_MISSING, EXIT_UNAVAILABLE = 0, 1, 2


def _load():
    import gi

    gi.require_version("Secret", "1")
    from gi.repository import Secret

    schema = Secret.Schema.new(
        SCHEMA_NAME, Secret.SchemaFlags.NONE, {"service": Secret.SchemaAttributeType.STRING}
    )
    return Secret, schema


def run(verb: str, stdin=sys.stdin, stdout=sys.stdout) -> int:
    try:
        secret, schema = _load()
    except (ImportError, ValueError):
        return EXIT_UNAVAILABLE
    try:
        if verb == "ping":
            secret.Service.get_sync(secret.ServiceFlags.NONE, None)
            return EXIT_OK
        if verb == "get":
            value = secret.password_lookup_sync(schema, ATTRS, None)
            if not value:
                return EXIT_MISSING
            stdout.write(value)
            return EXIT_OK
        if verb == "set":
            value = stdin.read().strip()
            if not value:
                return EXIT_MISSING
            ok = secret.password_store_sync(
                schema, ATTRS, secret.COLLECTION_DEFAULT, LABEL, value, None
            )
            return EXIT_OK if ok else EXIT_UNAVAILABLE
        if verb == "clear":
            return EXIT_OK if secret.password_clear_sync(schema, ATTRS, None) else EXIT_MISSING
    except Exception:  # noqa: BLE001 - GLib.Error text can echo paths; say nothing, exit code only
        return EXIT_UNAVAILABLE
    return EXIT_UNAVAILABLE


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) == 2 else ""))
