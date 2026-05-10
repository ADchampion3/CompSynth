import { useState } from "react";
import type { SourceResponse } from "../../api/types";
import {
  useSources,
  useImportYaml,
  useExportYaml,
  useCreateSource,
  useUpdateSource,
} from "../../api/hooks";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import ErrorCard from "../ui/ErrorCard";
import { SkeletonTable } from "../ui/LoadingSkeleton";
import EmptyState from "../ui/EmptyState";
import SourcesTable from "./SourcesTable";

type SourceFormData = {
  url: string;
  name: string;
  source_type: "rss" | "web" | "javascript";
  javascript: boolean;
};

const emptyForm: SourceFormData = {
  url: "",
  name: "",
  source_type: "web",
  javascript: false,
};

export default function SourcesPage() {
  const { data, isLoading, error } = useSources();
  const importYaml = useImportYaml();
  const exportYaml = useExportYaml();
  const createSource = useCreateSource();
  const updateSource = useUpdateSource();
  useDocumentTitle("Sources");

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<SourceResponse | null>(null);
  const [form, setForm] = useState<SourceFormData>(emptyForm);

  const openAdd = () => {
    setEditing(null);
    setForm(emptyForm);
    setShowForm(true);
  };

  const openEdit = (source: SourceResponse) => {
    setEditing(source);
    setForm({
      url: source.url,
      name: source.name ?? "",
      source_type: source.source_type as "rss" | "web" | "javascript",
      javascript: source.javascript,
    });
    setShowForm(true);
  };

  const cancel = () => {
    setShowForm(false);
    setEditing(null);
    setForm(emptyForm);
  };

  const submit = () => {
    if (!form.url.trim()) return;
    if (editing) {
      updateSource.mutate(
        {
          key: editing.source_key,
          url: form.url.trim(),
          name: form.name.trim() || null,
          source_type: form.source_type,
          javascript: form.javascript,
        },
        { onSuccess: cancel },
      );
    } else {
      createSource.mutate(
        {
          source_type: form.source_type,
          url: form.url.trim(),
          name: form.name.trim() || undefined,
          javascript: form.javascript,
        },
        { onSuccess: cancel },
      );
    }
  };

  const isPending = createSource.isPending || updateSource.isPending;

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      <div className="flex items-start justify-between gap-4 mb-6">
        <h1 className="font-display text-2xl md:text-3xl font-bold text-ink">
          Sources
        </h1>
        <div className="flex items-center gap-2">
          <button
            onClick={openAdd}
            className="shrink-0 rounded-md bg-accent px-4 py-2 text-sm font-medium text-paper hover:bg-accent-hover transition-colors min-h-[44px]"
          >
            + Add source
          </button>
          <button
            onClick={() => importYaml.mutate()}
            disabled={importYaml.isPending}
            title="从配置的 subscriptions.yaml 文件导入订阅源到数据库"
            className="shrink-0 rounded-md border border-rule px-4 py-2 text-sm font-medium text-ink-3 hover:bg-paper-2 disabled:opacity-50 transition-colors min-h-[44px]"
          >
            {importYaml.isPending ? "Importing…" : "Import YAML"}
          </button>
          <button
            onClick={() => exportYaml.mutate()}
            disabled={exportYaml.isPending}
            title="将数据库中的订阅源导出到配置的 subscriptions.yaml 文件"
            className="shrink-0 rounded-md border border-rule px-4 py-2 text-sm font-medium text-ink-3 hover:bg-paper-2 disabled:opacity-50 transition-colors min-h-[44px]"
          >
            {exportYaml.isPending ? "Exporting…" : "Export YAML"}
          </button>
        </div>
      </div>

      {/* Messages */}
      {importYaml.isSuccess && (
        <div className="mb-4 rounded-md bg-ok-muted p-3 text-sm text-ok font-medium">
          Imported {importYaml.data.imported} source(s).
        </div>
      )}
      {importYaml.isError && (
        <div className="mb-4 rounded-md bg-err-muted p-3 text-sm text-err">
          Import failed. Check that subscriptions.yaml exists.
        </div>
      )}
      {exportYaml.isSuccess && (
        <div className="mb-4 rounded-md bg-ok-muted p-3 text-sm text-ok font-medium">
          Exported to {exportYaml.data.exported}.
        </div>
      )}
      {exportYaml.isError && (
        <div className="mb-4 rounded-md bg-err-muted p-3 text-sm text-err">
          Export failed. Check that the database is accessible.
        </div>
      )}

      {/* Add/Edit form */}
      {showForm && (
        <div className="mb-6 rounded-md border border-rule bg-paper p-4 space-y-3">
          <h2 className="text-sm font-semibold text-ink">
            {editing ? `Edit: ${editing.name ?? editing.source_key}` : "Add source"}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1">
                URL
              </label>
              <input
                type="url"
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
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
                onChange={(e) => setForm({ ...form, name: e.target.value })}
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
                  setForm({
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
                    setForm({ ...form, javascript: e.target.checked })
                  }
                  className="accent-accent rounded-sm"
                />
                Requires JavaScript
              </label>
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={submit}
              disabled={isPending || !form.url.trim()}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-paper hover:bg-accent-hover disabled:opacity-50 transition-colors min-h-[44px]"
            >
              {isPending
                ? "Saving…"
                : editing
                  ? "Update"
                  : "Add"}
            </button>
            <button
              onClick={cancel}
              className="rounded-md border border-rule px-4 py-2 text-sm font-medium text-ink-3 hover:bg-paper-2 transition-colors min-h-[44px]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Source list */}
      {isLoading && <SkeletonTable rows={5} />}
      {error && <ErrorCard error={error} />}
      {data && data.length === 0 && (
        <EmptyState
          message="No sources configured."
          action={{
            label: "Add a source",
            onClick: openAdd,
          }}
        />
      )}
      {data && data.length > 0 && (
        <SourcesTable sources={data} onEdit={openEdit} />
      )}
    </div>
  );
}
