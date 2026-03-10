#!/usr/bin/env python3
"""Install a reusable project module into a target repository."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = ROOT / "project_modules"


def copy_tree(src: Path, dst: Path, force: bool) -> list[Path]:
    written: list[Path] = []
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            continue
        shutil.copy2(path, target)
        written.append(target)
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install a reusable project module.")
    parser.add_argument("module_name")
    parser.add_argument("--target", required=True, help="Target repository root.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    module_dir = MODULES_DIR / args.module_name / "template"
    if not module_dir.exists():
        raise SystemExit(f"Module not found: {args.module_name}")
    target = Path(args.target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    written = copy_tree(module_dir, target, args.force)
    for path in written:
        print(path)
    print(f"Installed {args.module_name} into {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
