export default function Pagination({
  total,
  limit,
  offset,
  onPageChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onPageChange: (newOffset: number) => void;
}) {
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <div className="flex items-center justify-between py-3 text-sm text-gray-500">
      <span>
        Showing {from}–{to} of {total}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => onPageChange(offset - limit)}
          disabled={!hasPrev}
          className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40 hover:bg-gray-50"
        >
          Prev
        </button>
        <button
          onClick={() => onPageChange(offset + limit)}
          disabled={!hasNext}
          className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40 hover:bg-gray-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
