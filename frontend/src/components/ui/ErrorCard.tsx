import { ApiError } from "../../api/client";

export default function ErrorCard({ error }: { error: unknown }) {
  if (error instanceof ApiError) {
    return (
      <div className="rounded-md bg-err-muted p-4 space-y-1">
        <div className="font-medium text-err text-sm">{error.problem}</div>
        {error.cause && <div className="text-sm text-err/80">{error.cause}</div>}
        {error.fix && <div className="text-sm text-err/70">Fix: {error.fix}</div>}
      </div>
    );
  }

  const message =
    error instanceof Error ? error.message : "An unknown error occurred.";

  return (
    <div className="rounded-md bg-err-muted p-4">
      <div className="font-medium text-err text-sm">{message}</div>
      <div className="text-sm text-err/70 mt-1">
        Check that the backend is running: <code className="font-mono text-xs">uv run compsynth serve</code>
      </div>
    </div>
  );
}
