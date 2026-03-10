#!/usr/bin/env python3
"""Local pipeline for fetching Douyin videos and converting them to MP3."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shared_config import get_section, load_shared_config


DEFAULT_EXTENSIONS = [".mp4", ".mov", ".mkv", ".webm"]


class PipelineError(RuntimeError):
    """Raised when the pipeline configuration or subprocess steps fail."""


@dataclass
class RunContext:
    run_dir: Path
    videos_dir: Path
    audio_dir: Path
    manifest_path: Path
    source_ref: str
    download_dir: Path | None = None


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "douyin-run"


def shorten_stem(value: str, limit: int = 20) -> str:
    cleaned = re.sub(r"\s+", "_", value).strip("._ ")
    if len(cleaned) <= limit:
        return cleaned or "audio"
    return cleaned[:limit].rstrip("._ ") or "audio"


def shorten_filename(name: str, index: int, limit: int = 48) -> str:
    path = Path(name)
    suffix = path.suffix.lower() or ".mp4"
    stem = shorten_stem(path.stem, limit=limit)
    return f"video_{index:03d}_{stem}{suffix}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Douyin videos and convert them to MP3.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run downloader and converter pipeline.")
    run.add_argument("--config", type=Path, help="Optional JSON config file.")
    run.add_argument("--profile-url", help="Douyin profile URL.")
    run.add_argument("--sec-user-id", help="Douyin sec_user_id if you prefer an identifier over a full URL.")
    run.add_argument("--cookie", help="Raw Douyin cookie string for the downloader.")
    run.add_argument("--cookie-file", type=Path, help="Path to a cookie file for the downloader.")
    run.add_argument("--runs-dir", type=Path, default=Path("runs"), help="Base directory for pipeline runs.")
    run.add_argument("--output-dir", type=Path, help="Explicit output directory for this run.")
    run.add_argument("--run-name", help="Optional custom run name. Defaults to a slug based on input.")
    run.add_argument("--video-dir", type=Path, help="Use an existing video directory instead of downloaded output.")
    run.add_argument("--skip-download", action="store_true", help="Skip downloader execution and use --video-dir or an existing run videos directory.")
    run.add_argument("--skip-convert", action="store_true", help="Skip MP3 conversion and only write manifest entries for videos.")
    run.add_argument("--downloader-bin", help="Downloader executable name or full path.")
    run.add_argument("--download-template", help="Command template used to launch the downloader.")
    run.add_argument("--ffmpeg-path", help="ffmpeg executable name or full path.")
    run.add_argument("--audio-sample-rate", type=int, help="MP3 sample rate, for example 16000.")
    run.add_argument("--audio-channels", type=int, help="MP3 channel count, for example 1.")
    run.add_argument("--audio-bitrate", help="MP3 bitrate, for example 64k.")
    run.add_argument("--video-extensions", nargs="+", help="Video file extensions to scan, for example .mp4 .mov")
    return parser


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    root = load_shared_config(args.config)
    merged: dict[str, Any] = {}
    merged.update(get_section(root, "douyin"))
    ffmpeg = get_section(root, "ffmpeg")
    if "path" in ffmpeg:
        merged["ffmpeg_path"] = ffmpeg["path"]
    for key in ("audio_sample_rate", "audio_channels", "audio_bitrate"):
        if key in ffmpeg:
            merged[key] = ffmpeg[key]
    paths = get_section(root, "paths")
    if "runs_dir" in paths:
        merged["runs_dir"] = paths["runs_dir"]
    if not merged:
        merged = dict(root)
    for key in (
        "profile_url",
        "sec_user_id",
        "cookie",
        "cookie_file",
        "runs_dir",
        "output_dir",
        "run_name",
        "video_dir",
        "skip_download",
        "skip_convert",
        "downloader_bin",
        "download_template",
        "ffmpeg_path",
        "audio_sample_rate",
        "audio_channels",
        "audio_bitrate",
        "video_extensions",
    ):
        value = getattr(args, key, None)
        if value is not None:
            merged[key] = value
    return merged


def ensure_dependency(command_name: str) -> str:
    executable = shutil.which(command_name)
    if executable is None:
        raise PipelineError(f"Required dependency not found on PATH: {command_name}")
    return executable


def create_run_context(config: dict[str, Any]) -> RunContext:
    source_ref = config.get("profile_url") or config.get("sec_user_id") or "local-video-dir"
    explicit_output_dir = config.get("output_dir")
    if explicit_output_dir:
        run_dir = Path(explicit_output_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = slugify(config.get("run_name") or source_ref)
        run_dir = Path(config.get("runs_dir", "runs")) / f"{stamp}-{suffix}"
    videos_dir = run_dir / "videos"
    audio_dir = run_dir / "audio"
    run_dir.mkdir(parents=True, exist_ok=bool(explicit_output_dir))
    videos_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    return RunContext(
        run_dir=run_dir,
        videos_dir=videos_dir,
        audio_dir=audio_dir,
        manifest_path=run_dir / "manifest.json",
        source_ref=source_ref,
    )


def create_download_workspace(config: dict[str, Any]) -> Path:
    runs_dir = Path(config.get("runs_dir", "runs")).resolve()
    workspace_root = runs_dir.parent
    return Path(tempfile.mkdtemp(prefix="dy-", dir=str(workspace_root)))


def build_download_command(config: dict[str, Any], run: RunContext) -> list[str]:
    template = config.get("download_template")
    if not template:
        raise PipelineError("Missing download_template. Set it in config.json or pass --download-template.")

    cookie = str(config.get("cookie", ""))
    # HTTP cookies do not require spaces after semicolons, and removing them
    # keeps the command-line placeholder from being split into extra arguments.
    cookie = re.sub(r";\s+", ";", cookie).strip()

    placeholders = {
        "profile_url": config.get("profile_url", ""),
        "sec_user_id": config.get("sec_user_id", ""),
        "cookie": cookie,
        "cookie_file": str(config.get("cookie_file", "")),
        "run_dir": str(run.run_dir.resolve()),
        "videos_dir": str((run.download_dir or run.videos_dir).resolve()),
    }
    try:
        rendered = template.format(**placeholders)
    except KeyError as exc:
        raise PipelineError(f"Unknown placeholder in download_template: {exc.args[0]}") from exc

    command = shlex.split(rendered, posix=os.name != "nt")
    if not command:
        raise PipelineError("download_template rendered an empty command.")

    downloader_bin = config.get("downloader_bin")
    if downloader_bin:
        command[0] = downloader_bin
    return command


def run_subprocess(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def discover_videos(video_dir: Path, extensions: list[str]) -> list[Path]:
    lowered = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}
    return sorted(path for path in video_dir.rglob("*") if path.is_file() and path.suffix.lower() in lowered)


def convert_video(ffmpeg_path: str, video_path: Path, audio_path: Path, sample_rate: int, channels: int, bitrate: str) -> subprocess.CompletedProcess[str]:
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-b:a",
        bitrate,
        str(audio_path),
    ]
    return run_subprocess(command)


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def materialize_downloaded_videos(source_dir: Path, target_dir: Path, extensions: list[str]) -> list[dict[str, Any]]:
    staged_videos = discover_videos(source_dir, extensions)
    copied: list[dict[str, Any]] = []
    for index, staged_path in enumerate(staged_videos, start=1):
        target_name = shorten_filename(staged_path.name, index)
        target_path = target_dir / target_name
        shutil.copy2(staged_path, target_path)
        copied.append(
            {
                "staged_path": str(staged_path.resolve()),
                "path": str(target_path.resolve()),
                "name": target_path.name,
                "size_bytes": target_path.stat().st_size,
            }
        )
    return copied


def run_pipeline(config: dict[str, Any]) -> int:
    profile_url = config.get("profile_url")
    sec_user_id = config.get("sec_user_id")
    skip_download = bool(config.get("skip_download"))
    skip_convert = bool(config.get("skip_convert"))
    video_dir_override = Path(config["video_dir"]) if config.get("video_dir") else None
    video_extensions = config.get("video_extensions") or DEFAULT_EXTENSIONS

    if not skip_download and not (profile_url or sec_user_id):
        raise PipelineError("Provide --profile-url or --sec-user-id unless --skip-download is set.")

    if skip_download and video_dir_override is None:
        raise PipelineError("When using --skip-download, you must provide --video-dir.")

    run = create_run_context(config)
    manifest: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "profile_url": profile_url,
            "sec_user_id": sec_user_id,
        },
        "run_dir": str(run.run_dir.resolve()),
        "videos_dir": str(run.videos_dir.resolve()),
        "audio_dir": str(run.audio_dir.resolve()),
        "download": {
            "attempted": not skip_download,
            "command": None,
            "returncode": None,
            "stdout": None,
            "stderr": None,
        },
        "videos": [],
        "audio": [],
        "failures": [],
    }

    if not skip_download:
        downloader_bin = config.get("downloader_bin", "f2")
        config["downloader_bin"] = ensure_dependency(downloader_bin)
        run.download_dir = create_download_workspace(config)
        command = build_download_command(config, run)
        manifest["download"]["command"] = command
        manifest["download"]["staging_dir"] = str(run.download_dir.resolve())
        result = run_subprocess(command, cwd=run.run_dir)
        manifest["download"]["returncode"] = result.returncode
        manifest["download"]["stdout"] = result.stdout
        manifest["download"]["stderr"] = result.stderr
        if result.returncode != 0:
            write_manifest(run.manifest_path, manifest)
            raise PipelineError(f"Downloader failed with exit code {result.returncode}. See manifest.json for stderr.")
        manifest["download"]["materialized_videos"] = materialize_downloaded_videos(run.download_dir, run.videos_dir, video_extensions)

    source_video_dir = video_dir_override or run.videos_dir
    if not source_video_dir.exists():
        write_manifest(run.manifest_path, manifest)
        raise PipelineError(f"Video directory does not exist: {source_video_dir}")

    videos = discover_videos(source_video_dir, video_extensions)
    if not skip_download and manifest["download"].get("materialized_videos"):
        manifest["videos"] = list(manifest["download"]["materialized_videos"])
    else:
        manifest["videos"] = [
            {
                "path": str(path.resolve()),
                "name": path.name,
                "size_bytes": path.stat().st_size,
            }
            for path in videos
        ]

    if not skip_convert:
        ffmpeg_path = ensure_dependency(config.get("ffmpeg_path", "ffmpeg"))
        sample_rate = int(config.get("audio_sample_rate", 16000))
        channels = int(config.get("audio_channels", 1))
        bitrate = str(config.get("audio_bitrate", "64k"))

        for video_path in videos:
            audio_name = shorten_stem(video_path.stem)
            audio_path = run.audio_dir / f"{audio_name}.mp3"
            result = convert_video(ffmpeg_path, video_path, audio_path, sample_rate, channels, bitrate)
            if result.returncode == 0:
                manifest["audio"].append(
                    {
                        "source_video": str(video_path.resolve()),
                        "path": str(audio_path.resolve()),
                        "size_bytes": audio_path.stat().st_size,
                    }
                )
            else:
                manifest["failures"].append(
                    {
                        "stage": "convert",
                        "source_video": str(video_path.resolve()),
                        "returncode": result.returncode,
                        "stderr": result.stderr,
                    }
                )

    write_manifest(run.manifest_path, manifest)
    failed = len(manifest["failures"])
    print(f"Run directory: {run.run_dir}")
    print(f"Discovered videos: {len(videos)}")
    print(f"Generated mp3 files: {len(manifest['audio'])}")
    if failed:
        print(f"Failures: {failed}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command != "run":
        parser.error(f"Unsupported command: {args.command}")

    config = resolve_config(args)
    try:
        return run_pipeline(config)
    except PipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
