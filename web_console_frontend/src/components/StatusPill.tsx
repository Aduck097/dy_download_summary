import type { StageStatus } from "../lib/types";

interface StatusPillProps {
  status: StageStatus | string;
}

export function StatusPill({ status }: StatusPillProps) {
  return <span className={`status-pill status-${status}`}>{status}</span>;
}
