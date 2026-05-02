import { useState } from "react";
import type { SourceResponse, SourceUpdateRequest } from "../../api/types";
import { useUpdateSource, useDeleteSource } from "../../api/hooks";
import { safeHref } from "../../api/client";
import { truncate } from "../../lib/format";

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
