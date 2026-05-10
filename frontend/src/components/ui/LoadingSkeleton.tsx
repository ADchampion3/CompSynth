export default function LoadingSkeleton({
  lines = 3,
}: {
  lines?: number;
}) {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3 bg-paper-3 rounded-sm"
          style={{ "--skeleton-w": `${Math.max(40, 100 - i * 15)}%` } as React.CSSProperties}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-6">
          <div className="h-3 bg-paper-3 rounded-sm w-1/4" />
          <div className="h-3 bg-paper-3 rounded-sm w-1/6" />
          <div className="h-3 bg-paper-3 rounded-sm flex-1" />
          <div className="h-3 bg-paper-3 rounded-sm w-14" />
        </div>
      ))}
    </div>
  );
}
