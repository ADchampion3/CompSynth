import { memo } from "react";
import { Link } from "react-router-dom";
import type { ArticleResponse } from "../../api/types";
import { useUpdateArticleState, useUpdateArticleLike } from "../../api/hooks";
import { formatRelativeTime, truncate } from "../../lib/format";

interface ArticleItemProps {
  article: ArticleResponse;
  isSelected: boolean;
  onSelect: (article: ArticleResponse) => void;
  onToggleLike: (articleId: string, liked: boolean) => void;
  onMarkRead: (articleId: string, readState: "unread" | "read") => void;
  isUpdating: boolean;
}

const ArticleListItem = memo(function ArticleListItem({
  article,
  isSelected,
  onSelect,
  onToggleLike,
  onMarkRead,
  isUpdating,
}: ArticleItemProps) {
  const isRead = article.read_state === "read";
  const isIgnored = article.read_state === "ignored";

  const titleClass = isRead
    ? "text-ink-4 font-normal"
    : isIgnored
      ? "text-ink-4/60 font-normal"
      : "text-ink font-medium";

  const metaClass = isRead
    ? "text-ink-4/70"
    : isIgnored
      ? "text-ink-4/50"
      : "text-ink-4";

  const summaryClass = isRead
    ? "text-ink-4"
    : isIgnored
      ? "text-ink-4/60"
      : "text-ink-3";

  return (
    <li
      role="button"
      tabIndex={0}
      aria-label={article.title || "(untitled)"}
      className={`py-3 px-2 cursor-pointer transition-colors rounded-md ${
        isSelected ? "bg-accent-muted/40" : "hover:bg-paper-2"
      }`}
      onClick={() => onSelect(article)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(article);
        }
      }}
    >
      <div className="flex items-start gap-3">
        <div className="pt-2 shrink-0">
          {!isRead && !isIgnored && (
            <span
              className="block w-1.5 h-1.5 rounded-full bg-accent"
              aria-label="Unread"
            />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <Link
            to={`/articles/${encodeURIComponent(article.article_id)}`}
            onClick={(e) => e.stopPropagation()}
            className={`font-display text-[0.9375rem] md:hidden block leading-snug py-1 ${titleClass} hover:text-accent-text`}
          >
            {truncate(article.title || "(untitled)", 80)}
          </Link>
          <Link
            to={`/articles/${encodeURIComponent(article.article_id)}`}
            onClick={(e) => e.stopPropagation()}
            className={`font-display text-[0.9375rem] hidden md:block leading-snug ${titleClass} hover:text-accent-text`}
          >
            {truncate(article.title || "(untitled)", 100)}
          </Link>
          <div className={`flex items-center gap-2 mt-1 text-xs ${metaClass}`}>
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
            <p className={`mt-1.5 text-xs leading-relaxed line-clamp-2 ${summaryClass}`}>
              {truncate(article.summary, 150)}
            </p>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0 pt-0.5">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleLike(article.article_id, article.liked !== 1);
            }}
            className={`text-sm p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md transition-colors ${
              article.liked === 1
                ? "text-warn"
                : "text-ink-4 hover:text-warn hover:bg-paper-2"
            }`}
            title={article.liked === 1 ? "Unlike" : "Like"}
            aria-label={article.liked === 1 ? "Unlike" : "Like"}
          >
            {article.liked === 1 ? "★" : "☆"}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onMarkRead(article.article_id, isRead ? "unread" : "read");
            }}
            disabled={isUpdating}
            className={`text-xs px-2.5 py-2 min-h-[44px] rounded-md transition-colors ${
              isRead
                ? "text-accent-text hover:text-accent hover:bg-paper-2"
                : "text-ink-4 hover:text-ink hover:bg-paper-2"
            }`}
            title={isRead ? "Mark unread" : "Mark read"}
            aria-label={isRead ? "Mark unread" : "Mark read"}
          >
            {isRead ? "Undo" : "Read"}
          </button>
        </div>
      </div>
    </li>
  );
});

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
    <ul className="divide-y divide-rule" role="list">
      {articles.map((article) => (
        <ArticleListItem
          key={article.article_id}
          article={article}
          isSelected={article.article_id === selectedId}
          onSelect={onSelect}
          onToggleLike={(id, liked) =>
            toggleLike.mutate({ articleId: id, liked })
          }
          onMarkRead={(id, readState) =>
            updateState.mutate({ articleId: id, readState })
          }
          isUpdating={updateState.isPending}
        />
      ))}
    </ul>
  );
}
