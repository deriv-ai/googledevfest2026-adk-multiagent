"""Upgrade every package trivy reports as fixable, then report what was left.

    .venv/bin/python scripts/trivy_patch.py        # or: make trivy-patch

trivy scans both lockfiles (uv.lock and web/package-lock.json). For every
vulnerable package with a published fix, this script takes the lowest fixed
version above the installed one and tries, in order:

  Python (uv.lock)
    1. ``uv lock --upgrade-package <pkg>``         enough when nothing caps it
    2. direct dependency pinned with ``==``     -> pin rewritten to ``==<fix>``
       anything else                           -> ``<pkg>>=<fix>`` added to
                                                  [tool.uv] constraint-dependencies

  npm (web/)
    direct dependency     -> ``npm install --save-exact <pkg>@<fix>``
    transitive dependency -> ``npm update <pkg>``, else an ``overrides`` entry

Every attempt is checked afterwards and ROLLED BACK (pyproject.toml, uv.lock,
package.json, package-lock.json restored) when it fails, when the package is
still below the fix, or when it only "worked" by DOWNGRADING some other
package (e.g. forcing a new filelock made the resolver fall back to an older
litellm). Rolled-back packages are reported with the reason, so a human can
decide (wait for upstream, accept the downgrade by hand, or add a justified
entry to .trivyignore).

Environment: TRIVY_SEVERITY (default HIGH,CRITICAL), UV (path to uv).
Exit code: 0 = everything fixable was upgraded, 1 = something was left behind.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

try:
    from packaging.version import InvalidVersion, Version
except ImportError:  # pragma: no cover - packaging ships with the project's deps
    Version = None  # type: ignore[assignment]
    InvalidVersion = ValueError  # type: ignore[assignment,misc]

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
PYPROJECT = ROOT / "pyproject.toml"
UV_LOCK = ROOT / "uv.lock"
PKG_JSON = WEB / "package.json"
PKG_LOCK = WEB / "package-lock.json"
SEVERITY = os.environ.get("TRIVY_SEVERITY", "HIGH,CRITICAL")

# Package names end up as command-line arguments (no shell, but a name that
# starts with "-" would be read as an option). Only accept well-formed names.
PY_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
NPM_NAME = re.compile(r"^(?:@[a-z0-9~][a-z0-9._~-]*/)?[a-z0-9~][a-z0-9._~-]*$")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def vkey(v: str):
    """Sortable version key (PEP 440 when possible, numeric tuple otherwise)."""
    if Version is not None:
        try:
            return (0, Version(v))
        except InvalidVersion:
            pass
    return (1, tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-+]", v)))


def run(cmd: list[str], cwd: Path = ROOT) -> bool:
    print("  $", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        out = "\n".join(p for p in (proc.stdout.strip(), proc.stderr.strip()) if p)
        print("    failed (exit %d):\n%s" % (proc.returncode, "\n".join("    | " + l for l in out.splitlines()[-25:])))
    return proc.returncode == 0


def uv_bin() -> str:
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        sys.exit("uv not found: install it (https://docs.astral.sh/uv/) or set UV=/path/to/uv")
    return uv


class Snapshot:
    """Byte-exact copy of files, restorable after a failed attempt."""

    def __init__(self, *paths: Path):
        self.saved = {p: p.read_bytes() for p in paths if p.exists()}

    def restore(self) -> None:
        for p, data in self.saved.items():
            p.write_bytes(data)


@dataclass
class Finding:
    ecosystem: str  # "uv" | "npm"
    name: str
    installed: str
    fix: str
    ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# trivy
# ---------------------------------------------------------------------------
def scan() -> list[Finding]:
    cmd = ["trivy", "fs", "--scanners", "vuln", "--format", "json", "--quiet",
           "--severity", SEVERITY, "--ignore-unfixed",
           "--skip-dirs", "web/node_modules", "--skip-dirs", ".venv", "--skip-dirs", ".claude", "."]
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"trivy failed:\n{proc.stderr}")
    report = json.loads(proc.stdout or "{}")
    found: dict[tuple[str, str], Finding] = {}
    for result in report.get("Results") or []:
        eco = {"uv": "uv", "npm": "npm"}.get(result.get("Type", ""))
        if eco is None:
            continue
        for vuln in result.get("Vulnerabilities") or []:
            name, installed = vuln.get("PkgName", ""), vuln.get("InstalledVersion", "")
            fixes = [f.strip() for f in (vuln.get("FixedVersion") or "").split(",") if f.strip()]
            above = sorted((f for f in fixes if vkey(f) > vkey(installed)), key=vkey)
            if not above:
                continue
            f = found.setdefault((eco, name), Finding(eco, name, installed, above[0]))
            if vkey(above[0]) > vkey(f.fix):  # several CVEs: need the highest of their fixes
                f.fix = above[0]
            f.ids.append(vuln.get("VulnerabilityID", "?"))
    return list(found.values())


# ---------------------------------------------------------------------------
# Python / uv
# ---------------------------------------------------------------------------
def canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def uv_versions() -> dict[str, str]:
    data = tomllib.loads(UV_LOCK.read_text())
    return {canon(p["name"]): p["version"] for p in data.get("package", []) if "version" in p}


def direct_pin(name: str) -> str | None:
    """The exact `name==x` requirement string in [project].dependencies, if any."""
    deps = tomllib.loads(PYPROJECT.read_text()).get("project", {}).get("dependencies", [])
    for req in deps:
        m = re.match(r"^\s*([A-Za-z0-9._-]+)(\[[^\]]*\])?\s*==\s*[^;,\s]+", req)
        if m and canon(m.group(1)) == canon(name):
            return req
    return None


def add_constraint(name: str, fix: str) -> None:
    """Add/replace `name>=fix` in [tool.uv] constraint-dependencies (text edit, layout kept)."""
    text = PYPROJECT.read_text()
    entry = f'"{name}>={fix}"'
    cfg = tomllib.loads(text).get("tool", {}).get("uv", {})
    if "constraint-dependencies" in cfg:
        # drop an older constraint on the same package, then append the new one
        text = re.sub(rf'\s*"{re.escape(name)}\s*>=[^"]*",?', "", text)
        text = re.sub(r"(constraint-dependencies\s*=\s*\[)", rf"\1\n    {entry},", text, count=1)
    elif re.search(r"^\[tool\.uv\]\s*$", text, re.M):
        text = re.sub(r"^\[tool\.uv\]\s*$", f"[tool.uv]\nconstraint-dependencies = [\n    {entry},\n]", text, count=1, flags=re.M)
    else:
        text = text.rstrip() + (
            "\n\n[tool.uv]\n# Security floors for transitive deps (managed by scripts/trivy_patch.py)\n"
            f"constraint-dependencies = [\n    {entry},\n]\n"
        )
    tomllib.loads(text)  # never write an unparsable pyproject
    PYPROJECT.write_text(text)


def fix_python(f: Finding, uv: str) -> str | None:
    """Return None on success, else the reason it was rolled back."""
    snap = Snapshot(PYPROJECT, UV_LOCK)
    before = uv_versions()

    def check() -> str | None:
        after = uv_versions()
        now = after.get(canon(f.name))
        if now is None or vkey(now) < vkey(f.fix):
            return f"resolver kept {f.name} at {now} (< {f.fix})"
        downgrades = [f"{k} {v} -> {after[k]}" for k, v in before.items()
                      if k in after and vkey(after[k]) < vkey(v)]
        if downgrades:
            return "fix would downgrade: " + ", ".join(downgrades)
        return None

    if run([uv, "lock", "--upgrade-package", f.name]) and check() is None:
        return None
    snap.restore()
    pin = direct_pin(f.name)
    if pin:
        new = re.sub(r"==\s*[^;,\s]+", f"=={f.fix}", pin, count=1)
        PYPROJECT.write_text(PYPROJECT.read_text().replace(f'"{pin}"', f'"{new}"', 1))
    else:
        add_constraint(f.name, f.fix)
    reason = None if run([uv, "lock"]) else "uv lock failed (version conflict)"
    reason = reason or check()
    if reason:
        snap.restore()
    return reason


# ---------------------------------------------------------------------------
# npm
# ---------------------------------------------------------------------------
def npm_version(name: str) -> str | None:
    lock = json.loads(PKG_LOCK.read_text())
    return (lock.get("packages", {}).get(f"node_modules/{name}") or {}).get("version")


def npm_versions() -> dict[str, str]:
    lock = json.loads(PKG_LOCK.read_text())
    return {k: v.get("version", "") for k, v in lock.get("packages", {}).items() if k and v.get("version")}


def fix_npm(f: Finding) -> str | None:
    snap = Snapshot(PKG_JSON, PKG_LOCK)
    before = npm_versions()
    pkg = json.loads(PKG_JSON.read_text())
    direct = any(f.name in pkg.get(s, {}) for s in ("dependencies", "devDependencies"))

    def check() -> str | None:
        now = npm_version(f.name)
        if now is None or vkey(now) < vkey(f.fix):
            return f"{f.name} still at {now} (< {f.fix})"
        after = npm_versions()
        downgrades = [f"{k.removeprefix('node_modules/')} {v} -> {after[k]}" for k, v in before.items()
                      if k in after and vkey(after[k]) < vkey(v)]
        return ("fix would downgrade: " + ", ".join(downgrades[:8])) if downgrades else None

    if direct:
        ok = run(["npm", "install", "--save-exact", f"{f.name}@{f.fix}"], cwd=WEB)
    else:
        ok = run(["npm", "update", f.name], cwd=WEB) and check() is None
        if not ok:
            snap.restore()
            pkg = json.loads(PKG_JSON.read_text())
            pkg.setdefault("overrides", {})[f.name] = f"^{f.fix}"
            PKG_JSON.write_text(json.dumps(pkg, indent=2) + "\n")
            ok = run(["npm", "install"], cwd=WEB)
    reason = None if ok else "npm install failed (peer/version conflict)"
    reason = reason or check()
    if reason:
        snap.restore()
        run(["npm", "install", "--no-audit", "--no-fund"], cwd=WEB)  # put node_modules back in sync
    return reason


# ---------------------------------------------------------------------------
def main() -> int:
    findings = scan()
    if not findings:
        print("\ntrivy: no fixable %s vulnerabilities. Nothing to do." % SEVERITY)
        return 0
    uv = uv_bin() if any(f.ecosystem == "uv" for f in findings) else ""
    fixed, left = [], []
    for f in sorted(findings, key=lambda x: (x.ecosystem, x.name)):
        valid = (PY_NAME if f.ecosystem == "uv" else NPM_NAME).match(f.name)
        print(f"\n[{f.ecosystem}] {f.name} {f.installed} -> {f.fix}  ({', '.join(sorted(set(f.ids)))})")
        if not valid:
            left.append((f, "refusing unusual package name"))
            continue
        try:
            reason = fix_python(f, uv) if f.ecosystem == "uv" else fix_npm(f)
        except Exception as exc:  # noqa: BLE001 - report and keep going with the rest
            reason = f"unexpected error: {exc}"
        (left.append((f, reason)) if reason else fixed.append(f))
        print("  ->", "upgraded" if not reason else f"ROLLED BACK: {reason}")

    print("\n================ trivy-patch summary ================")
    for f in fixed:
        print(f"  upgraded   [{f.ecosystem}] {f.name} {f.installed} -> >= {f.fix}")
    for f, reason in left:
        print(f"  NOT FIXED  [{f.ecosystem}] {f.name} {f.installed} (needs {f.fix}): {reason}")
    if left:
        print("\nOptions for what is left: wait for the upstream package to allow the fix, accept the\n"
              "downgrade by hand, or add the CVE id to .trivyignore with a comment saying why.")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
