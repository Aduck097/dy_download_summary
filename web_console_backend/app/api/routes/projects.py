import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from web_console_backend.app.schemas.project import ArtifactFile, ProjectDetail, ProjectListItem, ProjectStage
from web_console_backend.app.services.project_index import (
    discover_project_runs,
    get_project_detail,
    get_project_files,
    normalize_stage_index,
)


router = APIRouter()


@router.get("", response_model=list[ProjectListItem])
def list_projects() -> list[ProjectListItem]:
    return discover_project_runs()


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str) -> ProjectDetail:
    detail = get_project_detail(project_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return detail


@router.get("/{project_id}/stages", response_model=list[ProjectStage])
def get_project_stages(project_id: str) -> list[ProjectStage]:
    detail = get_project_detail(project_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return normalize_stage_index(detail.run_root)


@router.get("/{project_id}/files", response_model=list[ArtifactFile])
def get_files(project_id: str, stage_id: str | None = Query(default=None)) -> list[ArtifactFile]:
    detail = get_project_detail(project_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return get_project_files(detail.run_root, stage_id=stage_id)


@router.get("/{project_id}/file-content")
def get_file_content(project_id: str, path: str = Query(...)) -> dict:
    detail = get_project_detail(project_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    root = Path(detail.run_root).resolve()
    target = (root / path).resolve()
    if not target.exists() or not target.is_file() or root not in target.parents:
        raise HTTPException(status_code=404, detail="File not found")
    suffix = target.suffix.lower()
    if suffix == ".json":
        return {
            "kind": "json",
            "path": path,
            "content": json.loads(target.read_text(encoding="utf-8")),
        }
    if suffix in {".txt", ".srt", ".md", ".log"}:
        return {
            "kind": "text",
            "path": path,
            "content": target.read_text(encoding="utf-8", errors="replace"),
        }
    return {
        "kind": "unsupported",
        "path": path,
        "message": "Preview is only available for text and JSON files.",
    }


@router.get("/{project_id}/file-raw")
def get_file_raw(project_id: str, path: str = Query(...)) -> FileResponse:
    detail = get_project_detail(project_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    root = Path(detail.run_root).resolve()
    target = (root / path).resolve()
    if not target.exists() or not target.is_file() or root not in target.parents:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)
