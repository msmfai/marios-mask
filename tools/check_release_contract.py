#!/usr/bin/env python3
"""Fail fast when public-release version, pins, ignores, or source syntax drift."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def assignment(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=[\"']?([^\"'\n]+)[\"']?$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"missing {name} assignment")
    return match.group(1)


def main() -> int:
    failures: list[str] = []
    version = read("VERSION").strip()
    if not re.fullmatch(r"0\.\d+\.\d+-alpha\.\d+", version):
        failures.append(f"VERSION is not the expected alpha SemVer form: {version!r}")
    tag = f"v{version}"

    documents = {
        "README.md": read("README.md"),
        "RELEASE_V0.1_ALPHA.md": read("RELEASE_V0.1_ALPHA.md"),
        "GITHUB_RELEASE.md": read("GITHUB_RELEASE.md"),
        "PROVENANCE.md": read("PROVENANCE.md"),
    }
    for name in ("README.md", "RELEASE_V0.1_ALPHA.md"):
        if version not in documents[name]:
            failures.append(f"{name} does not identify version {version}")
    for name in ("RELEASE_V0.1_ALPHA.md", "GITHUB_RELEASE.md"):
        if tag not in documents[name]:
            failures.append(f"{name} does not identify tag {tag}")

    wrapper = read("tools/build_from_roms.sh")
    toolchain = read("tools/build-binutils.sh")
    try:
        pinned = {
            "SM64_SHA1": assignment(wrapper, "SM64_SHA1"),
            "MM_MD5": assignment(wrapper, "MM_MD5"),
            "SM64_COMMIT": assignment(wrapper, "SM64_COMMIT"),
            "MM_COMMIT": assignment(wrapper, "MM_COMMIT"),
            "BINUTILS_VER": assignment(toolchain, "BINUTILS_VER"),
            "ICONV_VER": assignment(toolchain, "ICONV_VER"),
        }
    except ValueError as error:
        failures.append(str(error))
        pinned = {}

    expected_docs = {
        "SM64_SHA1": ("README.md",),
        "MM_MD5": ("README.md",),
        "SM64_COMMIT": ("PROVENANCE.md",),
        "MM_COMMIT": ("PROVENANCE.md",),
        "BINUTILS_VER": ("README.md", "PROVENANCE.md"),
        "ICONV_VER": ("README.md", "PROVENANCE.md"),
    }
    for key, value in pinned.items():
        for name in expected_docs[key]:
            if value not in documents[name]:
                failures.append(f"{name} does not contain {key} pin {value}")

    ignored = {line.strip() for line in read(".gitignore").splitlines() if line.strip() and not line.startswith("#")}
    for pattern in ("out/", ".work/", "__pycache__/", "*.pyc", "*.n64", "*.rom", "*.v64", "*.z64", "toolchain/", "src/dsce_config.h", "src/dsce_tuning.h"):
        if pattern not in ignored:
            failures.append(f".gitignore is missing release boundary pattern {pattern}")

    workflow = read(".github/workflows/release-audit.yml")
    for required in ("fetch-depth: 0", "tools/release_audit.py", "tools/check_release_contract.py"):
        if required not in workflow:
            failures.append(f"release workflow is missing {required!r}")

    makefile = read("Makefile")
    for required in ("MM      ?= .work/mm", "SM64    ?= .work/sm64", "TOOLCHAIN ?= $(CURDIR)/.work/toolchain"):
        if required not in makefile:
            failures.append(f"Makefile is not standalone: missing {required!r}")

    for relative in (
        "tools/inputbot/build.sh",
        "tools/inputbot/input_script_plugin.c",
        "tools/inputbot/video_null_plugin.c",
    ):
        if not (ROOT / relative).is_file():
            failures.append(f"standalone public test dependency is missing: {relative}")

    outside_needles = (
        '/Users/',
        '/private/',
        'gitlab/',
        'HERE/../mm',
        'HERE/../sm64',
        'HERE/../tools/inputbot',
        'ROOT.parent / "tools" / "inputbot"',
        'os.path.join(HERE, "..", "tools", "inputbot"',
    )
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in {".git", ".work", "out", "toolchain", "__pycache__"} for part in path.relative_to(ROOT).parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        for needle in outside_needles:
            if needle in content:
                failures.append(f"outside-repository reference {needle!r}: {path.relative_to(ROOT)}")

    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".git", ".work", "out", "toolchain", "__pycache__"} for part in path.relative_to(ROOT).parts):
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (SyntaxError, UnicodeError) as error:
            failures.append(f"Python syntax/encoding: {path.relative_to(ROOT)}: {error}")

    for path in sorted(ROOT.rglob("*.sh")):
        if any(part in {".git", ".work", "out", "toolchain"} for part in path.relative_to(ROOT).parts):
            continue
        checked = subprocess.run(["bash", "-n", str(path)], text=True, capture_output=True)
        if checked.returncode:
            detail = checked.stderr.strip() or f"exit {checked.returncode}"
            failures.append(f"shell syntax: {path.relative_to(ROOT)}: {detail}")

    if failures:
        print("release contract FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(f"release contract OK: {tag}; pins, ignores, workflow, and source syntax agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
