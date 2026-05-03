import { useState } from "react";
import type { SourceResponse } from "../../api/types";
import { useUpdateSource, useDeleteSource } from "../../api/hooks";
import { safeHref } from "../../api/client";
import { formatRelativeTime, truncate } from "../../lib/format";

const STATUS_CFG: Record<string, { bg: string; text: string; label: string }> = {
  healthy: { bg: "bg-ok-muted", text: "text-ok", label: "Healthy" },
  stale: { bg: "bg-warn-muted", text: "text-warn", label: "Stale" },
  failed: { bg: "bg-err-muted", text: "text-err", label: "Failed" },
};

function CrawlHealthBadge({ source }: { source: SourceResponse }) {
  if (source.crawl_status === null) {
    return <span className="text-xs text-ink-4">Not yet crawled</span>;
  }

  const cfg = STATUS_CFG[source.crawl_status] ?? STATUS_CFG.healthy;

  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-1.5">
        <span className={`rounded-sm ${cfg.bg} px-1.5 py-0.5 text-[0.6875rem] font-medium ${cfg.text}`}>
          {cfg.label}
        </span>
        <span className="text-xs text-ink-4">
          {formatRelativeTime(source.last_crawled_at)}
        </span>
      </div>
      {source.last_new_item_count !== null && source.last_new_item_count > 0 && (
        <div className="text-[0.625rem] text-ink-4">
          {source.last_new_item_count} new item{source.last_new_item_count !== 1 ? "s" : ""}
        </div>
      )}
      {source.recent_zero_days !== null && source.recent_zero_days > 0 && (
        <div className="text-[0.625rem] text-warn">
          {source.recent_zero_days} zero-result day{source.recent_zero_days !== 1 ? "s" : ""}
        </div>
      )}
      {source.last_error && (
        <div className="text-[0.625rem] text-err truncate max-w-[200px]" title={source.last_error}>
          {truncate(source.last_error, 60)}
        </div>
      )}
    </div>
  );
}

export default function SourcesTable({
  sources,
  onEdit,
}: {
  sources: SourceResponse[];
  onEdit?: (source: SourceResponse) => void;
}) {
  const deleteSource = useDeleteSource();
  const updateSource = useUpdateSource();
  const [confirmKey, setConfirmKey] = useState<string | null>(null);

  const toggleEnabled = (source: SourceResponse) => {
    updateSource.mutate({
      key: source.source_key,
      enabled: !source.enabled,
    });
  };

  const handleDelete = (key: string) => {
    if (confirmKey === key) {
      deleteSource.mutate(key);
      setConfirmKey(null);
    } else {
      setConfirmKey(key);
    }
  };

  return (
    <div className="overflow-auto">
      {/* Desktop table */}
      <table className="hidden md:table w-full text-sm">
        <thead>
          <tr className="border-b border-rule text-left">
            <th className="pb-2 pr-4 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              Name
            </th>
            <th className="pb-2 pr-4 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              Type
            </th>
            <th className="pb-2 pr-4 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              URL
            </th>
            <th className="pb-2 pr-4 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              Last crawl
            </th>
            <th className="pb-2 pr-4 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              Status
            </th>
            <th className="pb-2 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 text-right">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {sources.map((source) => (
            <tr key={source.source_key} className="group">
              <td className="py-2.5 pr-4 font-medium text-ink">
                {source.name ?? source.source_key}
              </td>
              <td className="py-2.5 pr-4">
                <span className="rounded-sm bg-paper-3 px-1.5 py-0.5 text-[0.6875rem] font-medium text-ink-3">
                  {source.source_type}
                </span>
              </td>
              <td className="py-2.5 pr-4">
                <a
                  href={safeHref(source.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-text hover:underline text-xs"
                  title={source.url}
                >
                  {truncate(source.url, 50)}
                </a>
              </td>
              <td className="py-2.5 pr-4">
                <CrawlHealthBadge source={source} />
              </td>
              <td className="py-2.5 pr-4">
                <button
                  onClick={() => toggleEnabled(source)}
                  className="cursor-pointer"
                >
                  {source.enabled ? (
                    <span className="rounded-sm bg-ok-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-ok">
                      Active
                    </span>
                  ) : (
                    <span className="rounded-sm bg-err-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-err">
                      Disabled
                    </span>
                  )}
                </button>
              </td>
              <td className="py-2.5 text-right">
                <div className="flex items-center justify-end gap-2">
                  {onEdit && (
                    <button
                      onClick={() => onEdit(source)}
                      className="text-xs text-ink-4 hover:text-ink transition-colors"
                    >
                      Edit
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(source.source_key)}
                    className={`text-xs transition-colors ${
                      confirmKey === source.source_key
                        ? "text-err font-medium"
                        : "text-ink-4 hover:text-err"
                    }`}
                  >
                    {confirmKey === source.source_key ? "Confirm?" : "Delete"}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile card list */}
      <div className="md:hidden divide-y divide-rule">
        {sources.map((source) => (
          <div key={source.source_key} className="py-3">
            <div className="flex items-center justify-between">
              <span className="font-medium text-sm text-ink">
                {source.name ?? source.source_key}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleEnabled(source)}
                  className="cursor-pointer"
                >
                  {source.enabled ? (
                    <span className="rounded-sm bg-ok-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-ok">
                      Active
                    </span>
                  ) : (
                    <span className="rounded-sm bg-err-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-err">
                      Disabled
                    </span>
                  )}
                </button>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="rounded-sm bg-paper-3 px-1.5 py-0.5 text-[0.6875rem] font-medium text-ink-3">
                {source.source_type}
              </span>
            </div>
            <a
              href={safeHref(source.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block text-xs text-accent-text hover:underline truncate"
            >
              {source.url}
            </a>
            <div className="mt-1.5">
              <CrawlHealthBadge source={source} />
            </div>
            <div className="flex items-center gap-3 mt-2">
              {onEdit && (
                <button
                  onClick={() => onEdit(source)}
                  className="text-xs text-ink-4 hover:text-ink"
                >
                  Edit
                </button>
              )}
              <button
                onClick={() => handleDelete(source.source_key)}
                className={`text-xs ${
                  confirmKey === source.source_key
                    ? "text-err font-medium"
                    : "text-ink-4 hover:text-err"
                }`}
              >
                {confirmKey === source.source_key ? "Confirm?" : "Delete"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
