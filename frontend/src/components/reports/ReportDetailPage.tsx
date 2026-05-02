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
      <div className="p-6 md:p-8 max-w-4xl mx-auto">
        <LoadingSkeleton lines={10} />
      </div>
    );
  }

  if (error) return <div className="p-6 md:p-8 max-w-4xl mx-auto"><ErrorCard error={error} /></div>;

  return (
    <div className="p-6 md:p-8 max-w-4xl mx-auto">
      <Link
        to="/reports"
        className="text-xs font-medium uppercase tracking-wider text-ink-4 hover:text-ink transition-colors"
      >
        ← Reports
      </Link>
      <h1 className="font-display text-2xl md:text-3xl font-bold text-ink mt-4 mb-6 leading-tight">
        {data?.title ?? "Report"}
      </h1>
      {data?.markdown ? (
        <article className="prose prose-gray max-w-none">
          <Markdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeSanitize]}
          >
            {data.markdown}
          </Markdown>
        </article>
      ) : (
        <p className="text-sm text-ink-4">No content available.</p>
      )}
    </div>
  );
}
