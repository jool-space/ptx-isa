#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Check a built spec tree before it is published.

NVIDIA reshapes their documentation markup without notice, and the failure mode
is silent: the scraper keeps producing plausible-looking files that are wrong.
Every check here corresponds to a way a build has actually broken.

    ./validate.py dist
    ./validate.py dist --baseline previous   # also check for size cliffs
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Site chrome that must never survive into a doc file.
CHROME = [
    "Search In: Entire Site",
    "Toolkit Documentation",
    "Privacy Policy",
    "NVIDIA-LogoBlack.svg",
]

MAX_FILE_BYTES = 100_000
MAX_SIZE_DRIFT = 0.40
MIN_FILES = 300
EXPECTED_CHAPTERS = 13  # 14 is NVIDIA legal notices; scrape.py drops it


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.notes: list[str] = []

    def check(self, ok: bool, description: str, detail: str = "") -> None:
        print(f"  {'ok  ' if ok else 'FAIL'}  {description}")
        if not ok:
            self.failures.append(f"{description}{f': {detail}' if detail else ''}")
            if detail:
                for line in detail.splitlines()[:10]:
                    print(f"          {line}")

    def note(self, message: str) -> None:
        print(f"  note  {message}")
        self.notes.append(message)


def docs(root: Path) -> list[Path]:
    return sorted((root / "ptx").rglob("*.md"))


def validate(root: Path, baseline: Path | None) -> Report:
    report = Report()
    files = docs(root)

    print(f"\nValidating {root}")
    report.check(len(files) >= MIN_FILES, f"at least {MIN_FILES} section files", f"found {len(files)}")

    manifest_path = root / "VERSION.json"
    report.check(manifest_path.exists(), "VERSION.json present")
    if not manifest_path.exists():
        return report
    manifest = json.loads(manifest_path.read_text())
    version = manifest["ptx_isa_version"]
    report.check(
        bool(re.fullmatch(r"\d+\.\d+", version)),
        "VERSION.json records an ISA version",
        version,
    )

    report.check((root / "SKILL.md").exists(), "SKILL.md present")
    report.check((root / "INDEX.md").exists(), "INDEX.md present")

    skill = (root / "SKILL.md").read_text() if (root / "SKILL.md").exists() else ""
    report.check(
        "{{" not in skill,
        "SKILL.md template placeholders substituted",
        next((line for line in skill.splitlines() if "{{" in line), ""),
    )
    report.check(
        version in skill,
        f"SKILL.md refers to ISA {version}",
    )

    chapters = sorted(d for d in (root / "ptx").iterdir() if d.is_dir())
    numbered = {d.name.split("-", 1)[0] for d in chapters}
    missing = [str(n) for n in range(1, EXPECTED_CHAPTERS + 1) if str(n) not in numbered]
    report.check(not missing, f"chapters 1-{EXPECTED_CHAPTERS} all present", f"missing {missing}")

    # A chapter file that carries its subsections' text means the section
    # splitter stopped recursing -- every chapter would duplicate its children.
    oversized = [f"{f.relative_to(root)} ({f.stat().st_size:,}B)" for f in files if f.stat().st_size > MAX_FILE_BYTES]
    report.check(
        not oversized,
        f"no file exceeds {MAX_FILE_BYTES:,} bytes",
        "\n".join(oversized),
    )

    # Chapter index files hold only the chapter's preamble; if one contains a
    # subsection heading, the parent swallowed its children.
    swallowed = []
    for chapter in chapters:
        index = chapter / f"{chapter.name}.md"
        if index.exists() and re.search(r"^#{2,4} \d+\.\d+\.", index.read_text(), re.M):
            swallowed.append(str(index.relative_to(root)))
    report.check(not swallowed, "chapter files do not duplicate their subsections", "\n".join(swallowed))

    polluted = []
    for path in files:
        text = path.read_text()
        for marker in CHROME:
            if marker in text:
                polluted.append(f"{path.relative_to(root)}: {marker!r}")
    report.check(not polluted, "no site navigation or footer text in docs", "\n".join(polluted))

    empty = [str(f.relative_to(root)) for f in files if f.stat().st_size < 40]
    if empty:
        report.note(f"{len(empty)} near-empty section files (headings with no body)")

    total = sum(f.stat().st_size for f in files)
    print(f"  note  {len(files)} files, {total / 1e6:.2f} MB")

    if baseline and (baseline / "ptx").exists():
        before = sum(f.stat().st_size for f in docs(baseline))
        drift = abs(total - before) / before if before else 0
        report.check(
            drift <= MAX_SIZE_DRIFT,
            f"total size within {MAX_SIZE_DRIFT:.0%} of baseline",
            f"{before / 1e6:.2f} MB -> {total / 1e6:.2f} MB ({drift:+.0%})",
        )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, nargs="?", default=Path("dist"))
    parser.add_argument(
        "--baseline",
        type=Path,
        help="A previously published tree; fails the build on a large size cliff.",
    )
    args = parser.parse_args()

    report = validate(args.root, args.baseline)
    if report.failures:
        print(f"\n{len(report.failures)} check(s) failed:")
        for failure in report.failures:
            print(f"  - {failure}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
