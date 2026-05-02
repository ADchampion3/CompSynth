import { Link } from "react-router-dom";
import type { ArticleResponse } from "../../api/types";
import { formatRelativeTime } from "../../lib/format";

export default function ArticlePreview({
  article,
}: {
  article: ArticleResponse | null;
}) {
  if (!article) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        Select an article to preview
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      <h2 className="font-semibold text-sm">{article.title || "(untitled)"}</h2>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span>{article.source}</span>
        <span>
          {formatRelativeTime(article.published_at ?? article.collected_at)}
        </span>
      </div>
      {article.summary && (
        <p className="text-sm text-gray-700 whitespace-pre-wrap">
          {article.summary}
        </p>
      )}
      <Link
        to={`/articles/${encodeURIComponent(article.article_id)}`}
        className="inline-block text-sm text-blue-600 hover:underline"
      >
        Open full article →
      </Link>
    </div>
  );
}
