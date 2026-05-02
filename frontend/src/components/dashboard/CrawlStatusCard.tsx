import type { CrawlRunResponse } from "../../api/types";
import { formatRelativeTime } from "../../lib/format";

const STATUS_COLORS: Record<string, string> = {
  success: "bg-green-100 text-green-800",
  partial: "bg-yellow-100 text-yellow-800",
  failed: "bg-red-100 text-red-800",
  running: "bg-blue-100 text-blue-800",
  timed_out: "bg-red-100 text-red-800",
};

export default function CrawlStatusCard({ run }: { run: CrawlRunResponse }) {
  return (
    <div className="rounded border border-gray-200 p-4 space-y-2">
      <div className="flex items-center gap-2">
        <span
          className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[run.status] ?? "bg-gray-100 text-gray-800"}`}
        >
          {run.status}
        </span>
        <span className="text-sm text-gray-500">
          {formatRelativeTime(run.started_at)}
        </span>
      </div>
      <div className="text-sm text-gray-700">
        {run.new_items} new items
        {run.scope === "single" ? " (single source)" : " (all sources)"}
      </div>
      {run.error_text && (
        <div className="text-sm text-red-600">{run.error_text}</div>
      )}
    </div>
  );
}
