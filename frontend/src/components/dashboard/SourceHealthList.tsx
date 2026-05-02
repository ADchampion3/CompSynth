import { Link } from "react-router-dom";
import type { CrawlRunSourceResponse, SourceHealthResponse } from "../../api/types";
import { truncate } from "../../lib/format";

const STATUS_COLORS: Record<string, string> = {
  failed: "text-red-600",
  stale: "text-yellow-600",
};

export default function SourceHealthList({
  failedSources,
  unhealthySources,
}: {
  failedSources: CrawlRunSourceResponse[];
  unhealthySources: SourceHealthResponse[];
}) {
  if (failedSources.length === 0 && unhealthySources.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-semibold text-gray-700">Source Health</h2>
      {failedSources.length > 0 && (
        <div className="rounded border border-red-200 bg-red-50 p-3">
          <div className="text-sm font-medium text-red-800 mb-1">
            {failedSources.length} source(s) failed in last run
          </div>
          <ul className="space-y-1">
            {failedSources.map((s) => (
              <li key={s.source_key} className="text-xs text-red-700">
                <span className="font-medium">{s.source_key}</span>
                {s.error_text && `: ${truncate(s.error_text, 80)}`}
              </li>
            ))}
          </ul>
        </div>
      )}
      {unhealthySources.length > 0 && (
        <div className="rounded border border-yellow-200 bg-yellow-50 p-3">
          <div className="text-sm font-medium text-yellow-800 mb-1">
            Unhealthy sources
          </div>
          <ul className="space-y-1">
            {unhealthySources.map((s) => (
              <li key={s.source_key} className="text-xs text-yellow-700">
                <span className={`font-medium ${STATUS_COLORS[s.status] ?? ""}`}>
                  {s.source_key}
                </span>
                {" — "}
                {s.status === "stale"
                  ? `${s.recent_zero_days} zero-result days`
                  : s.last_error ?? "unknown error"}
              </li>
            ))}
          </ul>
          <Link
            to="/sources"
            className="mt-2 inline-block text-xs text-blue-600 hover:underline"
          >
            View all sources →
          </Link>
        </div>
      )}
    </div>
  );
}
