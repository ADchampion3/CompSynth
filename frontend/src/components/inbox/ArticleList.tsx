import { Link } from "react-router-dom";
import type { ArticleResponse } from "../../api/types";
import { useUpdateArticleState, useUpdateArticleLike } from "../../api/hooks";
import { formatRelativeTime, truncate } from "../../lib/format";

export default function ArticleList({
  articles,
  selectedId,
  onSelect,
}: {
  articles: ArticleResponse[];
  selectedId?: string;
  onSelect: (article: ArticleResponse) => void;
}) {
  const updateState = useUpdateArticleState();
  const toggleLike = useUpdateArticleLike();

  return (
    <ul className="divide-y divide-rule">
      {articles.map((article) => {
        const isSelected = article.article_id === selectedId;
        const isRead = article.read_state === "read";
        const isIgnored = article.read_state === "ignored";

        return (
          <li
            key={article.article_id}
            className={`py-3 px-1 cursor-pointer transition-colors ${
              isSelected
                ? "bg-accent-muted/40 -mx-1 px-2 rounded-md"
                : "hover:bg-paper-2 -mx-1 px-2 rounded-md"
            } ${isRead ? "opacity-55" : ""} ${isIgnored ? "opacity-35" : ""}`}
            onClick={() => onSelect(article)}
          >
            <div className="flex items-start gap-3">
              {/* Unread indicator */}
              <div className="pt-2 shrink-0">
                {!isRead && !isIgnored && (
                  <span
                    className="block w-1.5 h-1.5 rounded-full bg-accent"
                    title="Unread"
                  />
                )}
              </div>

              <div className="flex-1 min-w-0">
                {/* Mobile: link to full detail */}
                <Link
                  to={`/articles/${encodeURIComponent(article.article_id)}`}
                  onClick={(e) => e.stopPropagation()}
                  className={`font-display text-[0.9375rem] md:hidden block leading-snug ${
                    isRead
                      ? "text-ink-3 font-normal"
                      : "text-ink font-medium hover:text-accent-text"
                  }`}
                >
                  {truncate(article.title || "(untitled)", 80)}
                </Link>
                {/* Desktop: title text */}
                <span
                  className={`font-display text-[0.9375rem] hidden md:block leading-snug ${
                    isRead ? "text-ink-3 font-normal" : "text-ink font-medium"
                  }`}
                >
                  {truncate(article.title || "(untitled)", 100)}
                </span>
                <div className="flex items-center gap-2 mt-1 text-xs text-ink-4">
                  <span>{article.source}</span>
                  <span>
                    {formatRelativeTime(
                      article.published_at ?? article.collected_at,
                    )}
                  </span>
                  {article.read_state &&
                    article.read_state !== "unread" &&
                    article.read_state !== "read" && (
                      <span className="text-accent-text">
                        {article.read_state}
                      </span>
                    )}
                </div>
                {article.summary && (
                  <p className="mt-1.5 text-xs text-ink-3 leading-relaxed line-clamp-2">
                    {truncate(article.summary, 150)}
                  </p>
                )}
              </div>

              {/* State controls */}
              <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleLike.mutate({
                      articleId: article.article_id,
                      liked: article.liked !== 1,
                    });
                  }}
                  className={`text-sm transition-colors ${
                    article.liked === 1
                      ? "text-warn"
                      : "text-ink-4 hover:text-warn"
                  }`}
                  title={article.liked === 1 ? "Unlike" : "Like"}
                >
                  {article.liked === 1 ? "★" : "☆"}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    updateState.mutate({
                      articleId: article.article_id,
                      readState: isRead ? "unread" : "read",
                    });
                  }}
                  disabled={updateState.isPending}
                  className={`text-xs transition-colors ${
                    isRead
                      ? "text-accent-text hover:text-accent"
                      : "text-ink-4 hover:text-ink"
                  }`}
                  title={isRead ? "Mark unread" : "Mark read"}
                >
                  {isRead ? "Undo" : "Read"}
                </button>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
