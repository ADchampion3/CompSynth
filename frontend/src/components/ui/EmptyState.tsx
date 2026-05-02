export default function EmptyState({
  message,
  action,
}: {
  message: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <p className="text-gray-500 text-sm">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-3 rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
