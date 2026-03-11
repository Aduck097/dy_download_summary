import { formatDateTime } from "../lib/format";
import type { ProjectStage } from "../lib/types";
import { StatusPill } from "./StatusPill";

interface StageCardProps {
  stage: ProjectStage;
}

export function StageCard({ stage }: StageCardProps) {
  return (
    <article className="stage-card">
      <div className="stage-card-top">
        <div>
          <div className="stage-label">{stage.label}</div>
          <div className="stage-id">{stage.stage_id}</div>
        </div>
        <StatusPill status={stage.status} />
      </div>
      <div className="stage-meta">
        <span>{stage.artifact_count} 个文件</span>
        <span>{formatDateTime(stage.ended_at)}</span>
      </div>
      <div className="chip-row">
        {stage.primary_files.map((file) => (
          <span key={file} className="file-chip">
            {file}
          </span>
        ))}
      </div>
      {stage.error_message ? <p className="error-copy">{stage.error_message}</p> : null}
    </article>
  );
}
