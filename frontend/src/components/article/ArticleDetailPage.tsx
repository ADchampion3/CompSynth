import { useParams, Link } from "react-router-dom";
import { useArticleDetail, useArticleState } from "../../api/hooks";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";
import Badge from "../ui/Badge";
import ArticleHeader from "./ArticleHeader";
import NotePanel from "./NotePanel";
import RelatedArticles from "./RelatedArticles";

export default function ArticleDetailPage() {
  const { articleId: rawId } = useParams();
  const articleId = rawId ? decodeURIComponent(rawId) : undefined;

  const {
    data: article,
    isLoading,
    error,
  } = useArticleDetail(articleId);
  const { data: state } = useArticleState(articleId);

  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error) return <ErrorCard error={error} />;

  if (!article) {
    return (
      <div className="p-6 max-w-3xl mx-auto text-center text-gray-500">
        Article not found.
        <Link to="/inbox" className="ml-2 text-blue-600 hover:underline">
          Back to Inbox
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <Link
        to="/inbox"
        className="text-sm text-gray-500 hover:text-gray-700"
      >
        ← Back to Inbox
      </Link>

      <ArticleHeader article={article} state={state} />

      {/* Tags */}
      {article.tags.length > 0 && (
        <div className="flex gap-1">
          {article.tags.map((t) => (
            <Badge key={t} label={t} />
          ))}
        </div>
      )}

      {/* Summary */}
      {article.summary && (
        <div className="rounded border border-gray-200 bg-gray-50 p-4">
          <h3 className="text-xs font-semibold text-gray-500 mb-2">Summary</h3>
          <p className="text-sm text-gray-800 whitespace-pre-wrap">
            {article.summary}
          </p>
        </div>
      )}

      {/* Content */}
      {article.content ? (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 mb-2">Content</h3>
          <div className="text-sm text-gray-800 whitespace-pre-wrap">
            {article.content}
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-400">No full content available.</p>
      )}

      <hr className="border-gray-200" />

      <RelatedArticles articleId={article.article_id} />
      <NotePanel articleId={article.article_id} state={state} />
    </div>
  );
}
