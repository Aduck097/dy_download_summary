from datetime import datetime

from pydantic import BaseModel, Field


class ProjectListItem(BaseModel):
    project_id: str
    slug: str
    latest_run_key: str | None = None
    latest_status: str
    source_url: str | None = None
    updated_at: datetime | None = None


class ProjectStage(BaseModel):
    stage_id: str
    label: str
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    artifact_count: int = 0
    primary_files: list[str] = Field(default_factory=list)
    error_message: str | None = None
    log_path: str | None = None


class ArtifactFile(BaseModel):
    relative_path: str
    name: str
    extension: str
    size_bytes: int
    updated_at: datetime
    preview_type: str


class ProjectDetail(BaseModel):
    project_id: str
    slug: str
    run_key: str
    run_root: str
    source_url: str | None = None
    latest_status: str
    stages: list[ProjectStage] = Field(default_factory=list)
