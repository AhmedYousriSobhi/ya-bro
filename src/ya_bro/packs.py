"""App knowledge packs (ADR-0012, format v1 in ADR-0027): data about one app, never code.

packs/<id>/
  pack.toml     id, name, version, trust, locales, [match], [sources]
  knowledge.md  vocabulary, mental model, common mistakes (kept small: it rides in every prompt)
  tasks/*.toml  Show-me plans (the plans.py format) for common goals
  [[element]]   in pack.toml: role, name ("" = any), risk 0-3 and/or secret = true
  signals.toml  [weights] and [counts.signal] (count, window): bounded tuning of the detector
  fixits.toml   [[fixit]] code, meaning, suggest (a command to offer) or hint (plain words)
The core only reads packs; nothing in one is imported or executed.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path

from ya_bro import dirs, plans
from ya_bro.struggle import Signal
from ya_bro.types import Risk

PACK_FORMAT = 1
MAX_KNOWLEDGE_CHARS = 16_000  # about 4k tokens, ADR-0012 §4
TRUST = ("data-only", "hooks")
MATCH_KEYS = ("desktop_ids", "window_classes", "argv0", "urls")
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
_LICENCE = re.compile(r"[A-Za-z0-9.+() -]{1,80}")
_CODE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+")
_VERSION = re.compile(r"\d+\.\d+\.\d+")

SHIPPED = Path(__file__).resolve().parents[2] / "packs"


class PackError(ValueError):
    pass


@dataclass(frozen=True)
class Fixit:
    """What an app's error code means. `suggest` is only ever offered, never run (R2, ADR-0009)."""

    code: str
    meaning: str
    suggest: str = ""
    hint: str = ""


@dataclass(frozen=True)
class PackElement:
    """What the pack knows about an element: a floor for its risk, and whether it holds a secret."""

    role: str
    name: str = ""
    risk: Risk = Risk.R0
    secret: bool = False

    def covers(self, role: str, name: str) -> bool:
        return role.lower() == self.role.lower() and (
            not self.name or name.lower() == self.name.lower()
        )


@dataclass(frozen=True)
class Pack:
    id: str
    name: str
    version: str
    root: Path
    trust: str = "data-only"
    locales: tuple[str, ...] = ("en",)
    match: dict[str, tuple[str, ...]] = field(default_factory=dict)
    sources: dict[str, tuple[str, ...]] = field(default_factory=dict)
    license: str = ""
    knowledge: str = ""
    tasks: dict[str, Path] = field(default_factory=dict)
    fixits: dict[str, Fixit] = field(default_factory=dict)
    elements: tuple[PackElement, ...] = ()
    signal_weights: dict[str, float] = field(default_factory=dict)
    signal_counts: dict[str, tuple[int, float]] = field(default_factory=dict)

    def risk_of(self, role: str, name: str) -> Risk:
        return Risk(max((e.risk for e in self.elements if e.covers(role, name)), default=Risk.R0))

    def is_secret(self, role: str, name: str) -> bool:
        return any(e.secret and e.covers(role, name) for e in self.elements)

    def matches(
        self, app_id: str = "", window_class: str = "", argv0: str = "", url: str = ""
    ) -> bool:
        """Exact matchers only; an empty argument never matches."""
        m = self.match
        return bool(
            (app_id and app_id in m.get("desktop_ids", ()))
            or (
                window_class
                and window_class.lower() in (c.lower() for c in m.get("window_classes", ()))
            )
            or (argv0 and argv0 in m.get("argv0", ()))
            or (url and any(fnmatchcase(url, p) for p in m.get("urls", ())))
        )


def _strings(table: dict, key: str, where: str, *, allow_str: bool = False) -> tuple[str, ...]:
    value = table.get(key, ())
    if allow_str and isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) and v for v in value):
        raise PackError(f"{where}: {key} must be a list of non-empty strings")
    return tuple(value)


def _fixits(root: Path, argv0: tuple[str, ...]) -> dict[str, Fixit]:
    path = root / "fixits.toml"
    if not path.is_file():
        return {}
    try:
        rows = tomllib.loads(path.read_text()).get("fixit", [])
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise PackError(f"cannot read fixits.toml: {e}") from e
    commands = {Path(a).name for a in argv0}
    out: dict[str, Fixit] = {}
    for i, row in enumerate(rows, 1):
        where = f"fixits.toml entry {i}"
        fields = {k: row.get(k, "") for k in ("code", "meaning", "suggest", "hint")}
        if not all(isinstance(v, str) for v in fields.values()):
            raise PackError(f"{where}: values must be strings")
        if not _CODE.fullmatch(fields["code"]) or not fields["meaning"]:
            raise PackError(f"{where}: needs a code like WB-REFUSED-MEMORY and a meaning")
        if fields["code"] in out:
            raise PackError(f"{where}: duplicate code {fields['code']}")
        first = fields["suggest"].split(maxsplit=1)[:1]
        if first and Path(first[0]).name not in commands:
            raise PackError(f"{where}: suggest must run one of the pack's own commands")
        out[fields["code"]] = Fixit(**fields)
    return out


def _elements(rows: object) -> tuple[PackElement, ...]:
    if not isinstance(rows, list):
        raise PackError("element must be a list of [[element]] tables")
    out = []
    for i, row in enumerate(rows, 1):
        where = f"element {i}"
        role, name = row.get("role"), row.get("name", "")
        if not isinstance(role, str) or not role or not isinstance(name, str):
            raise PackError(f"{where}: needs a role (and a name, or none for any)")
        secret = row.get("secret", False)
        if not isinstance(secret, bool):
            raise PackError(f"{where}: secret must be true or false")
        try:
            risk = Risk(row.get("risk", 0))
        except ValueError as e:
            raise PackError(f"{where}: risk must be 0 to 3") from e
        if not secret and risk is Risk.R0:
            raise PackError(f"{where}: needs a risk above 0 or secret = true")
        out.append(PackElement(role, name, risk, secret))
    return tuple(out)


def _signals(root: Path) -> tuple[dict[str, float], dict[str, tuple[int, float]]]:
    path = root / "signals.toml"
    if not path.is_file():
        return {}, {}
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise PackError(f"cannot read signals.toml: {e}") from e
    names = {s.value for s in Signal}
    weights: dict[str, float] = {}
    for name, w in data.get("weights", {}).items():
        if name not in names or isinstance(w, bool) or not isinstance(w, (int, float)):
            raise PackError(f"signals.toml: weights.{name} must be a number for a known signal")
        if not 0 <= w <= 3:
            raise PackError(f"signals.toml: weights.{name} must be 0 to 3")
        weights[name] = float(w)
    counts: dict[str, tuple[int, float]] = {}
    for name, row in data.get("counts", {}).items():
        count, window = (
            row.get("count") if isinstance(row, dict) else None,
            row.get("window") if isinstance(row, dict) else None,
        )
        ok = isinstance(count, int) and not isinstance(count, bool) and 2 <= count <= 50
        ok = ok and isinstance(window, (int, float)) and 1 <= window <= 3600
        if name not in names or not ok:
            raise PackError(
                f"signals.toml: counts.{name} needs a count of 2 to 50 and a window of 1 to 3600 s"
            )
        counts[name] = (count, float(window))
    return weights, counts


def load(root: Path) -> Pack:
    """One pack directory. Raises PackError on anything malformed, tasks included."""
    root = Path(root)
    try:
        data = tomllib.loads((root / "pack.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise PackError(f"cannot read {root}/pack.toml: {e}") from e
    head = data.get("pack", {})
    pid, name, version = head.get("id"), head.get("name"), head.get("version")
    if not isinstance(pid, str) or not _ID.fullmatch(pid):
        raise PackError("pack.id must be a-z, 0-9, - and _ (max 32)")
    if pid != root.name:
        raise PackError(f"pack.id {pid!r} must match its directory name {root.name!r}")
    if not isinstance(name, str) or not name:
        raise PackError("pack.name is required")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise PackError("pack.version must look like 1.2.3")
    if head.get("format", PACK_FORMAT) != PACK_FORMAT:
        raise PackError(f"pack.format must be {PACK_FORMAT}")
    trust = head.get("trust", "data-only")
    if trust not in TRUST:
        raise PackError(f"pack.trust must be one of {', '.join(TRUST)}")
    locales = _strings(head, "locales", "pack") or ("en",)
    licence = head.get("license", "")
    if not isinstance(licence, str) or (licence and not _LICENCE.fullmatch(licence)):
        raise PackError("pack.license must be an SPDX identifier or expression, like MIT")

    raw_match = data.get("match", {})
    unknown = set(raw_match) - set(MATCH_KEYS)
    if unknown:
        raise PackError(f"match: unknown matcher {sorted(unknown)[0]!r}")
    match = {k: _strings(raw_match, k, "match") for k in raw_match}
    if not any(match.values()):
        raise PackError("match: a pack needs at least one matcher")
    sources = {
        k: _strings(data.get("sources", {}), k, "sources", allow_str=True)
        for k in data.get("sources", {})
    }

    knowledge = ""
    kpath = root / "knowledge.md"
    if kpath.is_file():
        knowledge = kpath.read_text()
        if len(knowledge) > MAX_KNOWLEDGE_CHARS:
            raise PackError(f"knowledge.md is over {MAX_KNOWLEDGE_CHARS} characters")

    tasks = {}
    for path in sorted((root / "tasks").glob("*.toml")):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise PackError(f"tasks/{path.name}: links out of the pack are not allowed")
        try:
            plans.load(path)
        except plans.PlanError as e:
            raise PackError(f"tasks/{path.name}: {e}") from e
        tasks[path.stem] = path
    fixits = _fixits(root, match.get("argv0", ()))
    elements = _elements(data.get("element", []))
    weights, counts = _signals(root)
    return Pack(
        pid, name, version, root, trust, locales, match, sources, licence, knowledge, tasks,
        fixits, elements, weights, counts,
    )  # fmt: skip


def roots(extra: list[Path] | None = None) -> list[Path]:
    """Where packs are searched: the shipped ones, then the user's (a user pack wins on id)."""
    return [SHIPPED, dirs.data_dir() / "packs", *(extra or [])]


def load_all(search: list[Path] | None = None) -> tuple[list[Pack], list[str]]:
    """(valid packs sorted by id, problems). A broken pack is skipped, never half-loaded."""
    found: dict[str, Pack] = {}
    problems: list[str] = []
    for base in search if search is not None else roots():
        for d in sorted(base.glob("*/pack.toml")) if base.is_dir() else []:
            try:
                pack = load(d.parent)
            except (PackError, OSError, UnicodeDecodeError) as e:
                problems.append(f"{d.parent}: {e}")
                continue
            found[pack.id] = pack
    return sorted(found.values(), key=lambda p: p.id), problems


def resolve(packs: list[Pack], **target: str) -> list[Pack]:
    """Packs that match this app (toolkit packs and the generic fallback come later)."""
    return [p for p in packs if p.matches(**target)]
