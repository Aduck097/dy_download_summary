#!/usr/bin/env python3
"""Scene-planning entrypoint for the text-to-video pipeline."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from shared_config import get_section, load_shared_config


class VideoPipelineError(RuntimeError):
    """Raised when the local video pipeline cannot continue."""


@dataclass(slots=True)
class ScenePlan:
    scene_id: int
    narration: str
    image_prompt: str
    duration: int
    visual_focus: str


@dataclass(slots=True)
class MotionPlan:
    name: str
    zoom_start: float
    zoom_end: float
    pan_x_start: float
    pan_x_end: float
    pan_y_start: float
    pan_y_end: float


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare text-to-video scene plans.")
    parser.add_argument("--config", type=Path, help="Optional JSON config file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Split text into scene JSON for downstream image/video generation.")
    plan.add_argument("--text", help="Inline script text.")
    plan.add_argument("--input-file", type=Path, help="Text file containing the script.")
    plan.add_argument("--output-dir", type=Path, help="Output directory for scene plan artifacts.")
    plan.add_argument("--title", help="Optional title stored in the plan metadata.")
    plan.add_argument("--target-scene-seconds", type=int, help="Target seconds per scene.")
    plan.add_argument("--min-scene-seconds", type=int, help="Minimum seconds per scene.")
    plan.add_argument("--max-scene-seconds", type=int, help="Maximum seconds per scene.")
    plan.add_argument("--chars-per-second", type=float, help="Narration speed heuristic.")
    plan.add_argument("--style", help="Visual style suffix for generated image prompts.")
    plan.add_argument("--max-scenes", type=int, help="Optionally cap the generated scene count for preview renders.")

    tasks = subparsers.add_parser("image-tasks", help="Generate per-scene image generation tasks from a scene plan.")
    tasks.add_argument("--scene-plan", type=Path, required=True, help="Path to scene_plan.json.")
    tasks.add_argument("--output-dir", type=Path, help="Output directory for task artifacts.")

    generate = subparsers.add_parser("generate-images", help="Generate scene images with Qwen-Image and download them locally.")
    generate.add_argument("--scene-plan", type=Path, required=True, help="Path to scene_plan.json.")
    generate.add_argument("--output-dir", type=Path, help="Output directory for image artifacts.")
    generate.add_argument("--api-key", help="DashScope API key. Falls back to config or environment.")
    generate.add_argument("--model", help="Image model name, defaults to qwen-image-2.0-pro.")
    generate.add_argument("--size", help="Image size, for example 1920*1080 or 1024*1024.")
    generate.add_argument("--negative-prompt", help="Negative prompt passed to the image model.")
    generate.add_argument("--image-count", type=int, help="Number of images per request.")
    generate.add_argument("--seed", type=int, help="Optional random seed.")
    generate.add_argument("--dry-run", action="store_true", help="Write request payloads without calling the API.")
    generate.add_argument("--skip-existing", action="store_true", help="Skip scenes whose output image already exists.")

    render = subparsers.add_parser("render", help="Render a video from a scene plan and existing scene images.")
    render.add_argument("--scene-plan", type=Path, required=True, help="Path to scene_plan.json.")
    render.add_argument("--images-dir", type=Path, required=True, help="Directory containing scene images.")
    render.add_argument("--output-dir", type=Path, help="Output directory for render artifacts.")
    render.add_argument("--ffmpeg-path", help="ffmpeg executable name or full path.")
    render.add_argument("--fps", type=int, help="Output frame rate.")
    render.add_argument("--width", type=int, help="Output width.")
    render.add_argument("--height", type=int, help="Output height.")
    render.add_argument("--codec", help="Output codec, defaults to libx264.")
    render.add_argument("--transition-seconds", type=float, help="Crossfade duration between scenes. Defaults to config or 0.")
    return parser


def merge_config(args: argparse.Namespace) -> dict[str, Any]:
    root = load_shared_config(args.config)
    merged = {
        "paths": get_section(root, "paths"),
        "video": get_section(root, "video"),
        "ffmpeg": get_section(root, "ffmpeg"),
        "qwen_image": get_section(root, "qwen_image"),
    }
    for key in (
        "output_dir",
        "title",
        "target_scene_seconds",
        "min_scene_seconds",
        "max_scene_seconds",
        "chars_per_second",
        "style",
        "max_scenes",
        "ffmpeg_path",
        "fps",
        "width",
        "height",
        "codec",
        "transition_seconds",
        "api_key",
        "model",
        "size",
        "negative_prompt",
        "image_count",
        "seed",
    ):
        value = getattr(args, key, None)
        if value is not None:
            if key == "ffmpeg_path":
                merged["ffmpeg"]["path"] = value
            elif key in {"api_key", "model", "size", "negative_prompt", "image_count", "seed"}:
                merged["qwen_image"][key] = value
            else:
                merged["video"][key] = value
    return merged


def ensure_output_dir(config: dict[str, Any], explicit: Path | None) -> Path:
    if explicit is not None:
        explicit.mkdir(parents=True, exist_ok=True)
        return explicit
    video = config.get("video", {})
    base = Path(video.get("output_dir", "runs/video"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = base / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def ensure_dependency(command_name: str) -> str:
    executable = shutil.which(command_name)
    if executable is None:
        raise VideoPipelineError(f"Required dependency not found on PATH: {command_name}")
    return executable


def http_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=body, method="POST", headers=headers)
    try:
        with request.urlopen(req, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VideoPipelineError(f"POST {url} failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise VideoPipelineError(f"POST {url} failed: {exc.reason}") from exc


def download_binary(url: str, target: Path) -> None:
    try:
        with request.urlopen(url, timeout=300) as response:
            target.write_bytes(response.read())
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VideoPipelineError(f"Downloading {url} failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise VideoPipelineError(f"Downloading {url} failed: {exc.reason}") from exc


def read_script_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text.strip()
    if args.input_file:
        return args.input_file.read_text(encoding="utf-8").strip()
    raise VideoPipelineError("Provide either --text or --input-file.")


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        raise VideoPipelineError("Input text is empty.")
    parts = re.split(r"(?<=[。！？!?；;.:])\s*", normalized)
    sentences = [part.strip(" \n\r\t") for part in parts if part.strip()]
    return sentences or [normalized]


def estimate_duration_seconds(text: str, chars_per_second: float, min_seconds: int, max_seconds: int) -> int:
    char_count = max(len(re.sub(r"\s+", "", text)), 1)
    estimated = round(char_count / max(chars_per_second, 0.1))
    return max(min_seconds, min(max_seconds, estimated))


def build_prompt(narration: str, style: str) -> str:
    prompt_parts = [
        narration,
        "single key frame for a short cinematic video",
        style,
    ]
    return ", ".join(part for part in prompt_parts if part).strip(", ")


def plan_scenes(config: dict[str, Any], text: str) -> list[ScenePlan]:
    video = config.get("video", {})
    target_seconds = int(video.get("target_scene_seconds", 5))
    min_seconds = int(video.get("min_scene_seconds", 4))
    max_seconds = int(video.get("max_scene_seconds", 6))
    chars_per_second = float(video.get("chars_per_second", 4.5))
    style = str(video.get("style", "cinematic lighting, realistic detail, unified visual style"))

    sentences = split_sentences(text)
    target_chars = max(1, round(target_seconds * chars_per_second))
    scenes: list[ScenePlan] = []
    current_parts: list[str] = []
    current_chars = 0

    for sentence in sentences:
        sentence_chars = len(re.sub(r"\s+", "", sentence))
        should_flush = current_parts and current_chars + sentence_chars > target_chars * 1.35
        if should_flush:
            narration = " ".join(current_parts).strip()
            scenes.append(
                ScenePlan(
                    scene_id=len(scenes) + 1,
                    narration=narration,
                    image_prompt=build_prompt(narration, style),
                    duration=estimate_duration_seconds(narration, chars_per_second, min_seconds, max_seconds),
                    visual_focus=narration,
                )
            )
            current_parts = []
            current_chars = 0
        current_parts.append(sentence)
        current_chars += sentence_chars

    if current_parts:
        narration = " ".join(current_parts).strip()
        scenes.append(
            ScenePlan(
                scene_id=len(scenes) + 1,
                narration=narration,
                image_prompt=build_prompt(narration, style),
                duration=estimate_duration_seconds(narration, chars_per_second, min_seconds, max_seconds),
                visual_focus=narration,
            )
        )
    max_scenes = video.get("max_scenes")
    if max_scenes is None:
        return scenes
    return limit_scenes(scenes, int(max_scenes))


def limit_scenes(scenes: list[ScenePlan], max_scenes: int) -> list[ScenePlan]:
    if max_scenes <= 0 or len(scenes) <= max_scenes:
        return scenes
    selected_indices = sorted({round(index * (len(scenes) - 1) / (max_scenes - 1)) for index in range(max_scenes)}) if max_scenes > 1 else [0]
    limited: list[ScenePlan] = []
    for new_id, scene_index in enumerate(selected_indices, start=1):
        scene = scenes[scene_index]
        limited.append(
            ScenePlan(
                scene_id=new_id,
                narration=scene.narration,
                image_prompt=scene.image_prompt,
                duration=scene.duration,
                visual_focus=scene.visual_focus,
            )
        )
    return limited


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise VideoPipelineError(f"Expected JSON object: {path}")
    return payload


def format_srt_timestamp(milliseconds: int) -> str:
    if milliseconds < 0:
        milliseconds = 0
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render_scene_srt(scenes: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    current_ms = 0
    for index, scene in enumerate(scenes, start=1):
        duration_seconds = int(scene.get("duration", 5))
        end_ms = current_ms + duration_seconds * 1000
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_timestamp(current_ms)} --> {format_srt_timestamp(end_ms)}",
                    str(scene.get("narration", "")).strip(),
                ]
            )
        )
        current_ms = end_ms
    return "\n\n".join(blocks).strip()


def resolve_api_key(config: dict[str, Any], explicit: str | None) -> str:
    qwen_image = config.get("qwen_image", {})
    return explicit or qwen_image.get("api_key") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("BAILIAN_API_KEY") or ""


def build_image_request(scene: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    qwen_image = config.get("qwen_image", {})
    parameters: dict[str, Any] = {
        "size": qwen_image.get("size", "1024*1024"),
        "prompt_extend": bool(qwen_image.get("prompt_extend", True)),
        "watermark": bool(qwen_image.get("watermark", False)),
        "n": int(qwen_image.get("image_count", 1)),
    }
    negative_prompt = qwen_image.get("negative_prompt")
    if negative_prompt:
        parameters["negative_prompt"] = negative_prompt
    if qwen_image.get("seed") is not None:
        parameters["seed"] = int(qwen_image["seed"])
    return {
        "model": qwen_image.get("model", "qwen-image-2.0-pro"),
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": str(scene.get("image_prompt", "")).strip(),
                        }
                    ],
                }
            ]
        },
        "parameters": parameters,
    }


def extract_generated_images(payload: dict[str, Any]) -> list[str]:
    output = payload.get("output")
    if not isinstance(output, dict):
        return []
    images: list[str] = []
    choices = output.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("image"), str):
                    images.append(item["image"])
    results = output.get("results")
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("url"), str):
                images.append(item["url"])
            elif isinstance(item.get("image"), str):
                images.append(item["image"])
    return images


def request_image_with_retry(endpoint: str, api_key: str, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    qwen_image = config.get("qwen_image", {})
    attempts = max(int(qwen_image.get("retry_attempts", 4)), 1)
    base_delay = max(float(qwen_image.get("retry_delay_seconds", 8)), 1.0)
    last_error: VideoPipelineError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return http_json(endpoint, api_key, payload)
        except VideoPipelineError as exc:
            last_error = exc
            if "HTTP 429" not in str(exc) or attempt >= attempts:
                break
            time.sleep(base_delay * attempt)
    raise last_error or VideoPipelineError("Image request failed.")


def scene_image_candidates(scene_id: int) -> list[str]:
    base_names = [
        f"scene_{scene_id:03d}",
        f"scene_{scene_id}",
    ]
    suffixes = [".png", ".jpg", ".jpeg", ".webp"]
    return [f"{base}{suffix}" for base in base_names for suffix in suffixes]


def choose_motion_name(scene: dict[str, Any], index: int, total_scenes: int, previous_motion: str | None) -> str:
    explicit_motion = str(scene.get("camera_move") or scene.get("motion") or "").strip().lower()
    aliases = {
        "push_in": "zoom_in",
        "pull_out": "zoom_out",
        "dolly_in": "zoom_in",
        "dolly_out": "zoom_out",
        "pan_left": "pan_right_to_left",
        "pan_right": "pan_left_to_right",
        "truck_left": "pan_right_to_left",
        "truck_right": "pan_left_to_right",
        "hold": "drift_center",
    }
    explicit_motion = aliases.get(explicit_motion, explicit_motion)
    if explicit_motion in {"zoom_in", "zoom_out", "pan_left_to_right", "pan_right_to_left", "drift_center"}:
        if explicit_motion == previous_motion:
            fallback = {
                "zoom_in": "pan_left_to_right",
                "zoom_out": "pan_right_to_left",
                "pan_left_to_right": "zoom_in",
                "pan_right_to_left": "zoom_out",
                "drift_center": "zoom_in",
            }
            return fallback[explicit_motion]
        return explicit_motion

    narration = f"{scene.get('narration', '')} {scene.get('visual_focus', '')} {scene.get('image_prompt', '')}".lower()
    wide_keywords = ("city", "road", "future", "landscape", "skyline", "panorama", "城市", "道路", "全景", "未来")
    subject_keywords = ("doctor", "person", "people", "face", "portrait", "close-up", "人物", "医生", "人脸", "特写")
    transition_keywords = ("from", "into", "through", "across", "进入", "从", "到", "驶过", "穿过")
    summary_keywords = ("finally", "conclusion", "summary", "未来", "整体", "总结", "全貌")

    if any(keyword in narration for keyword in summary_keywords) or index == total_scenes - 1:
        candidate = "zoom_out"
    elif any(keyword in narration for keyword in transition_keywords):
        candidate = "pan_left_to_right" if index % 2 == 0 else "pan_right_to_left"
    elif any(keyword in narration for keyword in wide_keywords):
        candidate = "pan_left_to_right" if index % 2 == 0 else "pan_right_to_left"
    elif any(keyword in narration for keyword in subject_keywords):
        candidate = "zoom_in"
    elif index == 0:
        candidate = "zoom_in"
    else:
        cycle = ["pan_left_to_right", "zoom_in", "pan_right_to_left", "zoom_out"]
        candidate = cycle[index % len(cycle)]

    if previous_motion == candidate:
        fallback = {
            "zoom_in": "pan_left_to_right",
            "zoom_out": "pan_right_to_left",
            "pan_left_to_right": "zoom_in",
            "pan_right_to_left": "zoom_out",
        }
        return fallback[candidate]
    return candidate


def build_motion_plan(motion_name: str) -> MotionPlan:
    plans = {
        "zoom_in": MotionPlan("zoom_in", 1.00, 1.10, 0.50, 0.50, 0.50, 0.50),
        "zoom_out": MotionPlan("zoom_out", 1.10, 1.00, 0.50, 0.50, 0.50, 0.50),
        "pan_left_to_right": MotionPlan("pan_left_to_right", 1.08, 1.10, 0.18, 0.82, 0.50, 0.50),
        "pan_right_to_left": MotionPlan("pan_right_to_left", 1.08, 1.10, 0.82, 0.18, 0.50, 0.50),
        "drift_center": MotionPlan("drift_center", 1.03, 1.06, 0.46, 0.54, 0.48, 0.52),
    }
    return plans.get(motion_name, plans["zoom_in"])


def clamp_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))


def build_zoompan_filter(plan: MotionPlan, frame_count: int, width: int, height: int, fps: int) -> str:
    denom = max(frame_count - 1, 1)
    zoom_delta = plan.zoom_end - plan.zoom_start
    x_start = clamp_ratio(plan.pan_x_start)
    x_end = clamp_ratio(plan.pan_x_end)
    y_start = clamp_ratio(plan.pan_y_start)
    y_end = clamp_ratio(plan.pan_y_end)
    x_ratio_expr = f"{x_start:.4f}+({x_end:.4f}-{x_start:.4f})*(on/{denom})"
    y_ratio_expr = f"{y_start:.4f}+({y_end:.4f}-{y_start:.4f})*(on/{denom})"
    zoom_expr = f"{plan.zoom_start:.4f}+({zoom_delta:.4f})*(on/{denom})"
    x_expr = f"(iw-iw/zoom)*({x_ratio_expr})"
    y_expr = f"(ih-ih/zoom)*({y_ratio_expr})"
    return (
        f"zoompan=z='{zoom_expr}':"
        f"x='{x_expr}':"
        f"y='{y_expr}':"
        f"d={frame_count}:s={width}x{height}:fps={fps}"
    )


def resolve_scene_image(images_dir: Path, scene_id: int) -> Path:
    for name in scene_image_candidates(scene_id):
        candidate = images_dir / name
        if candidate.exists() and candidate.is_file():
            return candidate
    raise VideoPipelineError(
        f"Missing image for scene {scene_id}. Expected one of: {', '.join(scene_image_candidates(scene_id))}"
    )


def run_subprocess(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def render_with_concat(ffmpeg_path: str, concat_list_path: Path, output_path: Path, codec: str) -> subprocess.CompletedProcess[str]:
    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-c:v",
        codec,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    return run_subprocess(command)


def render_with_xfade(
    ffmpeg_path: str,
    segment_paths: list[Path],
    durations: list[int],
    output_path: Path,
    codec: str,
    transition_seconds: float,
) -> subprocess.CompletedProcess[str]:
    inputs: list[str] = []
    for segment_path in segment_paths:
        inputs.extend(["-i", str(segment_path)])

    filter_parts: list[str] = []
    current_label = "[0:v]"
    elapsed = float(durations[0])
    for index in range(1, len(segment_paths)):
        next_label = f"[{index}:v]"
        output_label = f"[v{index}]"
        offset = max(elapsed - transition_seconds, 0.0)
        filter_parts.append(
            f"{current_label}{next_label}xfade=transition=fade:duration={transition_seconds:.3f}:offset={offset:.3f}{output_label}"
        )
        current_label = output_label
        elapsed += float(durations[index]) - transition_seconds

    command = [
        ffmpeg_path,
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        current_label,
        "-c:v",
        codec,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    return run_subprocess(command)


def render_scene_segment(
    ffmpeg_path: str,
    image_path: Path,
    output_path: Path,
    duration_seconds: int,
    fps: int,
    width: int,
    height: int,
    codec: str,
    motion_plan: MotionPlan,
) -> subprocess.CompletedProcess[str]:
    frame_count = max(duration_seconds * fps, 1)
    working_width = int(width * 1.20)
    working_height = int(height * 1.20)
    filter_graph = ",".join(
        [
            f"scale={working_width}:{working_height}:force_original_aspect_ratio=increase",
            build_zoompan_filter(motion_plan, frame_count, width, height, fps),
            "fps={fps}".format(fps=fps),
            "format=yuv420p",
        ]
    )
    command = [
        ffmpeg_path,
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-vf",
        filter_graph,
        "-frames:v",
        str(frame_count),
        "-c:v",
        codec,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    return run_subprocess(command)


def command_plan(args: argparse.Namespace, config: dict[str, Any]) -> int:
    text = read_script_text(args)
    output_dir = ensure_output_dir(config, args.output_dir)
    scenes = plan_scenes(config, text)
    plan_payload = {
        "title": config.get("video", {}).get("title") or "video-plan",
        "source_text": text,
        "scene_count": len(scenes),
        "total_duration_seconds": sum(scene.duration for scene in scenes),
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "narration": scene.narration,
                "image_prompt": scene.image_prompt,
                "duration": scene.duration,
                "visual_focus": scene.visual_focus,
            }
            for scene in scenes
        ],
    }
    write_json(output_dir / "scene_plan.json", plan_payload)
    (output_dir / "script.txt").write_text(text, encoding="utf-8")
    print(f"Scene count: {len(scenes)}")
    print(f"Output directory: {output_dir}")
    return 0


def command_image_tasks(args: argparse.Namespace) -> int:
    scene_plan = load_json(args.scene_plan)
    scenes = scene_plan.get("scenes")
    if not isinstance(scenes, list):
        raise VideoPipelineError("scene_plan.json is missing a scenes array.")
    output_dir = args.output_dir or args.scene_plan.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = {
        "title": scene_plan.get("title"),
        "scene_count": len(scenes),
        "tasks": [
            {
                "scene_id": scene.get("scene_id"),
                "image_prompt": scene.get("image_prompt"),
                "duration": scene.get("duration"),
                "output_file": f"scene_{int(scene.get('scene_id', index + 1)):03d}.png",
                "status": "pending",
            }
            for index, scene in enumerate(scenes)
            if isinstance(scene, dict)
        ],
    }
    write_json(output_dir / "image_tasks.json", tasks)
    print(f"Image tasks: {len(tasks['tasks'])}")
    print(f"Output directory: {output_dir}")
    return 0


def command_generate_images(args: argparse.Namespace, config: dict[str, Any]) -> int:
    scene_plan = load_json(args.scene_plan)
    scenes = scene_plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise VideoPipelineError("scene_plan.json is missing scenes.")
    output_dir = ensure_output_dir(config, args.output_dir)
    images_dir = output_dir / "images"
    requests_dir = output_dir / "requests"
    responses_dir = output_dir / "responses"
    images_dir.mkdir(parents=True, exist_ok=True)
    requests_dir.mkdir(parents=True, exist_ok=True)
    responses_dir.mkdir(parents=True, exist_ok=True)

    api_key = resolve_api_key(config, args.api_key)
    dry_run = bool(args.dry_run)
    if not api_key and not dry_run:
        raise VideoPipelineError("Missing DashScope API key. Set qwen_image.api_key, --api-key, or DASHSCOPE_API_KEY.")

    qwen_image = config.get("qwen_image", {})
    endpoint = qwen_image.get("generation_url", "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation")
    manifest: dict[str, Any] = {
        "scene_plan": str(args.scene_plan.resolve()),
        "output_dir": str(output_dir.resolve()),
        "images_dir": str(images_dir.resolve()),
        "dry_run": dry_run,
        "model": qwen_image.get("model", "qwen-image-2.0-pro"),
        "items": [],
        "failures": [],
    }

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        scene_id = int(scene.get("scene_id", index))
        request_payload = build_image_request(scene, config)
        request_path = requests_dir / f"scene_{scene_id:03d}.request.json"
        write_json(request_path, request_payload)
        image_path = images_dir / f"scene_{scene_id:03d}.png"

        if args.skip_existing and image_path.exists():
            manifest["items"].append(
                {
                    "scene_id": scene_id,
                    "status": "skipped",
                    "image_path": str(image_path.resolve()),
                    "request_path": str(request_path.resolve()),
                }
            )
            continue

        if dry_run:
            manifest["items"].append(
                {
                    "scene_id": scene_id,
                    "status": "dry_run",
                    "image_path": str(image_path.resolve()),
                    "request_path": str(request_path.resolve()),
                }
            )
            continue

        try:
            response_payload = request_image_with_retry(endpoint, api_key, request_payload, config)
            response_path = responses_dir / f"scene_{scene_id:03d}.response.json"
            write_json(response_path, response_payload)
            image_urls = extract_generated_images(response_payload)
            if not image_urls:
                raise VideoPipelineError(f"Image API returned no image URL for scene {scene_id}.")
            download_binary(image_urls[0], image_path)
            manifest["items"].append(
                {
                    "scene_id": scene_id,
                    "status": "generated",
                    "image_path": str(image_path.resolve()),
                    "image_url": image_urls[0],
                    "request_path": str(request_path.resolve()),
                    "response_path": str(response_path.resolve()),
                }
            )
        except VideoPipelineError as exc:
            manifest["failures"].append(
                {
                    "scene_id": scene_id,
                    "error": str(exc),
                    "request_path": str(request_path.resolve()),
                }
            )

    write_json(output_dir / "image_generation_manifest.json", manifest)
    if manifest["failures"]:
        raise VideoPipelineError(f"Image generation failed for {len(manifest['failures'])} scenes.")
    print(f"Image jobs: {len(manifest['items'])}")
    print(f"Output directory: {output_dir}")
    return 0


def command_render(args: argparse.Namespace, config: dict[str, Any]) -> int:
    scene_plan = load_json(args.scene_plan)
    scenes = scene_plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise VideoPipelineError("scene_plan.json is missing scenes.")
    output_dir = ensure_output_dir(config, args.output_dir)
    segments_dir = output_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = ensure_dependency(config.get("ffmpeg", {}).get("path", "ffmpeg"))
    video_config = config.get("video", {})
    fps = int(video_config.get("fps", 30))
    width = int(video_config.get("width", 1920))
    height = int(video_config.get("height", 1080))
    codec = str(video_config.get("codec", "libx264"))
    transition_seconds = max(float(video_config.get("transition_seconds", 0.35)), 0.0)

    manifest: dict[str, Any] = {
        "scene_plan": str(args.scene_plan.resolve()),
        "images_dir": str(args.images_dir.resolve()),
        "segments": [],
        "failures": [],
        "output_video": str((output_dir / "output.mp4").resolve()),
        "output_subtitles": str((output_dir / "subtitles.srt").resolve()),
    }

    concat_list_path = output_dir / "concat.txt"
    concat_lines: list[str] = []
    segment_paths: list[Path] = []
    segment_durations: list[int] = []
    previous_motion: str | None = None

    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        scene_id = int(scene.get("scene_id"))
        image_path = resolve_scene_image(args.images_dir, scene_id)
        segment_path = segments_dir / f"scene_{scene_id:03d}.mp4"
        duration = int(scene.get("duration", 5))
        motion_name = choose_motion_name(scene, index, len(scenes), previous_motion)
        motion_plan = build_motion_plan(motion_name)
        result = render_scene_segment(ffmpeg_path, image_path, segment_path, duration, fps, width, height, codec, motion_plan)
        if result.returncode != 0:
            manifest["failures"].append(
                {
                    "scene_id": scene_id,
                    "image_path": str(image_path.resolve()),
                    "motion": motion_name,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
            )
            continue
        manifest["segments"].append(
            {
                "scene_id": scene_id,
                "image_path": str(image_path.resolve()),
                "segment_path": str(segment_path.resolve()),
                "duration": duration,
                "motion": motion_name,
                "transition": scene.get("transition") or "cut",
            }
        )
        concat_lines.append(f"file '{segment_path.resolve().as_posix()}'")
        segment_paths.append(segment_path)
        segment_durations.append(duration)
        previous_motion = motion_name

    if manifest["failures"]:
        write_json(output_dir / "render_manifest.json", manifest)
        raise VideoPipelineError(f"Failed to render {len(manifest['failures'])} scene segments.")

    concat_list_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    subtitles = render_scene_srt([scene for scene in scenes if isinstance(scene, dict)])
    (output_dir / "subtitles.srt").write_text(subtitles, encoding="utf-8")

    if len(segment_paths) > 1 and transition_seconds > 0:
        concat_result = render_with_xfade(
            ffmpeg_path,
            segment_paths,
            segment_durations,
            output_dir / "output.mp4",
            codec,
            transition_seconds,
        )
        manifest["transition_seconds"] = transition_seconds
    else:
        concat_result = render_with_concat(ffmpeg_path, concat_list_path, output_dir / "output.mp4", codec)
        manifest["transition_seconds"] = 0
    if concat_result.returncode != 0:
        manifest["failures"].append(
            {
                "stage": "concat",
                "stderr": concat_result.stderr,
                "returncode": concat_result.returncode,
            }
        )
        write_json(output_dir / "render_manifest.json", manifest)
        raise VideoPipelineError("Failed to concatenate scene segments.")

    write_json(output_dir / "render_manifest.json", manifest)
    print(f"Rendered scenes: {len(manifest['segments'])}")
    print(f"Output directory: {output_dir}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = merge_config(args)
    try:
        if args.command == "plan":
            return command_plan(args, config)
        if args.command == "image-tasks":
            return command_image_tasks(args)
        if args.command == "generate-images":
            return command_generate_images(args, config)
        if args.command == "render":
            return command_render(args, config)
        parser.error(f"Unsupported command: {args.command}")
    except VideoPipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
