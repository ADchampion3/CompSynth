import { useParams, Link } from "react-router-dom";
import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { useReportDetail } from "../../api/hooks";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";

export default function ReportDetailPage() {
  const { reportId } = useParams();
  const { data, isLoading, error } = useReportDetail(reportId);

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <LoadingSkeleton lines={10} />
      </div>
    );
  }

  if (error) return <ErrorCard error={error} />;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link
        to="/reports"
        className="text-sm text-gray-500 hover:text-gray-700"
      >
        ← Back to Reports
      </Link>
      <h1 className="text-lg font-bold mt-3 mb-4">
        {data?.title ?? "Report"}
      </h1>
      {data?.markdown ? (
        <article className="prose prose-sm prose-gray max-w-none">
          <Markdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeSanitize]}
          >
            {data.markdown}
          </Markdown>
        </article>
      ) : (
        <p className="text-sm text-gray-400">No content available.</p>
      )}
    </div>
  );
}
