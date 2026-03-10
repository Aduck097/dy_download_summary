#!/usr/bin/env python3
"""Bailian FunASR recorded-file transcription client."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request

import oss2

from shared_config import get_section, load_shared_config


class FunASRError(RuntimeError):
    """Raised when the Bailian FunASR workflow fails."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit and poll Bailian FunASR transcription tasks.")
    parser.add_argument("--config", type=Path, help="Optional JSON config file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload = subparsers.add_parser("upload", help="Upload local files to OSS and print accessible URLs.")
    add_upload_args(upload)

    submit = subparsers.add_parser("submit", help="Submit a FunASR transcription task.")
    add_common_submit_args(submit)

    status = subparsers.add_parser("status", help="Fetch task status and optionally download results.")
    status.add_argument("--task-id", required=True, help="Bailian task ID to query.")
    status.add_argument("--download-results", action="store_true", help="Download successful transcription JSON files.")
    status.add_argument("--output-dir", type=Path, help="Output directory for stored status and transcript artifacts.")

    run = subparsers.add_parser("run", help="Submit and poll a task until completion.")
    add_common_submit_args(run)
    return parser


def add_common_submit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--file-url", action="append", dest="file_urls", help="Public file URL to transcribe. Repeat for multiple files.")
    parser.add_argument("--file-urls-json", type=Path, help="Path to a JSON file containing an array of file URLs.")
    parser.add_argument("--local-file", action="append", dest="local_files", help="Local audio file to upload to OSS before submission. Repeat for multiple files.")
    parser.add_argument("--api-key", help="Bailian API key or temporary token.")
    parser.add_argument("--model", help="FunASR model name.")
    parser.add_argument("--output-dir", type=Path, help="Output directory for stored task artifacts.")
    parser.add_argument("--download-results", action="store_true", help="Download successful transcription JSON files after completion.")


def add_upload_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--local-file", action="append", dest="local_files", required=True, help="Local file to upload to OSS. Repeat for multiple files.")
    parser.add_argument("--output-dir", type=Path, help="Output directory for upload artifacts.")
    parser.add_argument("--object-prefix", help="Override OSS object prefix for uploaded files.")


def merge_config(args: argparse.Namespace) -> dict[str, Any]:
    root = load_shared_config(args.config)
    merged = {
        "funasr": get_section(root, "funasr"),
        "oss": get_section(root, "oss"),
        "paths": get_section(root, "paths"),
    }
    if not merged["funasr"] and not merged["oss"]:
        merged = {
            "funasr": dict(root),
            "oss": {},
            "paths": {},
        }
    for key in ("api_key", "model", "output_dir"):
        value = getattr(args, key, None)
        if value is not None:
            merged["funasr"][key] = value
    object_prefix = getattr(args, "object_prefix", None)
    if object_prefix is not None:
        merged["oss"]["object_prefix"] = object_prefix
    return merged


def resolve_api_key(config: dict[str, Any], explicit: str | None) -> str:
    funasr = config.get("funasr", {})
    return explicit or funasr.get("api_key") or os.getenv("BAILIAN_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or ""


def resolve_oss_credentials(config: dict[str, Any]) -> tuple[str, str, str]:
    oss = config.get("oss", {})
    access_key_id = oss.get("access_key_id") or os.getenv("ALIYUN_ACCESS_KEY_ID") or os.getenv("OSS_ACCESS_KEY_ID") or ""
    access_key_secret = oss.get("access_key_secret") or os.getenv("ALIYUN_ACCESS_KEY_SECRET") or os.getenv("OSS_ACCESS_KEY_SECRET") or ""
    security_token = oss.get("security_token") or os.getenv("ALIYUN_SECURITY_TOKEN") or os.getenv("OSS_SECURITY_TOKEN") or ""
    return access_key_id, access_key_secret, security_token


def read_file_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.file_urls or [])
    if args.file_urls_json:
        payload = load_shared_config(args.file_urls_json)
        if not isinstance(payload, list):
            raise FunASRError("file-urls-json must contain a JSON array of URLs.")
        urls.extend(payload)
    if not urls and not list(args.local_files or []):
        raise FunASRError("Provide at least one --file-url, --file-urls-json, or --local-file.")
    for url in urls:
        if not isinstance(url, str) or not url:
            raise FunASRError("All file URLs must be non-empty strings.")
        parsed = parse.urlparse(url)
        if parsed.scheme not in {"http", "https", "oss"}:
            raise FunASRError(
                f"Unsupported file reference: {url}. Bailian FunASR requires a public HTTP/HTTPS URL or supported oss:// reference."
            )
    if len(urls) > 100:
        raise FunASRError("Bailian FunASR accepts at most 100 file URLs per request.")
    return urls


def default_output_dir(config: dict[str, Any]) -> Path:
    funasr = config.get("funasr", {})
    base = Path(funasr.get("output_dir", "runs/funasr"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = base / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def ensure_output_dir(config: dict[str, Any], explicit: Path | None) -> Path:
    if explicit is not None:
        explicit.mkdir(parents=True, exist_ok=True)
        return explicit
    return default_output_dir(config)


def http_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None, extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=120) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise FunASRError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise FunASRError(f"{method} {url} failed: {exc.reason}") from exc


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_text(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def submit_task(config: dict[str, Any], api_key: str, file_urls: list[str], model: str | None) -> dict[str, Any]:
    funasr = config.get("funasr", {})
    payload: dict[str, Any] = {
        "model": model or funasr.get("model", "fun-asr"),
        "input": {"file_urls": file_urls},
    }
    parameters = funasr.get("parameters") or {}
    if parameters:
        payload["parameters"] = parameters
    return http_json(
        "POST",
        funasr.get("submit_url", "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"),
        api_key,
        payload=payload,
        extra_headers={"X-DashScope-Async": "enable"},
    )


def fetch_status(config: dict[str, Any], api_key: str, task_id: str) -> dict[str, Any]:
    funasr = config.get("funasr", {})
    template = funasr.get("task_url_template", "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}")
    url = template.format(task_id=task_id)
    return http_json("POST", url, api_key)


def wait_for_completion(config: dict[str, Any], api_key: str, task_id: str) -> dict[str, Any]:
    funasr = config.get("funasr", {})
    interval = int(funasr.get("poll_interval_seconds", 5))
    timeout = int(funasr.get("poll_timeout_seconds", 600))
    deadline = time.time() + timeout
    while True:
        payload = fetch_status(config, api_key, task_id)
        status = (((payload.get("output") or {}).get("task_status")) or "").upper()
        if status in {"SUCCEEDED", "FAILED", "CANCELED"}:
            return payload
        if time.time() >= deadline:
            raise FunASRError(f"Polling timed out after {timeout} seconds for task {task_id}.")
        time.sleep(interval)


def download_url(url: str, target: Path) -> None:
    try:
        with request.urlopen(url, timeout=120) as response:
            target.write_bytes(response.read())
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise FunASRError(f"Downloading {url} failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise FunASRError(f"Downloading {url} failed: {exc.reason}") from exc


def extract_text(result_json: dict[str, Any]) -> str:
    transcripts = result_json.get("transcripts") or []
    chunks: list[str] = []
    for transcript in transcripts:
        text = transcript.get("text")
        if isinstance(text, str) and text:
            chunks.append(text)
    return "\n".join(chunks).strip()


def normalize_words(words: Any) -> list[dict[str, Any]]:
    if not isinstance(words, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in words:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "begin_time_ms": item.get("begin_time"),
                "end_time_ms": item.get("end_time"),
                "text": item.get("text", ""),
                "punctuation": item.get("punctuation", ""),
            }
        )
    return normalized


def extract_timeline(result_json: dict[str, Any]) -> list[dict[str, Any]]:
    transcripts = result_json.get("transcripts") or []
    timeline: list[dict[str, Any]] = []
    for transcript_index, transcript in enumerate(transcripts, start=1):
        if not isinstance(transcript, dict):
            continue
        sentence_candidates: list[dict[str, Any]] = []
        for key in ("sentences", "sentence_list", "segments", "utterances"):
            value = transcript.get(key)
            if isinstance(value, list):
                sentence_candidates = [item for item in value if isinstance(item, dict)]
                break
        if not sentence_candidates and {"begin_time", "end_time", "text"} <= set(transcript):
            sentence_candidates = [transcript]
        for sentence_index, sentence in enumerate(sentence_candidates, start=1):
            begin_time = sentence.get("begin_time")
            end_time = sentence.get("end_time")
            text = sentence.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            timeline.append(
                {
                    "transcript_index": transcript_index,
                    "channel_id": transcript.get("channel_id"),
                    "sentence_index": sentence_index,
                    "sentence_id": sentence.get("sentence_id"),
                    "begin_time_ms": begin_time,
                    "end_time_ms": end_time,
                    "duration_ms": (end_time - begin_time) if isinstance(begin_time, int) and isinstance(end_time, int) else None,
                    "text": text.strip(),
                    "words": normalize_words(sentence.get("words")),
                }
            )
    return timeline


def format_srt_timestamp(milliseconds: int) -> str:
    if milliseconds < 0:
        milliseconds = 0
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render_srt(timeline: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(timeline, start=1):
        begin_time = item.get("begin_time_ms")
        end_time = item.get("end_time_ms")
        text = item.get("text")
        if not isinstance(begin_time, int) or not isinstance(end_time, int) or not isinstance(text, str):
            continue
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_timestamp(begin_time)} --> {format_srt_timestamp(end_time)}",
                    text.strip(),
                ]
            )
        )
    return "\n\n".join(blocks).strip()


def sanitize_filename(name: str) -> str:
    cleaned = "".join(char if char not in '<>:"/\\|?*' else "_" for char in name)
    return cleaned.strip().replace(" ", "_") or "audio"


def shorten_object_name(name: str, limit: int = 20) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix or ".bin"
    safe_stem = sanitize_filename(stem)
    if len(safe_stem) > limit:
        safe_stem = safe_stem[:limit].rstrip("._-") or "audio"
    return f"{safe_stem}{suffix}"


def build_oss_bucket(config: dict[str, Any]) -> oss2.Bucket:
    oss = config.get("oss", {})
    endpoint = oss.get("endpoint") or ""
    bucket_name = oss.get("bucket") or ""
    if not endpoint or not bucket_name:
        raise FunASRError("Missing OSS endpoint or bucket in shared config.")
    access_key_id, access_key_secret, security_token = resolve_oss_credentials(config)
    if not access_key_id or not access_key_secret:
        raise FunASRError(
            "Missing OSS credentials. Set access_key_id/access_key_secret in config or use ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET."
        )
    auth = oss2.StsAuth(access_key_id, access_key_secret, security_token) if security_token else oss2.Auth(access_key_id, access_key_secret)
    return oss2.Bucket(auth, endpoint, bucket_name)


def object_url(config: dict[str, Any], bucket: oss2.Bucket, object_key: str) -> str:
    oss = config.get("oss", {})
    public_base_url = (oss.get("public_base_url") or "").rstrip("/")
    if public_base_url:
        return f"{public_base_url}/{parse.quote(object_key)}"
    expires = int(oss.get("sign_url_expires_seconds", 3600))
    return bucket.sign_url("GET", object_key, expires, slash_safe=True)


def upload_local_files(config: dict[str, Any], local_files: list[Path], output_dir: Path) -> list[str]:
    if not local_files:
        return []
    bucket = build_oss_bucket(config)
    oss = config.get("oss", {})
    prefix = (oss.get("object_prefix") or "douyin-audio").strip("/")
    date_prefix = datetime.now().strftime("%Y/%m/%d")
    urls: list[str] = []
    upload_manifest: list[dict[str, Any]] = []
    for local_path in local_files:
        if not local_path.exists() or not local_path.is_file():
            raise FunASRError(f"Local file does not exist: {local_path}")
        stamped_name = f"{datetime.now().strftime('%H%M%S')}_{shorten_object_name(local_path.name)}"
        object_key = "/".join(part for part in (prefix, date_prefix, stamped_name) if part)
        result = bucket.put_object_from_file(object_key, str(local_path))
        if result.status not in {200, 201}:
            raise FunASRError(f"OSS upload failed for {local_path} with status {result.status}.")
        url = object_url(config, bucket, object_key)
        urls.append(url)
        upload_manifest.append(
            {
                "local_path": str(local_path.resolve()),
                "object_key": object_key,
                "url": url,
                "etag": getattr(result, "etag", ""),
            }
        )
    write_json(output_dir / "uploads.json", {"items": upload_manifest})
    return urls


def save_task_artifacts(output_dir: Path, task_payload: dict[str, Any], download_results: bool) -> None:
    write_json(output_dir / "task.json", task_payload)
    if not download_results:
        return
    results = ((task_payload.get("output") or {}).get("results")) or []
    for index, item in enumerate(results, start=1):
        if item.get("subtask_status") != "SUCCEEDED":
            continue
        transcription_url = item.get("transcription_url")
        if not transcription_url:
            continue
        json_path = output_dir / f"result_{index}.json"
        download_url(transcription_url, json_path)
        result_payload = json.loads(json_path.read_text(encoding="utf-8"))
        write_text(output_dir / f"result_{index}.txt", extract_text(result_payload))
        timeline = extract_timeline(result_payload)
        write_json(
            output_dir / f"result_{index}.timeline.json",
            {
                "file_url": result_payload.get("file_url"),
                "transcript_count": len(result_payload.get("transcripts") or []),
                "sentence_count": len(timeline),
                "timeline": timeline,
            },
        )
        srt_content = render_srt(timeline)
        if srt_content:
            write_text(output_dir / f"result_{index}.srt", srt_content)


def command_submit(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api_key = resolve_api_key(config, args.api_key)
    if not api_key:
        raise FunASRError("Missing API key. Set it in config, --api-key, BAILIAN_API_KEY, or DASHSCOPE_API_KEY.")
    output_dir = ensure_output_dir(config, args.output_dir)
    file_urls = read_file_urls(args)
    local_files = [Path(path) for path in (args.local_files or [])]
    file_urls.extend(upload_local_files(config, local_files, output_dir))
    payload = submit_task(config, api_key, file_urls, args.model)
    write_json(output_dir / "submit.json", payload)
    task_id = ((payload.get("output") or {}).get("task_id")) or ""
    print(f"Task ID: {task_id}")
    print(f"Output directory: {output_dir}")
    return 0


def command_status(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api_key = resolve_api_key(config, None)
    if not api_key:
        raise FunASRError("Missing API key. Set it in config, BAILIAN_API_KEY, or DASHSCOPE_API_KEY.")
    output_dir = ensure_output_dir(config, args.output_dir)
    payload = fetch_status(config, api_key, args.task_id)
    save_task_artifacts(output_dir, payload, args.download_results)
    print(f"Task status: {((payload.get('output') or {}).get('task_status'))}")
    print(f"Output directory: {output_dir}")
    return 0


def command_run(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api_key = resolve_api_key(config, args.api_key)
    if not api_key:
        raise FunASRError("Missing API key. Set it in config, --api-key, BAILIAN_API_KEY, or DASHSCOPE_API_KEY.")
    output_dir = ensure_output_dir(config, args.output_dir)
    file_urls = read_file_urls(args)
    local_files = [Path(path) for path in (args.local_files or [])]
    file_urls.extend(upload_local_files(config, local_files, output_dir))
    submit_payload = submit_task(config, api_key, file_urls, args.model)
    write_json(output_dir / "submit.json", submit_payload)
    task_id = ((submit_payload.get("output") or {}).get("task_id")) or ""
    if not task_id:
        raise FunASRError("Submit response did not contain a task_id.")
    task_payload = wait_for_completion(config, api_key, task_id)
    save_task_artifacts(output_dir, task_payload, args.download_results)
    task_status = ((task_payload.get("output") or {}).get("task_status")) or ""
    print(f"Task ID: {task_id}")
    print(f"Task status: {task_status}")
    print(f"Output directory: {output_dir}")
    return 0


def command_upload(args: argparse.Namespace, config: dict[str, Any]) -> int:
    output_dir = ensure_output_dir(config, args.output_dir)
    local_files = [Path(path) for path in (args.local_files or [])]
    urls = upload_local_files(config, local_files, output_dir)
    for url in urls:
        print(url)
    print(f"Output directory: {output_dir}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = merge_config(args)
    try:
        if args.command == "upload":
            return command_upload(args, config)
        if args.command == "submit":
            return command_submit(args, config)
        if args.command == "status":
            return command_status(args, config)
        if args.command == "run":
            return command_run(args, config)
        parser.error(f"Unsupported command: {args.command}")
    except FunASRError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
