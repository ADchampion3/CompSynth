import { useSources, useImportYaml } from "../../api/hooks";
import ErrorCard from "../ui/ErrorCard";
import { SkeletonTable } from "../ui/LoadingSkeleton";
import EmptyState from "../ui/EmptyState";
import SourcesTable from "./SourcesTable";

export default function SourcesPage() {
  const { data, isLoading, error } = useSources();
  const importYaml = useImportYaml();

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-bold">Sources</h1>
        <button
          onClick={() => importYaml.mutate()}
          disabled={importYaml.isPending}
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {importYaml.isPending ? "Importing..." : "Import YAML"}
        </button>
      </div>

      {importYaml.isSuccess && (
        <div className="mb-4 rounded bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          Imported {importYaml.data.imported} source(s).
        </div>
      )}
      {importYaml.isError && (
        <div className="mb-4 rounded bg-red-50 border border-red-200 p-3 text-sm text-red-700">
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
