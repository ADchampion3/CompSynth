import { ApiError } from "../../api/client";

export default function ErrorCard({ error }: { error: unknown }) {
  if (error instanceof ApiError) {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-4 space-y-1">
        <div className="font-medium text-red-800">{error.problem}</div>
        {error.cause && <div className="text-sm text-red-700">{error.cause}</div>}
        {error.fix && <div className="text-sm text-red-600">Fix: {error.fix}</div>}
      </div>
    );
  }

  const message =
    error instanceof Error ? error.message : "An unknown error occurred.";

  return (
    <div className="rounded border border-red-200 bg-red-50 p-4">
      <div className="font-medium text-red-800">
        {message}
      </div>
      <div className="text-sm text-red-600 mt-1">
        Check that the backend is running: <code>uv run compsynth serve</code>
      </div>
    </div>
  );
}
