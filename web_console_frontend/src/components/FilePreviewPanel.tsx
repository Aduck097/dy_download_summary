import { rawFileUrl } from "../lib/api";
import type { ArtifactFile, FilePreviewPayload } from "../lib/types";

interface FilePreviewPanelProps {
  projectId: string;
  file: ArtifactFile | null;
  preview: FilePreviewPayload | null;
  loading: boolean;
  error: string | null;
}

export function FilePreviewPanel({ projectId, file, preview, loading, error }: FilePreviewPanelProps) {
  if (!file) {
    return (
      <div className="preview-panel preview-empty">
        <div className="section-eyebrow">文件预览</div>
        <h3>选择一个文件</h3>
        <p>当前以文本内容预览为主，适合查看 JSON、转写、分镜和日志。</p>
      </div>
    );
  }

  const rawUrl = rawFileUrl(projectId, file.relative_path);

  return (
    <div className="preview-panel">
      <div className="preview-header">
        <div>
          <div className="section-eyebrow">文件预览</div>
          <h3>{file.name}</h3>
          <p>{file.relative_path}</p>
        </div>
        <a className="preview-link" href={rawUrl} target="_blank" rel="noreferrer">
          打开原文件
        </a>
      </div>

      {loading ? <p>正在加载预览...</p> : null}
      {error ? <p className="error-copy">{error}</p> : null}

      {!loading && !error && file.preview_type === "image" ? <img className="preview-image" src={rawUrl} alt={file.name} /> : null}
      {!loading && !error && preview?.kind === "json" ? (
        <pre className="code-panel">{JSON.stringify(preview.content, null, 2)}</pre>
      ) : null}
      {!loading && !error && preview?.kind === "text" ? <pre className="code-panel">{String(preview.content ?? "")}</pre> : null}
      {!loading && !error && (file.preview_type === "audio" || file.preview_type === "video") ? (
        <div className="preview-empty">
          <p>当前不在页面内预览这类媒体文件，你可以通过“打开原文件”单独查看。</p>
        </div>
      ) : null}
      {!loading && !error && preview?.kind === "unsupported" ? (
        <div className="preview-empty">
          <p>{preview.message}</p>
        </div>
      ) : null}
    </div>
  );
}
