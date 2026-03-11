export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export interface ProjectListItem {
  project_id: string;
  slug: string;
  latest_run_key: string | null;
  latest_status: StageStatus | string;
  source_url: string | null;
  updated_at: string | null;
}

export interface ProjectStage {
  stage_id: string;
  label: string;
  status: StageStatus | string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  artifact_count: number;
  primary_files: string[];
  error_message: string | null;
  log_path: string | null;
}

export interface ProjectDetail {
  project_id: string;
  slug: string;
  run_key: string;
  run_root: string;
  source_url: string | null;
  latest_status: StageStatus | string;
  stages: ProjectStage[];
}

export interface ArtifactFile {
  relative_path: string;
  name: string;
  extension: string;
  size_bytes: number;
  updated_at: string;
  preview_type: string;
}

export interface FilePreviewPayload {
  kind: "json" | "text" | "unsupported";
  path: string;
  content?: unknown;
  message?: string;
}
