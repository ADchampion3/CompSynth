import { Link } from "react-router-dom";
import type { CrawlRunSourceResponse, SourceHealthResponse } from "../../api/types";
import { truncate } from "../../lib/format";

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
    <section>
      <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-3 mb-3">
        Source Health
      </h2>

      {failedSources.length > 0 && (
        <div className="rounded-md bg-err-muted p-3 mb-3">
          <div className="text-sm font-medium text-err mb-1.5">
            {failedSources.length} source(s) failed in last run
          </div>
          <ul className="space-y-1">
            {failedSources.map((s) => (
              <li key={s.source_key} className="text-xs text-err/80">
                <span className="font-medium">{s.source_key}</span>
                {s.error_text && ` — ${truncate(s.error_text, 80)}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {unhealthySources.length > 0 && (
        <div className="rounded-md bg-warn-muted p-3">
          <div className="text-sm font-medium text-warn mb-1.5">
            Unhealthy sources
          </div>
          <ul className="space-y-1">
            {unhealthySources.map((s) => (
              <li key={s.source_key} className="text-xs text-warn/80">
                <span className="font-medium">{s.source_key}</span>
                {" — "}
                {s.status === "stale"
                  ? `${s.recent_zero_days} zero-result days`
                  : s.last_error ?? "unknown error"}
              </li>
            ))}
          </ul>
          <Link
            to="/sources"
            className="mt-2 inline-block text-xs text-accent-text hover:underline"
          >
            View all sources →
          </Link>
        </div>
      )}
    </section>
  );
}
