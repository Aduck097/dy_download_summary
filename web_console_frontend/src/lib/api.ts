import type { ArtifactFile, FilePreviewPayload, ProjectDetail, ProjectListItem } from "./types";

const API_BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchProjects() {
  return request<ProjectListItem[]>("/projects");
}

export function fetchProject(projectId: string) {
  return request<ProjectDetail>(`/projects/${projectId}`);
}

export function fetchProjectFiles(projectId: string, stageId?: string) {
  const query = stageId ? `?stage_id=${encodeURIComponent(stageId)}` : "";
  return request<ArtifactFile[]>(`/projects/${projectId}/files${query}`);
}

export function fetchConfig() {
  return request<Record<string, unknown>>("/config");
}

export function validateConfig(data: Record<string, unknown>) {
  return request<{ valid: boolean; errors: string[] }>("/config/validate", {
    method: "POST",
    body: JSON.stringify({ data }),
  });
}

export function saveConfig(data: Record<string, unknown>) {
  return request<{ status: string }>("/config", {
    method: "PUT",
    body: JSON.stringify({ data }),
  });
}

export function fetchFileContent(projectId: string, relativePath: string) {
  return request<FilePreviewPayload>(
    `/projects/${projectId}/file-content?path=${encodeURIComponent(relativePath)}`,
  );
}

export function rawFileUrl(projectId: string, relativePath: string) {
  return `${API_BASE}/projects/${projectId}/file-raw?path=${encodeURIComponent(relativePath)}`;
}
