#!/usr/bin/env python3
"""Project-scoped orchestrator for condensed story video remakes."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from shared_config import get_section, load_shared_config
import video_pipeline


class StoryProjectError(RuntimeError):
    """Raised when the project orchestration pipeline cannot continue."""


@dataclass(slots=True)
class ProjectPaths:
    root: Path
    ingest: Path
    stt: Path
    summary: Path
    rewrite: Path
    tts: Path
    storyboard: Path
    route_a: Path
    route_b: Path
    final: Path
    compare: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a project-scoped story remake pipeline.")
    parser.add_argument("--config", type=Path, help="Optional JSON config file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run the full condensed A/B pipeline for one source video.")
    run.add_argument("--profile-url", required=True, help="Source Douyin video URL.")
    run.add_argument("--project-slug", help="Optional project slug.")
    run.add_argument("--project-root", type=Path, help="Explicit project root output directory.")
    run.add_argument("--max-scenes", type=int, default=4, help="Condensed scene count for both routes.")
    run.add_argument("--skip-ingest", action="store_true", help="Reuse existing ingest artifacts under the project root.")
    run.add_argument("--skip-stt", action="store_true", help="Reuse existing STT artifacts under the project root.")
    run.add_argument("--skip-route-a", action="store_true", help="Skip the Qwen-image plus FFmpeg route.")
    run.add_argument("--skip-route-b", action="store_true", help="Skip the Wan image-to-video route.")
    return parser


def merge_config(args: argparse.Namespace) -> dict[str, Any]:
    root = load_shared_config(args.config)
    return {
        "paths": get_section(root, "paths"),
        "douyin": get_section(root, "douyin"),
        "funasr": get_section(root, "funasr"),
        "video": get_section(root, "video"),
        "ffmpeg": get_section(root, "ffmpeg"),
        "tts": get_section(root, "tts"),
        "qwen_image": get_section(root, "qwen_image"),
        "qwen_text": get_section(root, "qwen_text"),
        "wan_video": get_section(root, "wan_video"),
    }


def slugify(value: str) -> str:
    return "-".join(part for part in "".join(char.lower() if char.isalnum() else "-" for char in value).split("-") if part) or "story-project"


def extract_video_id(profile_url: str) -> str:
    marker = "/video/"
    if marker not in profile_url:
        return "source"
    remainder = profile_url.split(marker, 1)[1]
    return "".join(char for char in remainder if char.isdigit()) or "source"


def build_project_paths(config: dict[str, Any], profile_url: str, explicit_slug: str | None, explicit_root: Path | None) -> ProjectPaths:
    if explicit_root is not None:
        root = explicit_root
    else:
        video_id = extract_video_id(profile_url)
        project_slug = explicit_slug or f"douyin-{video_id}"
        base = Path(config.get("paths", {}).get("runs_dir", "runs")) / "projects" / slugify(project_slug)
        root = base / datetime.now().strftime("%Y%m%d-%H%M%S")

    ingest = root / "01_ingest"
    stt = root / "02_stt"
    summary = root / "03_summary"
    rewrite = root / "04_rewrite"
    tts = root / "05_tts"
    storyboard = root / "06_storyboard"
    route_a = root / "07_route_a_qwen_ffmpeg"
    route_b = root / "08_route_b_wan_i2v"
    final = root / "09_final"
    compare = root / "10_compare"
    for path in (ingest, stt, summary, rewrite, tts, storyboard, route_a, route_b, final, compare):
        path.mkdir(parents=True, exist_ok=True)
    return ProjectPaths(root, ingest, stt, summary, rewrite, tts, storyboard, route_a, route_b, final, compare)


def run_command(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        cwd=str(cwd or Path(__file__).resolve().parents[1]),
    )
    if result.returncode != 0:
        raise StoryProjectError(
            f"Command failed ({result.returncode}): {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise StoryProjectError(f"Expected JSON object: {path}")
    return payload


def find_first(path: Path, pattern: str) -> Path:
    matches = sorted(path.glob(pattern))
    if not matches:
        raise StoryProjectError(f"Missing expected artifact matching {pattern} under {path}")
    return matches[0]


def resolve_shared_api_key(config: dict[str, Any]) -> str:
    for section_name in ("tts", "wan_video", "qwen_text", "qwen_image", "funasr"):
        section = config.get(section_name, {})
        value = section.get("api_key")
        if isinstance(value, str) and value:
            return value
    return ""


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    req = request.Request(url=url, data=json.dumps(payload).encode("utf-8"), method="POST", headers=headers)
    try:
        with request.urlopen(req, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise StoryProjectError(f"POST {url} failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise StoryProjectError(f"POST {url} failed: {exc.reason}") from exc


def get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = request.Request(url=url, method="GET", headers=headers)
    try:
        with request.urlopen(req, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise StoryProjectError(f"GET {url} failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise StoryProjectError(f"GET {url} failed: {exc.reason}") from exc


def download_file(url: str, target: Path) -> None:
    req = request.Request(url=url, method="GET")
    try:
        with request.urlopen(req, timeout=600) as response:
            target.write_bytes(response.read())
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise StoryProjectError(f"Downloading {url} failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise StoryProjectError(f"Downloading {url} failed: {exc.reason}") from exc


def extract_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise StoryProjectError("Model response did not contain a JSON object.")
    return json.loads(cleaned[start : end + 1])


def chat_json(config: dict[str, Any], system_prompt: str, user_prompt: str) -> dict[str, Any]:
    api_key = resolve_shared_api_key(config)
    if not api_key:
        raise StoryProjectError("Missing DashScope API key for summary and rewrite planning.")
    qwen_text = config.get("qwen_text", {})
    endpoint = str(qwen_text.get("endpoint") or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    payload = {
        "model": str(qwen_text.get("model") or "qwen-plus"),
        "temperature": float(qwen_text.get("temperature", 0.6)),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    response = post_json(endpoint, {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, payload)
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise StoryProjectError(f"Unexpected chat response: {response}")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise StoryProjectError(f"Chat response did not contain message content: {response}")
    return extract_json_block(content)


def build_summary_prompt(transcript_text: str, max_scenes: int) -> tuple[str, str]:
    system_prompt = (
        "You are a Chinese content strategist. "
        "Summarize long transcripts into concise production guidance for a short-video remake. "
        "Return JSON only."
    )
    user_prompt = f"""
请把下面的中文转写内容整理成一个用于视频重制的总结，不要直接改写成口播。

要求：
1. 提炼核心观点、论证顺序、情绪基调、适合保留的关键表达。
2. 指出哪些内容属于重复、口水话、赘述，后续应该压缩或删除。
3. 给出 {max_scenes} 个推荐叙事段落方向，供后续改写和分镜使用。
4. 返回 JSON，结构必须是：
{{
  "title": "...",
  "summary": "...",
  "tone": "...",
  "core_message": "...",
  "key_points": ["...", "..."],
  "remove_or_compress": ["...", "..."],
  "audience_takeaway": "...",
  "recommended_beats": [
    {{
      "beat_id": 1,
      "headline": "...",
      "goal": "...",
      "source_focus": "..."
    }}
  ]
}}

转写内容：
{transcript_text}
""".strip()
    return system_prompt, user_prompt


def build_rewrite_prompt(summary_payload: dict[str, Any], max_scenes: int) -> tuple[str, str]:
    system_prompt = (
        "You are a Chinese short-video script writer. "
        "Rewrite from a summary into fresh spoken lines that preserve the core meaning but do not reuse the original wording. "
        "The result should sound conversational and suitable for a warm female narration. "
        "Return JSON only."
    )
    user_prompt = f"""
请根据下面的 summary.json 生成一版全新的中文口播稿。

要求：
1. 核心表达思想必须一致，但不能照抄原转写。
2. 用更口语化、更顺、更像真人讲述的表达。
3. 每个 beat 输出一段 spoken_text，适合直接做 TTS。
4. 总共输出 {max_scenes} 个 beat。
5. 每段 spoken_text 尽量控制在 1 到 3 句。
6. 返回 JSON，结构必须是：
{{
  "title": "...",
  "hook": "...",
  "summary": "...",
  "continuity": {{
    "protagonist": "...",
    "wardrobe": "...",
    "setting": "...",
    "time_of_day": "...",
    "palette": "...",
    "camera_language": "..."
  }},
  "beats": [
    {{
      "beat_id": 1,
      "headline": "...",
      "spoken_text": "...",
      "visual_anchor": "...",
      "continuity_note": "...",
      "duration_hint": 5
    }}
  ]
}}

summary.json:
{json.dumps(summary_payload, ensure_ascii=False, indent=2)}
""".strip()
    return system_prompt, user_prompt


def stringify_compact(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def build_character_bible(rewrite_payload: dict[str, Any], summary_payload: dict[str, Any]) -> dict[str, Any]:
    continuity = rewrite_payload.get("continuity") or {}
    protagonist = normalize_text(continuity.get("protagonist") or "Chinese female narrator in her late 20s")
    wardrobe = normalize_text(continuity.get("wardrobe") or "soft cream knit cardigan with a light beige blouse")
    palette = normalize_text(continuity.get("palette") or "warm natural palette, soft beige and wood tones")
    tone = normalize_text(summary_payload.get("tone") or "calm, grounded, reflective")
    return {
        "project_title": normalize_text(rewrite_payload.get("title") or summary_payload.get("title") or "story-video"),
        "style_direction": palette or "cinematic realism",
        "characters": [
            {
                "character_id": "protagonist_01",
                "role": "primary narrator",
                "display_name": normalize_text(protagonist or "?????"),
                "identity_prompt": protagonist,
                "wardrobe_lock": {
                    "summary": wardrobe,
                },
                "voice_persona": "warm, calm, conversational, trustworthy",
                "performance_notes": [
                    tone or "natural spoken delivery",
                    "maintain realistic expression and restrained gestures",
                ],
                "hard_constraints": [
                    "keep the same facial structure and age impression across all shots",
                    "do not change wardrobe inside the same sequence",
                ],
                "reference_images": [],
            }
        ],
    }


def build_scene_bible(rewrite_payload: dict[str, Any], summary_payload: dict[str, Any]) -> dict[str, Any]:
    continuity = rewrite_payload.get("continuity") or {}
    setting = normalize_text(continuity.get("setting") or "small realistic office corner for direct-to-camera storytelling")
    time_of_day = normalize_text(continuity.get("time_of_day") or "afternoon")
    palette = normalize_text(continuity.get("palette") or "warm beige, soft wood brown, muted green accents")
    camera_language = normalize_text(continuity.get("camera_language") or "natural eye-level camera with gentle push-ins and slow lateral drift")
    return {
        "project_title": normalize_text(rewrite_payload.get("title") or summary_payload.get("title") or "story-video"),
        "global_style": {
            "visual_style": "cinematic realism",
            "palette": palette,
            "lighting": f"{time_of_day} natural light",
            "lens_bias": camera_language,
            "texture": "grounded, realistic, lived-in",
        },
        "scenes": [
            {
                "scene_id": "primary_location",
                "display_name": normalize_text(setting or "???"),
                "location_prompt": setting,
                "time_of_day": time_of_day,
                "must_keep": [
                    setting,
                    palette,
                    f"{time_of_day} light",
                ],
                "allowed_variations": [
                    "camera angle changes",
                    "framing distance changes",
                    "small prop or posture changes",
                ],
                "prop_lock": [],
                "transition_role": "main narrative location",
                "reference_images": [],
            }
        ],
    }


def build_director_prompt(
    rewrite_payload: dict[str, Any], character_bible: dict[str, Any], scene_bible: dict[str, Any]
) -> tuple[str, str]:
    system_prompt = (
        "You are a film director and storyboard artist creating a coherent AI video remake. "
        "You maintain visual continuity across shots and vary camera language intentionally. "
        "Return JSON only."
    )
    user_prompt = f"""
??? rewrite.json ???????

???
1. ???????????????????
2. ??????????????????zoom_in, zoom_out, pan_left_to_right, pan_right_to_left, drift_center?
3. ?? scene ???????? prompt ????? prompt?
4. narration ??? rewrite ? spoken_text ???????????????
5. transition ??? cut?dissolve?bridge?
6. ????? character_bible.json ? scene_bible.json????????????
7. ?? JSON???????
{{
  "title": "...",
  "style": "...",
  "scenes": [
    {{
      "scene_id": 1,
      "headline": "...",
      "narration": "...",
      "duration": 5,
      "visual_focus": "...",
      "continuity_anchor": "...",
      "camera_move": "zoom_in",
      "transition": "dissolve",
      "image_prompt": "...",
      "video_prompt": "..."
    }}
  ]
}}

rewrite.json:
{stringify_compact(rewrite_payload)}

character_bible.json:
{stringify_compact(character_bible)}

scene_bible.json:
{stringify_compact(scene_bible)}
""".strip()
    return system_prompt, user_prompt


def normalize_summary(payload: dict[str, Any], max_scenes: int) -> dict[str, Any]:
    beats = payload.get("recommended_beats")
    normalized_beats: list[dict[str, Any]] = []
    if isinstance(beats, list):
        for index, beat in enumerate(beats[:max_scenes], start=1):
            if not isinstance(beat, dict):
                continue
            normalized_beats.append(
                {
                    "beat_id": index,
                    "headline": str(beat.get("headline") or f"Beat {index}").strip(),
                    "goal": str(beat.get("goal") or "").strip(),
                    "source_focus": str(beat.get("source_focus") or "").strip(),
                }
            )
    if not normalized_beats:
        normalized_beats = [{"beat_id": 1, "headline": "核心观点", "goal": str(payload.get("core_message") or "").strip(), "source_focus": "全文核心内容"}]
    payload["recommended_beats"] = normalized_beats
    return payload


def normalize_rewrite(payload: dict[str, Any], max_scenes: int) -> dict[str, Any]:
    beats = payload.get("beats")
    if not isinstance(beats, list) or not beats:
        raise StoryProjectError("rewrite response is missing beats.")
    normalized_beats: list[dict[str, Any]] = []
    for index, beat in enumerate(beats[:max_scenes], start=1):
        if not isinstance(beat, dict):
            continue
        spoken_text = str(beat.get("spoken_text") or beat.get("narration") or "").strip()
        normalized_beats.append(
            {
                "beat_id": index,
                "headline": str(beat.get("headline") or f"Beat {index}").strip(),
                "spoken_text": spoken_text,
                "visual_anchor": str(beat.get("visual_anchor") or "").strip(),
                "continuity_note": str(beat.get("continuity_note") or "").strip(),
                "duration_hint": max(4, min(15, int(beat.get("duration_hint") or 5))),
            }
        )
    payload["beats"] = normalized_beats
    return payload


def normalize_director_plan(payload: dict[str, Any]) -> dict[str, Any]:
    scenes = payload.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise StoryProjectError("director plan is missing scenes.")
    normalized_scenes: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        normalized_scenes.append(
            {
                "scene_id": index,
                "headline": str(scene.get("headline") or f"Scene {index}").strip(),
                "narration": str(scene.get("narration") or "").strip(),
                "duration": max(4, min(15, int(scene.get("duration") or 5))),
                "visual_focus": str(scene.get("visual_focus") or "").strip(),
                "continuity_anchor": str(scene.get("continuity_anchor") or "").strip(),
                "camera_move": str(scene.get("camera_move") or "drift_center").strip(),
                "transition": str(scene.get("transition") or "dissolve").strip(),
                "image_prompt": str(scene.get("image_prompt") or "").strip(),
                "video_prompt": str(scene.get("video_prompt") or "").strip(),
            }
        )
    payload["scene_count"] = len(normalized_scenes)
    payload["scenes"] = normalized_scenes
    return payload


def build_shot_continuity(
    rewrite_payload: dict[str, Any],
    director_payload: dict[str, Any],
    character_bible: dict[str, Any],
    scene_bible: dict[str, Any],
) -> dict[str, Any]:
    rewrite_beats = {int(beat["beat_id"]): beat for beat in rewrite_payload.get("beats", []) if isinstance(beat, dict)}
    protagonist = ((character_bible.get("characters") or [{}])[0] if isinstance(character_bible.get("characters"), list) else {})
    primary_scene = ((scene_bible.get("scenes") or [{}])[0] if isinstance(scene_bible.get("scenes"), list) else {})
    raw_scenes = director_payload.get("scenes", [])
    shots: list[dict[str, Any]] = []
    previous_visual_state = "start of sequence"
    for index, scene in enumerate(raw_scenes, start=1):
        if not isinstance(scene, dict):
            continue
        beat = rewrite_beats.get(index, {})
        current_visual_state = normalize_text(scene.get("visual_focus") or beat.get("visual_anchor") or scene.get("headline") or f"Scene {index}")
        next_note = ""
        if index < len(raw_scenes) and isinstance(raw_scenes[index], dict):
            next_note = normalize_text(raw_scenes[index].get("visual_focus") or raw_scenes[index].get("headline"))
        shots.append(
            {
                "shot_id": index,
                "beat_id": index,
                "character_id": protagonist.get("character_id") or "protagonist_01",
                "scene_id": primary_scene.get("scene_id") or "primary_location",
                "narration": normalize_text(beat.get("spoken_text") or scene.get("narration")),
                "shot_role": "establishing intro" if index == 1 else "narrative continuation",
                "visual_goal": current_visual_state,
                "continuity_anchor": normalize_text(
                    scene.get("continuity_anchor")
                    or beat.get("continuity_note")
                    or f"same character, same wardrobe, same location, evolving from: {previous_visual_state}"
                ),
                "prev_visual_state": previous_visual_state,
                "current_visual_state": current_visual_state,
                "next_visual_state": next_note or "sequence end",
                "camera_plan": {
                    "framing": "medium shot" if index == 1 else "medium close-up",
                    "angle": "eye level",
                    "move": normalize_text(scene.get("camera_move") or "drift_center"),
                    "lens_feel": "natural 35mm" if index == 1 else "natural 50mm",
                    "energy": "calm" if index == 1 else "focused",
                },
                "transition_out": normalize_text(scene.get("transition") or "dissolve"),
                "image_prompt_addendum": normalize_text(scene.get("image_prompt")),
                "video_prompt_addendum": normalize_text(scene.get("video_prompt")),
            }
        )
        previous_visual_state = current_visual_state
    return {
        "project_title": normalize_text(rewrite_payload.get("title") or "story-video"),
        "sequence_goal": normalize_text(rewrite_payload.get("summary") or "coherent spoken remake with stable continuity"),
        "shots": shots,
    }


def compose_image_prompt(
    shot: dict[str, Any], character_bible: dict[str, Any], scene_bible: dict[str, Any], director_scene: dict[str, Any]
) -> str:
    protagonist = ((character_bible.get("characters") or [{}])[0] if isinstance(character_bible.get("characters"), list) else {})
    primary_scene = ((scene_bible.get("scenes") or [{}])[0] if isinstance(scene_bible.get("scenes"), list) else {})
    parts = [
        "single key frame for a coherent short cinematic video",
        normalize_text(character_bible.get("style_direction") or scene_bible.get("global_style", {}).get("visual_style")),
        normalize_text(protagonist.get("identity_prompt")),
        normalize_text((protagonist.get("wardrobe_lock") or {}).get("summary")),
        normalize_text(primary_scene.get("location_prompt")),
        normalize_text(shot.get("continuity_anchor")),
        normalize_text(shot.get("current_visual_state")),
        normalize_text(director_scene.get("visual_focus")),
        normalize_text(shot.get("image_prompt_addendum")),
    ]
    return ", ".join(part for part in parts if part)


def compose_video_prompt(
    shot: dict[str, Any], character_bible: dict[str, Any], scene_bible: dict[str, Any], director_scene: dict[str, Any]
) -> str:
    protagonist = ((character_bible.get("characters") or [{}])[0] if isinstance(character_bible.get("characters"), list) else {})
    primary_scene = ((scene_bible.get("scenes") or [{}])[0] if isinstance(scene_bible.get("scenes"), list) else {})
    parts = [
        "coherent cinematic continuation shot",
        normalize_text(protagonist.get("identity_prompt")),
        normalize_text((protagonist.get("wardrobe_lock") or {}).get("summary")),
        normalize_text(primary_scene.get("location_prompt")),
        f"inherit previous visual state: {normalize_text(shot.get('prev_visual_state'))}",
        f"current state: {normalize_text(shot.get('current_visual_state'))}",
        f"handoff to next state: {normalize_text(shot.get('next_visual_state'))}",
        f"camera move: {normalize_text((shot.get('camera_plan') or {}).get('move'))}",
        normalize_text(director_scene.get("video_prompt") or shot.get("video_prompt_addendum")),
    ]
    return ", ".join(part for part in parts if part)


def build_scene_plan(
    director_payload: dict[str, Any],
    rewrite_payload: dict[str, Any],
    duration_map: dict[int, int],
    character_bible: dict[str, Any],
    scene_bible: dict[str, Any],
    shot_continuity: dict[str, Any],
) -> dict[str, Any]:
    rewrite_beats = {int(beat["beat_id"]): beat for beat in rewrite_payload.get("beats", []) if isinstance(beat, dict)}
    continuity = rewrite_payload.get("continuity") or {}
    shots_by_id = {int(shot["shot_id"]): shot for shot in shot_continuity.get("shots", []) if isinstance(shot, dict)}
    scenes: list[dict[str, Any]] = []
    for scene in director_payload.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = int(scene.get("scene_id", len(scenes) + 1))
        beat = rewrite_beats.get(scene_id, {})
        shot = shots_by_id.get(scene_id, {})
        scenes.append(
            {
                "scene_id": scene_id,
                "headline": str(scene.get("headline") or beat.get("headline") or f"Scene {scene_id}").strip(),
                "narration": str(beat.get("spoken_text") or scene.get("narration") or "").strip(),
                "duration": int(duration_map.get(scene_id, scene.get("duration", beat.get("duration_hint", 5)))),
                "visual_focus": str(scene.get("visual_focus") or beat.get("visual_anchor") or "").strip(),
                "continuity_anchor": str(shot.get("continuity_anchor") or scene.get("continuity_anchor") or beat.get("continuity_note") or "").strip(),
                "camera_move": str(scene.get("camera_move") or "drift_center").strip(),
                "transition": str(scene.get("transition") or "dissolve").strip(),
                "image_prompt": compose_image_prompt(shot, character_bible, scene_bible, scene),
                "video_prompt": compose_video_prompt(shot, character_bible, scene_bible, scene),
                "character_id": str(shot.get("character_id") or "protagonist_01"),
                "scene_ref_id": str(shot.get("scene_id") or "primary_location"),
                "prev_visual_state": str(shot.get("prev_visual_state") or "").strip(),
                "current_visual_state": str(shot.get("current_visual_state") or "").strip(),
                "next_visual_state": str(shot.get("next_visual_state") or "").strip(),
            }
        )
    return {
        "title": director_payload.get("title") or rewrite_payload.get("title") or "story-video",
        "style": director_payload.get("style") or "cinematic realism",
        "summary": rewrite_payload.get("summary") or "",
        "continuity": continuity,
        "character_bible": character_bible,
        "scene_bible": scene_bible,
        "shot_continuity_path": "06_storyboard/shot_continuity.json",
        "scene_count": len(scenes),
        "total_duration_seconds": sum(int(scene["duration"]) for scene in scenes),
        "scenes": scenes,
    }


def build_tts_request(text: str, config: dict[str, Any]) -> dict[str, Any]:
    tts = config.get("tts", {})
    payload: dict[str, Any] = {
        "model": str(tts.get("model") or "qwen3-tts-instruct-flash"),
        "input": {
            "text": text,
            "voice": str(tts.get("voice") or "Serena"),
            "language_type": str(tts.get("language_type") or "Chinese"),
        },
    }
    parameters: dict[str, Any] = {}
    if tts.get("format"):
        parameters["format"] = str(tts["format"])
    if tts.get("sample_rate"):
        parameters["sample_rate"] = int(tts["sample_rate"])
    if tts.get("volume") is not None:
        parameters["volume"] = int(tts["volume"])
    if tts.get("speed") is not None:
        parameters["speed"] = float(tts["speed"])
    if tts.get("pitch") is not None:
        parameters["pitch"] = float(tts["pitch"])
    if tts.get("instructions"):
        parameters["instructions"] = str(tts["instructions"])
    if tts.get("prompt"):
        parameters["prompt"] = str(tts["prompt"])
    if tts.get("use_chat_template") is not None:
        parameters["use_chat_template"] = bool(tts["use_chat_template"])
    if tts.get("optimize_instructions") is not None:
        parameters["optimize_instructions"] = bool(tts["optimize_instructions"])
    if parameters:
        payload["parameters"] = parameters
    return payload


def extract_tts_audio_url(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if isinstance(output, dict):
        audio = output.get("audio")
        if isinstance(audio, dict):
            url = audio.get("url")
            if isinstance(url, str) and url:
                return url
        for key in ("audio_url", "url"):
            value = output.get(key)
            if isinstance(value, str) and value:
                return value
    raise StoryProjectError(f"Unable to find audio URL in TTS payload: {payload}")


def resolve_ffprobe_path(ffmpeg_path: str) -> str:
    ffmpeg_candidate = Path(ffmpeg_path)
    if ffmpeg_candidate.parent != Path("."):
        ffprobe_candidate = ffmpeg_candidate.with_name("ffprobe.exe" if ffmpeg_candidate.suffix.lower() == ".exe" else "ffprobe")
        if ffprobe_candidate.exists():
            return str(ffprobe_candidate)
    found = shutil.which("ffprobe")
    if found:
        return found
    raise StoryProjectError("ffprobe was not found on PATH.")


def probe_duration_seconds(ffprobe_path: str, media_path: Path) -> float:
    result = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise StoryProjectError(f"ffprobe failed for {media_path}: {result.stderr}")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise StoryProjectError(f"ffprobe returned an invalid duration for {media_path}: {result.stdout}") from exc


def normalize_audio_file(ffmpeg_path: str, source: Path, target: Path, sample_rate: int) -> None:
    run_command(
        [
            ffmpeg_path,
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(target),
        ]
    )


def pad_audio_file(ffmpeg_path: str, source: Path, target: Path, target_seconds: int) -> None:
    run_command(
        [
            ffmpeg_path,
            "-y",
            "-i",
            str(source),
            "-af",
            "apad",
            "-t",
            str(target_seconds),
            "-c:a",
            "pcm_s16le",
            str(target),
        ]
    )


def concat_audio_files(ffmpeg_path: str, sources: list[Path], output_path: Path) -> None:
    concat_list = output_path.parent / "audio_concat.txt"
    write_text(concat_list, "\n".join(f"file '{source.resolve().as_posix()}'" for source in sources) + "\n")
    run_command(
        [
            ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    )


def build_line_srt(items: list[dict[str, Any]]) -> str:
    def split_caption_units(text: str, max_chars: int = 18) -> list[str]:
        cleaned = " ".join(str(text).split()).strip()
        if not cleaned:
            return []
        chunks: list[str] = []
        buffer = ""
        punctuation = "，。！？；：,.!?;:"
        for char in cleaned:
            buffer += char
            should_flush = False
            if char in punctuation:
                should_flush = True
            elif len(buffer) >= max_chars:
                should_flush = True
            if should_flush:
                chunk = buffer.strip(" ，。！？；：,.!?;:")
                if chunk:
                    chunks.append(chunk)
                buffer = ""
        tail = buffer.strip(" ，。！？；：,.!?;:")
        if tail:
            chunks.append(tail)
        return chunks or [cleaned]

    blocks: list[str] = []
    current_ms = 0
    cue_index = 1
    for item in items:
        scene_duration_ms = int(item["scene_duration_seconds"]) * 1000
        units = split_caption_units(str(item["text"]).strip())
        if not units:
            current_ms += scene_duration_ms
            continue
        slice_ms = max(scene_duration_ms // len(units), 800)
        scene_start_ms = current_ms
        for unit_index, unit in enumerate(units, start=1):
            start_ms = scene_start_ms + (unit_index - 1) * slice_ms
            end_ms = scene_start_ms + unit_index * slice_ms if unit_index < len(units) else current_ms + scene_duration_ms
            blocks.append(
                "\n".join(
                    [
                        str(cue_index),
                        f"{video_pipeline.format_srt_timestamp(start_ms)} --> {video_pipeline.format_srt_timestamp(end_ms)}",
                        unit,
                    ]
                )
            )
            cue_index += 1
        current_ms += scene_duration_ms
    return "\n\n".join(blocks).strip()


def synthesize_tts(config: dict[str, Any], project: ProjectPaths, rewrite_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[int, int]]:
    api_key = resolve_shared_api_key(config)
    if not api_key:
        raise StoryProjectError("Missing DashScope API key for TTS.")
    ffmpeg_path = video_pipeline.ensure_dependency(config.get("ffmpeg", {}).get("path", "ffmpeg"))
    ffprobe_path = resolve_ffprobe_path(ffmpeg_path)
    tts = config.get("tts", {})
    endpoint = str(tts.get("generation_url") or "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation")
    sample_rate = int(tts.get("sample_rate") or 24000)
    silence_padding = float(tts.get("silence_padding_seconds") or 0.35)

    raw_dir = project.tts / "raw"
    normalized_dir = project.tts / "normalized"
    padded_dir = project.tts / "padded"
    requests_dir = project.tts / "requests"
    responses_dir = project.tts / "responses"
    for path in (raw_dir, normalized_dir, padded_dir, requests_dir, responses_dir):
        path.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "model": str(tts.get("model") or "qwen3-tts-instruct-flash"),
        "voice": str(tts.get("voice") or "Serena"),
        "items": [],
        "narration_audio": "",
        "subtitles": "",
    }
    duration_map: dict[int, int] = {}
    padded_audio_files: list[Path] = []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    for beat in rewrite_payload.get("beats", []):
        if not isinstance(beat, dict):
            continue
        scene_id = int(beat.get("beat_id", 0))
        text = str(beat.get("spoken_text") or "").strip()
        request_payload = build_tts_request(text, config)
        request_path = requests_dir / f"scene_{scene_id:03d}.request.json"
        response_path = responses_dir / f"scene_{scene_id:03d}.response.json"
        raw_path = raw_dir / f"scene_{scene_id:03d}.wav"
        normalized_path = normalized_dir / f"scene_{scene_id:03d}.wav"
        padded_path = padded_dir / f"scene_{scene_id:03d}.wav"
        write_json(request_path, request_payload)
        response_payload = post_json(endpoint, headers, request_payload)
        write_json(response_path, response_payload)
        audio_url = extract_tts_audio_url(response_payload)
        download_file(audio_url, raw_path)
        normalize_audio_file(ffmpeg_path, raw_path, normalized_path, sample_rate)
        raw_duration = probe_duration_seconds(ffprobe_path, normalized_path)
        scene_duration = max(4, min(15, math.ceil(raw_duration + silence_padding)))
        pad_audio_file(ffmpeg_path, normalized_path, padded_path, scene_duration)
        padded_audio_files.append(padded_path)
        duration_map[scene_id] = scene_duration
        manifest["items"].append(
            {
                "scene_id": scene_id,
                "headline": beat.get("headline"),
                "text": text,
                "audio_url": audio_url,
                "request_path": str(request_path.resolve()),
                "response_path": str(response_path.resolve()),
                "raw_audio_path": str(raw_path.resolve()),
                "audio_path": str(normalized_path.resolve()),
                "padded_audio_path": str(padded_path.resolve()),
                "raw_duration_seconds": raw_duration,
                "scene_duration_seconds": scene_duration,
            }
        )

    narration_audio_path = project.tts / "narration.wav"
    concat_audio_files(ffmpeg_path, padded_audio_files, narration_audio_path)
    subtitles_path = project.tts / "subtitles.srt"
    write_text(subtitles_path, build_line_srt(manifest["items"]))
    manifest["narration_audio"] = str(narration_audio_path.resolve())
    manifest["subtitles"] = str(subtitles_path.resolve())
    write_json(project.tts / "tts_manifest.json", manifest)
    return manifest, duration_map


def run_route_a(config: dict[str, Any], config_path: Path | None, project: ProjectPaths, scene_plan_path: Path) -> dict[str, Any]:
    shared_api_key = resolve_shared_api_key(config)
    generate_cmd = [sys.executable, "scripts/video_pipeline.py"]
    if config_path is not None:
        generate_cmd.extend(["--config", str(config_path)])
    generate_cmd.extend(["generate-images", "--scene-plan", str(scene_plan_path), "--output-dir", str(project.route_a)])
    if shared_api_key:
        generate_cmd.extend(["--api-key", shared_api_key])
    run_command(generate_cmd)

    render_cmd = [sys.executable, "scripts/video_pipeline.py"]
    if config_path is not None:
        render_cmd.extend(["--config", str(config_path)])
    render_cmd.extend(
        [
            "render",
            "--scene-plan",
            str(scene_plan_path),
            "--images-dir",
            str(project.route_a / "images"),
            "--output-dir",
            str(project.route_a / "render"),
        ]
    )
    run_command(render_cmd)
    return load_json(project.route_a / "image_generation_manifest.json")


def resolve_video_url(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if isinstance(output, dict):
        for key in ("video_url", "url"):
            value = output.get(key)
            if isinstance(value, str) and value:
                return value
        results = output.get("results")
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                for key in ("video_url", "url"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        return value
    raise StoryProjectError(f"Unable to locate video URL in task payload: {payload}")


def run_route_b(config: dict[str, Any], project: ProjectPaths, scene_plan: dict[str, Any], route_a_manifest: dict[str, Any]) -> dict[str, Any]:
    api_key = resolve_shared_api_key(config)
    if not api_key:
        raise StoryProjectError("Missing DashScope API key for Wan video generation.")

    ffmpeg_path = video_pipeline.ensure_dependency(config.get("ffmpeg", {}).get("path", "ffmpeg"))
    wan_video = config.get("wan_video", {})
    endpoint = str(wan_video.get("generation_url") or "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis")
    task_template = str(wan_video.get("task_url_template") or "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}")
    poll_interval = max(int(wan_video.get("poll_interval_seconds", 8)), 3)
    poll_timeout = max(int(wan_video.get("poll_timeout_seconds", 1800)), 60)
    model = str(wan_video.get("model") or "wan2.6-i2v-flash")

    clips_dir = project.route_b / "clips"
    tasks_dir = project.route_b / "tasks"
    clips_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)

    image_url_by_scene: dict[int, str] = {}
    for item in route_a_manifest.get("items", []):
        if isinstance(item, dict) and isinstance(item.get("scene_id"), int) and isinstance(item.get("image_url"), str):
            image_url_by_scene[item["scene_id"]] = item["image_url"]

    manifest: dict[str, Any] = {
        "model": model,
        "scene_plan": str((project.storyboard / "scene_plan.json").resolve()),
        "clips": [],
        "failures": [],
        "output_video": str((project.route_b / "output.mp4").resolve()),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    for scene in scene_plan.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = int(scene.get("scene_id", 0))
        image_url = image_url_by_scene.get(scene_id)
        if not image_url:
            manifest["failures"].append({"scene_id": scene_id, "error": "Missing image_url from route A manifest"})
            continue
        payload = {
            "model": model,
            "input": {
                "prompt": str(scene.get("video_prompt") or scene.get("image_prompt") or "").strip(),
                "img_url": image_url,
            },
            "parameters": {
                "duration": max(4, min(15, int(scene.get("duration") or 5))),
                "prompt_extend": bool(wan_video.get("prompt_extend", True)),
            },
        }
        if wan_video.get("resolution"):
            payload["parameters"]["resolution"] = wan_video["resolution"]
        if wan_video.get("watermark") is not None:
            payload["parameters"]["watermark"] = bool(wan_video["watermark"])

        request_path = tasks_dir / f"scene_{scene_id:03d}.request.json"
        response_path = tasks_dir / f"scene_{scene_id:03d}.submit.json"
        status_path = tasks_dir / f"scene_{scene_id:03d}.status.json"
        clip_path = clips_dir / f"scene_{scene_id:03d}.mp4"
        write_json(request_path, payload)
        submit_payload = post_json(endpoint, headers, payload)
        write_json(response_path, submit_payload)
        task_id = str(((submit_payload.get("output") or {}).get("task_id")) or submit_payload.get("task_id") or "").strip()
        if not task_id:
            manifest["failures"].append({"scene_id": scene_id, "error": f"Missing task_id in submit response: {submit_payload}"})
            continue

        deadline = time.time() + poll_timeout
        status_payload: dict[str, Any] | None = None
        while time.time() < deadline:
            status_payload = get_json(task_template.format(task_id=task_id), {"Authorization": f"Bearer {api_key}"})
            task_status = str(((status_payload.get("output") or {}).get("task_status")) or "").upper()
            if task_status in {"SUCCEEDED", "FAILED", "CANCELED"}:
                break
            time.sleep(poll_interval)

        if status_payload is None:
            manifest["failures"].append({"scene_id": scene_id, "task_id": task_id, "error": "Polling did not return a payload"})
            continue
        write_json(status_path, status_payload)
        task_status = str(((status_payload.get("output") or {}).get("task_status")) or "").upper()
        if task_status != "SUCCEEDED":
            manifest["failures"].append({"scene_id": scene_id, "task_id": task_id, "error": f"Task ended with status {task_status}"})
            continue
        video_url = resolve_video_url(status_payload)
        download_file(video_url, clip_path)
        manifest["clips"].append(
            {
                "scene_id": scene_id,
                "task_id": task_id,
                "clip_path": str(clip_path.resolve()),
                "video_url": video_url,
            }
        )

    if manifest["failures"]:
        write_json(project.route_b / "video_generation_manifest.json", manifest)
        raise StoryProjectError(f"Wan route failed for {len(manifest['failures'])} scene(s).")

    concat_path = project.route_b / "concat.txt"
    write_text(concat_path, "\n".join(f"file '{Path(item['clip_path']).as_posix()}'" for item in manifest["clips"]) + "\n")
    run_command(
        [
            ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c:v",
            str(config.get("video", {}).get("codec", "libx264")),
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(project.route_b / "output.mp4"),
        ]
    )
    write_json(project.route_b / "video_generation_manifest.json", manifest)
    return manifest


def mux_video_with_audio_and_subtitles(ffmpeg_path: str, video_path: Path, audio_path: Path, subtitles_path: Path, output_path: Path) -> None:
    escaped_subtitles = subtitles_path.resolve().as_posix().replace(":", "\\:").replace("'", r"\'")
    subtitle_filter = (
        f"subtitles='{escaped_subtitles}':"
        "force_style='FontName=Microsoft YaHei,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=28'"
    )
    run_command(
        [
            ffmpeg_path,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-vf",
            subtitle_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    )


def build_final_outputs(config: dict[str, Any], project: ProjectPaths) -> dict[str, Any]:
    ffmpeg_path = video_pipeline.ensure_dependency(config.get("ffmpeg", {}).get("path", "ffmpeg"))
    narration_audio = project.tts / "narration.wav"
    subtitles = project.tts / "subtitles.srt"
    route_a_video = project.route_a / "render" / "output.mp4"
    route_b_video = project.route_b / "output.mp4"
    route_a_final = project.final / "route_a_final.mp4"
    route_b_final = project.final / "route_b_final.mp4"

    if route_a_video.exists():
        mux_video_with_audio_and_subtitles(ffmpeg_path, route_a_video, narration_audio, subtitles, route_a_final)
    if route_b_video.exists():
        mux_video_with_audio_and_subtitles(ffmpeg_path, route_b_video, narration_audio, subtitles, route_b_final)

    manifest = {
        "narration_audio": str(narration_audio.resolve()),
        "subtitles": str(subtitles.resolve()),
        "route_a_final": str(route_a_final.resolve()) if route_a_final.exists() else "",
        "route_b_final": str(route_b_final.resolve()) if route_b_final.exists() else "",
    }
    write_json(project.final / "final_manifest.json", manifest)
    return manifest


def write_compare_report(project: ProjectPaths, scene_plan: dict[str, Any], route_a_enabled: bool, route_b_enabled: bool, final_manifest: dict[str, Any]) -> None:
    route_a_video = final_manifest.get("route_a_final") or ""
    route_b_video = final_manifest.get("route_b_final") or ""
    report = {
        "scene_count": scene_plan.get("scene_count"),
        "route_a": {
            "enabled": route_a_enabled,
            "video": route_a_video,
            "heuristic": "Static-image route stays more controllable on composition and subtitle timing, but motion remains synthetic.",
        },
        "route_b": {
            "enabled": route_b_enabled,
            "video": route_b_video,
            "heuristic": "Wan route usually feels more continuous and cinematic with the same narration track, but output is less deterministic.",
        },
        "recommended_default": "route_b" if route_b_video else "route_a",
    }
    write_json(project.compare / "report.json", report)


def command_run(args: argparse.Namespace, config: dict[str, Any]) -> int:
    project = build_project_paths(config, args.profile_url, args.project_slug, args.project_root)
    config_path = args.config.resolve() if args.config else None

    if not args.skip_ingest:
        ingest_cmd = [sys.executable, "scripts/douyin_pipeline.py", "run"]
        if config_path is not None:
            ingest_cmd.extend(["--config", str(config_path)])
        ingest_cmd.extend(["--profile-url", args.profile_url, "--output-dir", str(project.ingest)])
        run_command(ingest_cmd)

    if not args.skip_stt:
        audio_file = find_first(project.ingest / "audio", "*.mp3")
        stt_cmd = [sys.executable, "scripts/bailian_funasr.py"]
        if config_path is not None:
            stt_cmd.extend(["--config", str(config_path)])
        stt_cmd.extend(["run", "--local-file", str(audio_file), "--output-dir", str(project.stt), "--download-results"])
        run_command(stt_cmd)

    transcript_path = find_first(project.stt, "result_*.txt")
    transcript_text = transcript_path.read_text(encoding="utf-8").strip()

    summary_system, summary_user = build_summary_prompt(transcript_text, args.max_scenes)
    summary_payload = normalize_summary(chat_json(config, summary_system, summary_user), args.max_scenes)
    write_json(project.summary / "summary.json", summary_payload)

    rewrite_system, rewrite_user = build_rewrite_prompt(summary_payload, args.max_scenes)
    rewrite_payload = normalize_rewrite(chat_json(config, rewrite_system, rewrite_user), args.max_scenes)
    write_json(project.rewrite / "rewrite.json", rewrite_payload)

    character_bible = build_character_bible(rewrite_payload, summary_payload)
    scene_bible = build_scene_bible(rewrite_payload, summary_payload)
    write_json(project.rewrite / "character_bible.json", character_bible)
    write_json(project.rewrite / "scene_bible.json", scene_bible)

    tts_manifest, duration_map = synthesize_tts(config, project, rewrite_payload)
    write_json(project.tts / "tts_lines.json", {"items": tts_manifest["items"]})

    director_system, director_user = build_director_prompt(rewrite_payload, character_bible, scene_bible)
    director_payload = normalize_director_plan(chat_json(config, director_system, director_user))
    write_json(project.storyboard / "director_plan.json", director_payload)

    shot_continuity = build_shot_continuity(rewrite_payload, director_payload, character_bible, scene_bible)
    write_json(project.storyboard / "shot_continuity.json", shot_continuity)

    scene_plan = build_scene_plan(director_payload, rewrite_payload, duration_map, character_bible, scene_bible, shot_continuity)
    write_json(project.storyboard / "scene_plan.json", scene_plan)

    generation_note = {
        "status": "generation_disabled",
        "message": "Image and video generation are currently disabled. The pipeline now stops after storyboard output.",
        "stopped_after_stage": "06_storyboard",
    }
    write_json(project.route_a / "disabled.json", generation_note)
    write_json(project.route_b / "disabled.json", generation_note)
    write_json(
        project.final / "final_manifest.json",
        {
            "status": "skipped",
            "message": "Final mux skipped because image and video generation are disabled.",
            "route_a_final": "",
            "route_b_final": "",
        },
    )
    write_json(
        project.compare / "report.json",
        {
            "scene_count": scene_plan.get("scene_count"),
            "route_a": {
                "enabled": False,
                "video": "",
                "heuristic": "Route A skipped because generation is disabled.",
            },
            "route_b": {
                "enabled": False,
                "video": "",
                "heuristic": "Route B skipped because generation is disabled.",
            },
            "recommended_default": "none",
            "status": "skipped",
        },
    )
    print(f"Project root: {project.root}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = merge_config(args)
    try:
        if args.command == "run":
            return command_run(args, config)
        parser.error(f"Unsupported command: {args.command}")
    except StoryProjectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
