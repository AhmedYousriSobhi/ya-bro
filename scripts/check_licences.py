#!/usr/bin/env python3
"""Licence compliance gate (ADR-0020 §2, §7). Exit 0 when clean, 1 on a violation.

Checks, in order:
  1. The project itself: pyproject says MIT, LICENSE is the MIT text, every shipped pack says MIT.
  2. Every package in the dependency closure (from uv.lock, so extras and dev tools too) is listed
     in docs/licences.toml, and its declared licence is allowed for its scope.
  3. Nothing in docs/licences.toml's forbidden names is in the closure.
  4. Installed packages' own metadata agrees with the policy (a GPL surprise is caught).
  5. src/ never imports a forbidden module (GPL and AGPL stay out of process).
Usage: scripts/check_licences.py [--markdown]
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERMISSIVE = {
    "mit", "bsd-2-clause", "bsd-3-clause", "apache-2.0", "isc", "psf-2.0", "python-2.0",
    "unlicense", "0bsd", "cc0-1.0", "zlib", "hpnd",
}  # fmt: skip
WEAK = ("lgpl", "mpl", "epl")
RANK = {"permissive": 0, "weak": 1, "strong": 2, "unknown": 3}
SHIPPED = ("runtime", "optional")
SCOPES = ("runtime", "optional", "dev", "tests-only")


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def category(token: str) -> str:
    t = token.strip().strip("()").lower()
    t = re.sub(r"\s+with\s+.*$", "", t)  # "GPL-2.0 WITH Classpath-exception-2.0"
    if t in PERMISSIVE:
        return "permissive"
    if t.startswith(WEAK):
        return "weak"
    if t.startswith(("gpl", "agpl")):
        return "strong"
    return "unknown"


def expression_category(expr: str) -> str:
    """The least restrictive way to satisfy an SPDX expression ("A OR B"), all of "A AND B"."""
    if not expr.strip():
        return "unknown"
    best = None
    for alt in re.split(r"\s+OR\s+", expr.strip(), flags=re.I):
        worst = max((category(p) for p in re.split(r"\s+AND\s+", alt, flags=re.I)), key=RANK.get)
        best = worst if best is None or RANK[worst] < RANK[best] else best
    return best or "unknown"


def metadata_category(dist: metadata.Distribution) -> str | None:
    """What an installed package's own metadata says, as a category; None when it says nothing."""
    md = dist.metadata
    declared = [md.get("License-Expression") or ""]
    text = " ".join([*declared, md.get("License") or "", *md.get_all("Classifier", [])])
    text = text.lower()
    if not text.strip():
        return None
    lgpl = "lgpl" in text or "lesser general public" in text
    rest = text.replace("lesser general public", "").replace("lgpl", "")
    if any(w in rest for w in ("agpl", "affero", "gpl", "general public license")):
        # A dual or multi licence that also offers a permissive one is fine.
        if declared[0]:
            return expression_category(declared[0])
        return "strong"
    if lgpl or "mozilla public" in text:
        return "weak"
    permissive = ("mit", "bsd", "apache", "isc", "python software")
    return "permissive" if any(w in text for w in permissive) else None


def closure(pyproject: dict, lock: dict) -> dict[str, str]:
    """name -> widest scope it is reachable from (runtime > optional > dev)."""
    deps = {norm(p["name"]): p for p in lock.get("package", [])}
    roots: dict[str, str] = {}

    def req_name(spec: str) -> str:
        return norm(re.split(r"[<>=!~;\[ ]", spec.strip(), maxsplit=1)[0])

    proj = pyproject["project"]
    for spec in proj.get("dependencies", []):
        roots[req_name(spec)] = "runtime"
    for specs in proj.get("optional-dependencies", {}).values():
        for spec in specs:
            roots.setdefault(req_name(spec), "optional")
    for specs in pyproject.get("dependency-groups", {}).values():
        for spec in specs:
            roots.setdefault(req_name(spec), "dev")
    order = {"runtime": 0, "optional": 1, "dev": 2}
    out: dict[str, str] = {}

    def visit(name: str, scope: str) -> None:
        if name in out and order[out[name]] <= order[scope]:
            return
        out[name] = scope
        for d in deps.get(name, {}).get("dependencies", []):
            visit(norm(d["name"]), scope)

    for name, scope in roots.items():
        visit(name, scope)
    out.pop(norm(proj["name"]), None)
    return out


def check_project(root: Path, errors: list[str]) -> None:
    proj = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    if proj.get("license") != "MIT":
        errors.append(f"pyproject.toml: license is {proj.get('license')!r}, the project is MIT")
    lic = root / "LICENSE"
    if not lic.is_file() or not lic.read_text().lstrip().startswith("MIT License"):
        errors.append("LICENSE: missing, or not the MIT text")
    if "LICENSE" not in proj.get("license-files", []):
        errors.append("pyproject.toml: license-files must list LICENSE")
    for pack in sorted((root / "packs").glob("*/pack.toml")):
        lic_id = tomllib.loads(pack.read_text()).get("pack", {}).get("license")
        if lic_id != "MIT":
            errors.append(
                f'{pack.parent.name}: shipped packs must say license = "MIT" (is {lic_id!r})'
            )


def check_closure(root: Path, errors: list[str]) -> list[tuple[str, str, str, str]]:
    policy = tomllib.loads((root / "docs" / "licences.toml").read_text())
    pkgs = policy.get("packages", {})
    forbidden = {norm(n) for n in policy.get("forbidden", {}).get("names", [])}
    pyproject = tomllib.loads((root / "pyproject.toml").read_text())
    lock = tomllib.loads((root / "uv.lock").read_text())
    rows = []
    for name, scope in sorted(closure(pyproject, lock).items()):
        entry = pkgs.get(name)
        if entry is None:
            errors.append(
                f"{name} ({scope}): not in docs/licences.toml; read its licence and add it"
            )
            continue
        declared, declared_scope = entry.get("license", ""), entry.get("scope", "")
        if declared_scope not in SCOPES:
            errors.append(f"{name}: scope must be one of {', '.join(SCOPES)}")
            continue
        cat = expression_category(declared)
        shipped = scope in SHIPPED or declared_scope in SHIPPED
        if cat == "unknown":
            errors.append(f"{name}: licence {declared!r} is not one this gate recognises")
        elif cat == "strong" and declared_scope != "tests-only":
            errors.append(
                f"{name} ({scope}): {declared} is strong copyleft; only 'tests-only' may be"
            )
        if shipped and name in forbidden:
            errors.append(f"{name}: forbidden in anything that ships (ADR-0020 §2)")
        if scope in SHIPPED and declared_scope == "tests-only":
            errors.append(f"{name}: marked tests-only but reachable at runtime")
        try:
            seen = metadata_category(metadata.distribution(name))
        except metadata.PackageNotFoundError:
            seen = None
        if seen is not None and RANK[seen] > RANK[cat]:
            errors.append(f"{name}: installed metadata says {seen}, docs/licences.toml says {cat}")
        rows.append((name, scope, declared, cat))
    return rows


def check_sources(root: Path, errors: list[str]) -> None:
    policy = tomllib.loads((root / "docs" / "licences.toml").read_text())
    banned = {norm(m) for m in policy.get("forbidden", {}).get("modules", [])}
    for path in sorted((root / "src").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module]
            for n in names:
                if norm(n.split(".")[0]) in banned:
                    errors.append(f"{path.relative_to(root)}:{node.lineno}: imports {n} (copyleft)")


def run(root: Path = ROOT) -> tuple[list[str], list[tuple[str, str, str, str]]]:
    errors: list[str] = []
    check_project(root, errors)
    rows = check_closure(root, errors)
    check_sources(root, errors)
    return errors, rows


def markdown(rows) -> str:
    lines = ["| Package | Reached from | Licence | Class |", "|---|---|---|---|"]
    lines += [f"| {n} | {s} | {lic} | {c} |" for n, s, lic, c in rows]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    errors, rows = run()
    if "--markdown" in argv:
        print(markdown(rows))
        return 0
    for n, s, lic, c in rows:
        print(f"  {n:<18} {s:<9} {lic}  [{c}]")
    if errors:
        print(f"\nLICENCE GATE FAILED ({len(errors)}):")
        print("\n".join(f"  - {e}" for e in errors))
        return 1
    print(f"licence gate: ok ({len(rows)} packages, project and packs are MIT, src/ is clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
