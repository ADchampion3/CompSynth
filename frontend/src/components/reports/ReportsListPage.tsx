import { Link } from "react-router-dom";
import { useReports } from "../../api/hooks";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { formatDate } from "../../lib/format";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";
import EmptyState from "../ui/EmptyState";

export default function ReportsListPage() {
  const { data, isLoading, error } = useReports();
  useDocumentTitle("Reports");

  if (isLoading) {
    return (
      <div className="p-6 md:p-8 max-w-3xl">
        <LoadingSkeleton lines={5} />
      </div>
    );
  }

  if (error) return <div className="p-6 md:p-8 max-w-3xl"><ErrorCard error={error} /></div>;

  return (
    <div className="p-6 md:p-8 max-w-3xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold text-ink mb-6">
        Reports
      </h1>
      {!data || data.length === 0 ? (
        <EmptyState message="No reports yet. Run a crawl to generate content." />
      ) : (
        <ul className="divide-y divide-rule">
          {data.map((report) => (
            <li key={report.report_id}>
              <Link
                to={`/reports/${report.report_id}`}
                className="flex items-baseline justify-between gap-4 py-3 group"
              >
                <span className="font-display text-[0.9375rem] font-medium text-ink group-hover:text-accent-text transition-colors">
                  {report.title}
                </span>
                <span className="text-xs text-ink-4 shrink-0 tabular-nums">
                  {formatDate(report.created_at)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
