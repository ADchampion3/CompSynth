import { Link } from "react-router-dom";
import { useReports } from "../../api/hooks";
import { formatDate } from "../../lib/format";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";
import EmptyState from "../ui/EmptyState";

export default function ReportsListPage() {
  const { data, isLoading, error } = useReports();

  if (isLoading) {
    return (
      <div className="p-6">
        <LoadingSkeleton lines={5} />
      </div>
    );
  }

  if (error) return <ErrorCard error={error} />;

  return (
    <div className="p-6">
      <h1 className="text-lg font-bold mb-4">Reports</h1>
      {!data || data.length === 0 ? (
        <EmptyState message="No reports yet. Run a crawl to generate content." />
      ) : (
        <ul className="divide-y divide-gray-100">
          {data.map((report) => (
            <li key={report.report_id} className="py-3">
              <Link
                to={`/reports/${report.report_id}`}
                className="flex items-center justify-between hover:bg-gray-50 px-2 py-1 -mx-2 rounded"
              >
                <span className="text-sm font-medium text-gray-900">
                  {report.title}
                </span>
                <span className="text-xs text-gray-500">
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
