import { Fragment, useState } from "react";
import type { SourceResponse } from "../../api/types";
import { useUpdateSource, useDeleteSource } from "../../api/hooks";
import { safeHref } from "../../api/client";
import { formatRelativeTime, truncate } from "../../lib/format";
import SelectorsEditor from "./SelectorsEditor";

export type SourceFormData = {
  url: string;
  name: string;
  source_type: "rss" | "web" | "javascript";
  javascript: boolean;
};

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

function EditFormInline({
  form,
  onFormChange,
  onSubmit,
  onCancel,
  isPending,
}: {
  form: SourceFormData;
  onFormChange: (form: SourceFormData) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  return (
    <div className="rounded border border-rule bg-paper p-4 space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1">
            URL
          </label>
          <input
            type="url"
            value={form.url}
            onChange={(e) => onFormChange({ ...form, url: e.target.value })}
            placeholder="https://example.com/feed"
            className="w-full rounded-md border border-rule bg-paper px-2.5 py-2 text-sm text-ink placeholder:text-ink-4 focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1">
            Name (optional)
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => onFormChange({ ...form, name: e.target.value })}
            placeholder="My Blog"
            className="w-full rounded-md border border-rule bg-paper px-2.5 py-2 text-sm text-ink placeholder:text-ink-4 focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1">
            Type
          </label>
          <select
            value={form.source_type}
            onChange={(e) =>
              onFormChange({
                ...form,
                source_type: e.target.value as "rss" | "web" | "javascript",
              })
            }
            className="w-full rounded-md border border-rule bg-paper px-2.5 py-2 text-sm text-ink focus:border-accent focus:outline-none"
          >
            <option value="rss">RSS</option>
            <option value="web">Web</option>
            <option value="javascript">JavaScript</option>
          </select>
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer pb-2">
            <input
              type="checkbox"
              checked={form.javascript}
              onChange={(e) =>
                onFormChange({ ...form, javascript: e.target.checked })
              }
              className="accent-accent rounded-sm"
            />
            Requires JavaScript
          </label>
        </div>
      </div>
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={onSubmit}
          disabled={isPending || !form.url.trim()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-paper hover:bg-accent-hover disabled:opacity-50 transition-colors min-h-[44px]"
        >
          {isPending ? "Saving…" : "Update"}
        </button>
        <button
          onClick={onCancel}
          className="rounded-md border border-rule px-4 py-2 text-sm font-medium text-ink-3 hover:bg-paper-2 transition-colors min-h-[44px]"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function SourcesTable({
  sources,
  onEdit,
  editingKey,
  form,
  onFormChange,
  onFormSubmit,
  onFormCancel,
  formPending,
}: {
  sources: SourceResponse[];
  onEdit?: (source: SourceResponse) => void;
  editingKey?: string | null;
  form?: SourceFormData;
  onFormChange?: (form: SourceFormData) => void;
  onFormSubmit?: () => void;
  onFormCancel?: () => void;
  formPending?: boolean;
}) {
  const deleteSource = useDeleteSource();
  const updateSource = useUpdateSource();
  const [confirmKey, setConfirmKey] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

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

  const isEditing = (key: string) => editingKey === key && form && onFormChange && onFormSubmit && onFormCancel;

  return (
    <div>
      {/* Desktop table */}
      <table className="hidden md:table w-full table-fixed text-sm">
        <colgroup>
          <col className="w-[15%]" />
          <col className="w-[8%]" />
          <col className="w-[30%]" />
          <col className="w-[22%]" />
          <col className="w-[10%]" />
          <col className="w-[15%]" />
        </colgroup>
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
            <Fragment key={source.source_key}>
            <tr className="group">
              <td className="py-2.5 pr-4 font-medium text-ink truncate">
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
                  className="text-accent-text hover:underline text-xs truncate block"
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
                  {source.source_type !== "rss" && (
                    <button
                      onClick={() => setExpandedKey(expandedKey === source.source_key ? null : source.source_key)}
                      className={`text-xs transition-colors ${expandedKey === source.source_key ? "text-accent font-medium" : "text-ink-4 hover:text-ink"}`}
                    >
                      {expandedKey === source.source_key ? "Hide" : "Selectors"}
                    </button>
                  )}
                  {onEdit && (
                    <button
                      onClick={() => onEdit(source)}
                      className={`text-xs transition-colors ${editingKey === source.source_key ? "text-accent font-medium" : "text-ink-4 hover:text-ink"}`}
                    >
                      {editingKey === source.source_key ? "Editing" : "Edit"}
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
            {isEditing(source.source_key) && (
              <tr>
                <td colSpan={6} className="px-4 pb-3 pt-0">
                  <EditFormInline
                    form={form}
                    onFormChange={onFormChange}
                    onSubmit={onFormSubmit}
                    onCancel={onFormCancel}
                    isPending={formPending ?? false}
                  />
                </td>
              </tr>
            )}
            {expandedKey === source.source_key && !isEditing(source.source_key) && (
              <tr>
                <td colSpan={6} className="px-4 pb-3 pt-0">
                  <div className="rounded border border-rule bg-paper p-3">
                    <h3 className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 mb-2">
                      CSS Selectors
                    </h3>
                    <SelectorsEditor source={source} />
                  </div>
                </td>
              </tr>
            )}
            </Fragment>
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
              {source.source_type !== "rss" && (
                <button
                  onClick={() => setExpandedKey(expandedKey === source.source_key ? null : source.source_key)}
                  className={`text-xs ${expandedKey === source.source_key ? "text-accent font-medium" : "text-ink-4 hover:text-ink"}`}
                >
                  {expandedKey === source.source_key ? "Hide selectors" : "Selectors"}
                </button>
              )}
              {onEdit && (
                <button
                  onClick={() => onEdit(source)}
                  className={`text-xs ${editingKey === source.source_key ? "text-accent font-medium" : "text-ink-4 hover:text-ink"}`}
                >
                  {editingKey === source.source_key ? "Editing" : "Edit"}
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
            {isEditing(source.source_key) && (
              <div className="mt-2">
                <EditFormInline
                  form={form}
                  onFormChange={onFormChange}
                  onSubmit={onFormSubmit}
                  onCancel={onFormCancel}
                  isPending={formPending ?? false}
                />
              </div>
            )}
            {expandedKey === source.source_key && !isEditing(source.source_key) && (
              <div className="mt-2 rounded border border-rule bg-paper p-3">
                <h3 className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 mb-2">
                  CSS Selectors
                </h3>
                <SelectorsEditor source={source} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
