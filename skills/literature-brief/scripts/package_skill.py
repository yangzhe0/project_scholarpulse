#!/usr/bin/env python3
"""Validate, test, and create a reproducible literature-brief release archive."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR.parents[1]


def metadata() -> tuple[str, str]:
    content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    name_match = re.search(r"(?m)^name:\s*['\"]?([^'\"\r\n]+)", content)
    version_match = re.search(r"(?m)^\s*version:\s*['\"]?([^'\"\r\n]+)", content)
    if not name_match or not version_match:
        raise ValueError("SKILL.md must declare name and metadata.version")
    return name_match.group(1).strip(), version_match.group(1).strip()


def package_files() -> list[Path]:
    ignored_parts = {"__pycache__", ".pytest_cache", "dist"}
    return sorted(
        path for path in SKILL_DIR.rglob("*")
        if path.is_file()
        and not ignored_parts.intersection(path.parts)
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )


def run_tests() -> None:
    subprocess.run([sys.executable, str(SCRIPT_DIR / "test_search_literature.py")], check=True)


def build(output_dir: Path) -> tuple[Path, Path]:
    name, version = metadata()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{name}-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in package_files():
            relative = path.relative_to(SKILL_DIR)
            info = zipfile.ZipInfo(f"{name}/{relative.as_posix()}", date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_suffix(".zip.sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return archive, checksum


def main() -> int:
    parser = argparse.ArgumentParser(description="Test and package the literature-brief skill.")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "dist")
    parser.add_argument("--skip-tests", action="store_true", help="Package without running offline regression tests")
    args = parser.parse_args()
    if not args.skip_tests:
        run_tests()
    archive, checksum = build(args.output_dir.resolve())
    print(f"archive: {archive}")
    print(f"sha256:  {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
