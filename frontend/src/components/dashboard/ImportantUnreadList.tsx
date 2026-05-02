import { Link } from "react-router-dom";
import type { ImportantArticleResponse } from "../../api/types";
import { useUpdateArticleState } from "../../api/hooks";
import { formatRelativeTime } from "../../lib/format";
import Badge from "../ui/Badge";

export default function ImportantUnreadList({
  items,
}: {
  items: ImportantArticleResponse[];
}) {
  const markRead = useUpdateArticleState();

  if (items.length === 0) {
    return (
      <div className="text-sm text-gray-500 py-2">
        No unread important articles.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-semibold text-gray-700">
        Important Unread ({items.length})
      </h2>
      <ul className="divide-y divide-gray-100">
        {items.map(({ article, importance_score }) => (
          <li
            key={article.article_id}
            className="flex items-start gap-3 py-2"
          >
            <div className="flex-1 min-w-0">
              <Link
                to={`/articles/${encodeURIComponent(article.article_id)}`}
                className="text-sm font-medium text-blue-700 hover:underline truncate block"
              >
                {article.title || "(untitled)"}
              </Link>
              <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                <span>{article.source}</span>
                <span>{formatRelativeTime(article.published_at ?? article.collected_at)}</span>
                {article.tags.slice(0, 3).map((tag) => (
                  <Badge key={tag} label={tag} />
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-gray-400">
                {importance_score.toFixed(1)}
              </span>
              <button
                onClick={() =>
                  markRead.mutate({
                    articleId: article.article_id,
                    readState: "read",
                  })
                }
                disabled={markRead.isPending}
                className="text-xs text-gray-500 hover:text-gray-700 disabled:opacity-50"
              >
                Mark Read
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
