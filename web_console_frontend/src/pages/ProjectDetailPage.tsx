import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { FileTable } from "../components/FileTable";
import { FilePreviewPanel } from "../components/FilePreviewPanel";
import { MetricCard } from "../components/MetricCard";
import { SectionHeader } from "../components/SectionHeader";
import { StageCard } from "../components/StageCard";
import { StatusPill } from "../components/StatusPill";
import { useAsyncValue } from "../hooks/useAsyncValue";
import { fetchFileContent, fetchProject, fetchProjectFiles } from "../lib/api";
import type { ArtifactFile } from "../lib/types";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const { data, loading, error } = useAsyncValue(() => fetchProject(projectId), [projectId]);
  const detail = data;
  const [selectedStage, setSelectedStage] = useState<string | undefined>(undefined);
  const [selectedFile, setSelectedFile] = useState<ArtifactFile | null>(null);
  const filesLoader = useMemo(() => () => fetchProjectFiles(projectId, selectedStage), [projectId, selectedStage]);
  const filesState = useAsyncValue(filesLoader, [filesLoader]);
  const previewState = useAsyncValue(
    () =>
      selectedFile && (selectedFile.preview_type === "json" || selectedFile.preview_type === "text")
        ? fetchFileContent(projectId, selectedFile.relative_path)
        : Promise.resolve(null),
    [projectId, selectedFile?.relative_path],
  );

  return (
    <div className="page-stack">
      <section className="content-card">
        {loading ? <p>正在加载项目...</p> : null}
        {error ? <p className="error-copy">{error}</p> : null}
        {detail ? (
          <>
            <div className="detail-hero">
              <div>
                <div className="section-eyebrow">项目详情</div>
                <h1>{detail.slug}</h1>
                <p>{detail.source_url ?? "暂无源链接"}</p>
              </div>
              <StatusPill status={detail.latest_status} />
            </div>
            <div className="metrics-grid">
              <MetricCard label="运行标识" value={detail.run_key} />
              <MetricCard label="阶段数量" value={detail.stages.length} />
              <MetricCard label="项目目录" value={detail.run_root} />
            </div>
          </>
        ) : null}
      </section>

      <section className="content-card">
        <SectionHeader
          eyebrow="阶段总览"
          title="流水线节点"
          body="点击阶段卡片可以过滤下面的文件列表。"
        />
        <div className="stage-grid">
          {detail?.stages.map((stage) => (
            <button
              key={stage.stage_id}
              type="button"
              className={`stage-button ${selectedStage === stage.stage_id ? "is-active" : ""}`}
              onClick={() => {
                setSelectedFile(null);
                setSelectedStage((current) => (current === stage.stage_id ? undefined : stage.stage_id));
              }}
            >
              <StageCard stage={stage} />
            </button>
          ))}
        </div>
      </section>

      <div className="detail-grid">
        <section className="content-card">
          <SectionHeader
            eyebrow="产物浏览"
            title={selectedStage ? `${selectedStage} 文件` : "全部文件"}
            body="点击文件即可在右侧查看文本内容，适合检查转写、总结、分镜、配置和日志。"
          />
          {filesState.loading ? <p>正在加载文件...</p> : null}
          {filesState.error ? <p className="error-copy">{filesState.error}</p> : null}
          {filesState.data ? (
            <FileTable
              files={filesState.data}
              selectedPath={selectedFile?.relative_path}
              onSelect={setSelectedFile}
            />
          ) : null}
        </section>

        <section className="content-card">
          <FilePreviewPanel
            projectId={projectId}
            file={selectedFile}
            preview={previewState.data}
            loading={previewState.loading}
            error={previewState.error}
          />
        </section>
      </div>
    </div>
  );
}
