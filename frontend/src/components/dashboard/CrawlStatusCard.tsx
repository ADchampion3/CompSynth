import type { CrawlRunResponse } from "../../api/types";
import { formatRelativeTime } from "../../lib/format";

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  success: { label: "Success", cls: "text-ok" },
  partial: { label: "Partial", cls: "text-warn" },
  failed: { label: "Failed", cls: "text-err" },
  running: { label: "Running", cls: "text-accent" },
  timed_out: { label: "Timed out", cls: "text-err" },
};

export default function CrawlStatusCard({ run }: { run: CrawlRunResponse }) {
  const status = STATUS_MAP[run.status] ?? { label: run.status, cls: "text-ink-3" };

  return (
    <div className="flex items-baseline gap-3 text-sm">
      <span className={`font-medium ${status.cls}`}>{status.label}</span>
      <span className="text-ink-3">
        {run.new_items} new{run.scope === "single" ? " (single)" : ""}
      </span>
      <span className="text-ink-4">{formatRelativeTime(run.started_at)}</span>
      {run.error_text && (
        <span className="text-err text-xs">{run.error_text}</span>
      )}
    </div>
  );
}
