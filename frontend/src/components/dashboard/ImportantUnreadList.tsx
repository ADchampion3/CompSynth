import { Link } from "react-router-dom";
import type { ImportantArticleResponse } from "../../api/types";
import { useUpdateArticleState } from "../../api/hooks";
import { formatRelativeTime } from "../../lib/format";

export default function ImportantUnreadList({
  items,
}: {
  items: ImportantArticleResponse[];
}) {
  const markRead = useUpdateArticleState();

  if (items.length === 0) {
    return (
      <>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-3 mb-3">
          Important Unread
        </h2>
        <p className="text-sm text-ink-4">Nothing unread.</p>
      </>
    );
  }

  return (
    <>
      <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-3 mb-3">
        Important Unread ({items.length})
      </h2>
      <ul className="divide-y divide-rule">
        {items.map(({ article, importance_score }) => (
          <li
            key={article.article_id}
            className="flex items-start gap-3 py-3 group"
          >
            <div className="flex-1 min-w-0">
              <Link
                to={`/articles/${encodeURIComponent(article.article_id)}`}
                className="font-display text-[0.9375rem] font-medium text-ink hover:text-accent-text transition-colors"
              >
                {article.title || "(untitled)"}
              </Link>
              <div className="flex items-center gap-2 mt-0.5 text-xs text-ink-4">
                <span>{article.source}</span>
                <span>{formatRelativeTime(article.published_at ?? article.collected_at)}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="text-xs text-ink-4 tabular-nums">
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
                className="text-xs text-ink-3 hover:text-ink disabled:opacity-50"
              >
                Read
              </button>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
