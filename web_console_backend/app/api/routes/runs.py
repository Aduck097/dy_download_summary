from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class RunRequest(BaseModel):
    profile_url: str | None = None
    project_root: str | None = None
    max_scenes: int = 4


@router.post("")
def start_run(payload: RunRequest) -> dict:
    raise HTTPException(status_code=501, detail="Run execution is scaffolded but not implemented yet")


@router.post("/from-stt")
def start_run_from_stt(payload: RunRequest) -> dict:
    raise HTTPException(status_code=501, detail="Run-from-STT execution is scaffolded but not implemented yet")


@router.post("/projects/{project_id}/rerun")
def rerun_project(project_id: str) -> dict:
    raise HTTPException(status_code=501, detail=f"Rerun API for {project_id} is scaffolded but not implemented yet")
