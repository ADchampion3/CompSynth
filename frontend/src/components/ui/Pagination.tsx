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
    <div className="flex items-center justify-between py-4 text-sm text-ink-3">
      <span className="tabular-nums">
        {from}–{to} of {total}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => onPageChange(offset - limit)}
          disabled={!hasPrev}
          className="rounded-md px-3 py-1 text-sm border border-rule hover:bg-paper-2 disabled:opacity-30 transition-colors"
        >
          Prev
        </button>
        <button
          onClick={() => onPageChange(offset + limit)}
          disabled={!hasNext}
          className="rounded-md px-3 py-1 text-sm border border-rule hover:bg-paper-2 disabled:opacity-30 transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
}
