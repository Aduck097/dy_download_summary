import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from web_console_backend.app.core.config import get_settings
from web_console_backend.app.schemas.project import ArtifactFile, ProjectDetail, ProjectListItem, ProjectStage


STAGE_ORDER: list[tuple[str, str]] = [
    ("01_ingest", "Ingest"),
    ("02_stt", "STT"),
    ("03_summary", "Summary"),
    ("04_rewrite", "Rewrite"),
    ("05_tts", "TTS"),
    ("06_storyboard", "Storyboard"),
    ("07_route_a_qwen_ffmpeg", "Route A"),
    ("08_route_b_wan_i2v", "Route B"),
    ("09_final", "Final"),
    ("10_compare", "Compare"),
]

PRIMARY_FILES: dict[str, list[str]] = {
    "01_ingest": ["manifest.json"],
    "02_stt": ["result_1.txt", "result_1.srt", "result_1.timeline.json"],
    "03_summary": ["summary.json"],
    "04_rewrite": ["rewrite.json", "character_bible.json", "scene_bible.json"],
    "05_tts": ["narration.wav", "subtitles.srt", "tts_manifest.json"],
    "06_storyboard": ["shot_continuity.json", "director_plan.json", "scene_plan.json"],
    "07_route_a_qwen_ffmpeg": ["image_generation_manifest.json", "render/output.mp4"],
    "08_route_b_wan_i2v": ["video_generation_manifest.json", "output.mp4"],
    "09_final": ["final_manifest.json", "route_a_final.mp4", "route_b_final.mp4"],
    "10_compare": ["report.json"],
}


@dataclass(slots=True)
class ResolvedProject:
    slug: str
    run_key: str
    run_root: Path


def _settings_runs_dir() -> Path:
    return get_settings().runs_dir


def _parse_iso_like(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def _resolve_project(project_id: str) -> ResolvedProject | None:
    runs_dir = _settings_runs_dir()
    if "__" not in project_id:
        return None
    slug, run_key = project_id.split("__", 1)
    run_root = runs_dir / slug / run_key
    if not run_root.exists():
        return None
    return ResolvedProject(slug=slug, run_key=run_key, run_root=run_root)


def _infer_source_url(run_root: Path) -> str | None:
    ingest_manifest = run_root / "01_ingest" / "manifest.json"
    if not ingest_manifest.exists():
        return None
    try:
        payload = json.loads(ingest_manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    source = payload.get("source") or {}
    value = source.get("profile_url")
    return value if isinstance(value, str) and value else None


def discover_project_runs() -> list[ProjectListItem]:
    runs_dir = _settings_runs_dir()
    items: list[ProjectListItem] = []
    if not runs_dir.exists():
        return items
    for project_dir in sorted(runs_dir.iterdir(), reverse=True):
        if not project_dir.is_dir():
            continue
        run_dirs = sorted([path for path in project_dir.iterdir() if path.is_dir()], key=lambda p: p.name, reverse=True)
        if not run_dirs:
            continue
        latest_run = run_dirs[0]
        detail = ProjectDetail(
            project_id=f"{project_dir.name}__{latest_run.name}",
            slug=project_dir.name,
            run_key=latest_run.name,
            run_root=str(latest_run.resolve()),
            source_url=_infer_source_url(latest_run),
            latest_status=_summarize_run_status(latest_run),
            stages=normalize_stage_index(str(latest_run.resolve())),
        )
        items.append(
            ProjectListItem(
                project_id=detail.project_id,
                slug=detail.slug,
                latest_run_key=detail.run_key,
                latest_status=detail.latest_status,
                source_url=detail.source_url,
                updated_at=_parse_iso_like(latest_run),
            )
        )
    return items


def _summarize_run_status(run_root: Path) -> str:
    stages = normalize_stage_index(str(run_root.resolve()))
    if any(stage.status == "failed" for stage in stages):
        return "failed"
    if any(stage.status == "running" for stage in stages):
        return "running"
    if stages and all(stage.status in {"completed", "skipped"} for stage in stages):
        return "completed"
    return "pending"


def _artifact_count(stage_root: Path) -> int:
    if not stage_root.exists():
        return 0
    return sum(1 for path in stage_root.rglob("*") if path.is_file())


def _status_for_stage(stage_root: Path, stage_id: str) -> str:
    generation_stage_ids = {"07_route_a_qwen_ffmpeg", "08_route_b_wan_i2v", "09_final", "10_compare"}
    storyboard_root = stage_root.parent / "06_storyboard"
    if (stage_root / "disabled.json").exists():
        return "skipped"
    if stage_id == "09_final":
        manifest_path = stage_root / "final_manifest.json"
        if manifest_path.exists():
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                payload = {}
            if payload.get("status") == "skipped":
                return "skipped"
    if stage_id == "10_compare":
        report_path = stage_root / "report.json"
        if report_path.exists():
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                payload = {}
            if payload.get("status") == "skipped":
                return "skipped"
    if not stage_root.exists():
        if stage_id in generation_stage_ids and storyboard_root.exists() and _artifact_count(storyboard_root) > 0:
            return "skipped"
        return "pending"
    if stage_id == "09_final" and not any((stage_root / name).exists() for name in ("route_a_final.mp4", "route_b_final.mp4")):
        return "running"
    return "completed" if _artifact_count(stage_root) > 0 else "running"


def normalize_stage_index(run_root: str) -> list[ProjectStage]:
    root = Path(run_root)
    stages: list[ProjectStage] = []
    for stage_id, label in STAGE_ORDER:
        stage_root = root / stage_id
        primary_files = [
            str((stage_root / rel_path).relative_to(root))
            for rel_path in PRIMARY_FILES.get(stage_id, [])
            if (stage_root / rel_path).exists()
        ]
        updated_at = _parse_iso_like(stage_root)
        stages.append(
            ProjectStage(
                stage_id=stage_id,
                label=label,
                status=_status_for_stage(stage_root, stage_id),
                ended_at=updated_at,
                artifact_count=_artifact_count(stage_root),
                primary_files=primary_files,
            )
        )
    return stages


def get_project_detail(project_id: str) -> ProjectDetail | None:
    resolved = _resolve_project(project_id)
    if resolved is None:
        return None
    return ProjectDetail(
        project_id=project_id,
        slug=resolved.slug,
        run_key=resolved.run_key,
        run_root=str(resolved.run_root.resolve()),
        source_url=_infer_source_url(resolved.run_root),
        latest_status=_summarize_run_status(resolved.run_root),
        stages=normalize_stage_index(str(resolved.run_root.resolve())),
    )


def _preview_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return "json"
    if suffix in {".txt", ".srt", ".md", ".log"}:
        return "text"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    if suffix in {".wav", ".mp3", ".m4a"}:
        return "audio"
    if suffix in {".mp4", ".mov", ".webm"}:
        return "video"
    return "binary"


def get_project_files(run_root: str, stage_id: str | None = None) -> list[ArtifactFile]:
    root = Path(run_root)
    base = root / stage_id if stage_id else root
    if not base.exists():
        return []
    files: list[ArtifactFile] = []
    for path in sorted([item for item in base.rglob("*") if item.is_file()]):
        stat = path.stat()
        files.append(
            ArtifactFile(
                relative_path=str(path.relative_to(root)).replace("\\", "/"),
                name=path.name,
                extension=path.suffix.lower(),
                size_bytes=stat.st_size,
                updated_at=datetime.fromtimestamp(stat.st_mtime),
                preview_type=_preview_type(path),
            )
        )
    return files
