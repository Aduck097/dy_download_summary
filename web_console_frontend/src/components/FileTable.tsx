import { formatBytes, formatDateTime } from "../lib/format";
import type { ArtifactFile } from "../lib/types";

interface FileTableProps {
  files: ArtifactFile[];
  selectedPath?: string;
  onSelect?: (file: ArtifactFile) => void;
}

export function FileTable({ files, selectedPath, onSelect }: FileTableProps) {
  return (
    <div className="file-table">
      <div className="file-table-head">
        <span>文件</span>
        <span>类型</span>
        <span>大小</span>
        <span>更新时间</span>
      </div>
      {files.map((file) => (
        <button
          key={file.relative_path}
          type="button"
          className={`file-row ${selectedPath === file.relative_path ? "is-active" : ""}`}
          onClick={() => onSelect?.(file)}
        >
          <span>{file.relative_path}</span>
          <span>{file.preview_type}</span>
          <span>{formatBytes(file.size_bytes)}</span>
          <span>{formatDateTime(file.updated_at)}</span>
        </button>
      ))}
    </div>
  );
}
