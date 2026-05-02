import { useSources, useImportYaml } from "../../api/hooks";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import ErrorCard from "../ui/ErrorCard";
import { SkeletonTable } from "../ui/LoadingSkeleton";
import EmptyState from "../ui/EmptyState";
import SourcesTable from "./SourcesTable";

export default function SourcesPage() {
  const { data, isLoading, error } = useSources();
  const importYaml = useImportYaml();
  useDocumentTitle("Sources");

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      <div className="flex items-start justify-between gap-4 mb-6">
        <h1 className="font-display text-2xl md:text-3xl font-bold text-ink">
          Sources
        </h1>
        <button
          onClick={() => importYaml.mutate()}
          disabled={importYaml.isPending}
          className="shrink-0 rounded-md bg-accent px-4 py-2 text-sm font-medium text-paper hover:bg-accent-hover disabled:opacity-50 transition-colors min-h-[44px]"
        >
          {importYaml.isPending ? "Importing…" : "Import YAML"}
        </button>
      </div>

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

      {isLoading && <SkeletonTable rows={5} />}
      {error && <ErrorCard error={error} />}
      {data && data.length === 0 && (
        <EmptyState
          message="No sources configured."
          action={{ label: "Import from YAML", onClick: () => importYaml.mutate() }}
        />
      )}
      {data && data.length > 0 && <SourcesTable sources={data} />}
    </div>
  );
}
