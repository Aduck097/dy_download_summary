#!/usr/bin/env python3
"""Queue and inspect Cursor pipeline jobs stored in the repo."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / ".cursor" / "pipeline"
JOBS_DIR = PIPELINE_DIR / "jobs"
RESULTS_DIR = PIPELINE_DIR / "results"
CONFIG_PATH = PIPELINE_DIR / "config.json"


def ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        return {}
    return load_json(CONFIG_PATH)


def cmd_enqueue(args: argparse.Namespace) -> int:
    ensure_dirs()
    config = load_config()
    defaults = config.get("defaults", {})
    job_id = args.job_id or datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    scope = args.scope or defaults.get("scope", [])
    acceptance = args.acceptance or defaults.get("acceptance_criteria", [])
    verification = args.verify or defaults.get("verification", [])
    constraints = args.constraint or defaults.get("constraints", [])
    payload = {
        "id": job_id,
        "status": "pending",
        "agent": args.agent,
        "title": args.title,
        "task": args.task,
        "scope": scope,
        "acceptance_criteria": acceptance,
        "verification": verification,
        "constraints": constraints,
        "created_at": utc_now(),
        "created_by": "codex",
    }
    path = JOBS_DIR / f"{job_id}.json"
    dump_json(path, payload)
    print(path)
    return 0


def iter_jobs() -> list[Path]:
    ensure_dirs()
    return sorted(JOBS_DIR.glob("*.json"))


def cmd_list(args: argparse.Namespace) -> int:
    jobs = []
    for path in iter_jobs():
        payload = load_json(path)
        if args.status and payload.get("status") != args.status:
            continue
        jobs.append(
            {
                "id": payload.get("id"),
                "status": payload.get("status"),
                "agent": payload.get("agent"),
                "title": payload.get("title"),
                "result_file": payload.get("result_file", ""),
            }
        )
    print(json.dumps(jobs, indent=2, ensure_ascii=False))
    return 0


def resolve_job(job_id: str) -> Path:
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        raise SystemExit(f"Job not found: {job_id}")
    return path


def cmd_show(args: argparse.Namespace) -> int:
    path = resolve_job(args.job_id)
    print(json.dumps(load_json(path), indent=2, ensure_ascii=False))
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    for path in iter_jobs():
        payload = load_json(path)
        if payload.get("status") == "pending":
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
    print("{}")
    return 0


def cmd_result(args: argparse.Namespace) -> int:
    ensure_dirs()
    payload = load_json(resolve_job(args.job_id))
    result_path = RESULTS_DIR / f"{args.job_id}.json"
    if not result_path.exists():
        raise SystemExit(f"Result not found: {result_path}")
    result = load_json(result_path)
    print(json.dumps({"job": payload, "result": result}, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Cursor pipeline jobs.")
    sub = parser.add_subparsers(dest="command", required=True)

    enqueue = sub.add_parser("enqueue", help="Create a new pipeline job.")
    enqueue.add_argument("--job-id", help="Optional explicit job id.")
    enqueue.add_argument("--agent", required=True, choices=["cursor-implementer", "cursor-reviewer", "cursor-acceptance-tester"])
    enqueue.add_argument("--title", required=True)
    enqueue.add_argument("--task", required=True)
    enqueue.add_argument("--scope", action="append", default=[])
    enqueue.add_argument("--acceptance", action="append", default=[])
    enqueue.add_argument("--verify", action="append", default=[])
    enqueue.add_argument("--constraint", action="append", default=[])
    enqueue.set_defaults(func=cmd_enqueue)

    list_cmd = sub.add_parser("list", help="List pipeline jobs.")
    list_cmd.add_argument("--status", choices=["pending", "in_progress", "done", "failed"])
    list_cmd.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="Show one job.")
    show.add_argument("job_id")
    show.set_defaults(func=cmd_show)

    next_cmd = sub.add_parser("next", help="Show the oldest pending job.")
    next_cmd.set_defaults(func=cmd_next)

    result = sub.add_parser("result", help="Show the stored result for one job.")
    result.add_argument("job_id")
    result.set_defaults(func=cmd_result)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
