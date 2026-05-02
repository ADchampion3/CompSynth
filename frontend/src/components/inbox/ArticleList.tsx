import { Link } from "react-router-dom";
import type { ArticleResponse } from "../../api/types";
import { useUpdateArticleState, useUpdateArticleLike } from "../../api/hooks";
import { formatRelativeTime, truncate } from "../../lib/format";
import Badge from "../ui/Badge";

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
    <ul className="divide-y divide-gray-100">
      {articles.map((article) => {
        const isSelected = article.article_id === selectedId;
        const isRead = article.read_state === "read";
        const isIgnored = article.read_state === "ignored";

        return (
          <li
            key={article.article_id}
            className={`py-3 px-2 cursor-pointer hover:bg-gray-50 ${
              isSelected ? "bg-blue-50" : ""
            } ${isRead ? "opacity-60" : ""} ${isIgnored ? "opacity-40" : ""}`}
            onClick={() => onSelect(article)}
          >
            <div className="flex items-start gap-2">
              {/* Unread dot */}
              <div className="pt-1.5 shrink-0">
                {!isRead && !isIgnored && (
                  <span className="block w-2 h-2 rounded-full bg-blue-500" title="Unread" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                {/* Mobile: link to full detail */}
                <Link
                  to={`/articles/${encodeURIComponent(article.article_id)}`}
                  onClick={(e) => e.stopPropagation()}
                  className={`text-sm md:hidden block ${
                    isRead ? "text-gray-500 font-normal" : "text-gray-900 font-medium hover:text-blue-700"
                  }`}
                >
                  {truncate(article.title || "(untitled)", 80)}
                </Link>
                {/* Desktop: just title text */}
                <span className={`text-sm hidden md:block ${
                  isRead ? "text-gray-500 font-normal" : "text-gray-900 font-medium"
                }`}>
                  {truncate(article.title || "(untitled)", 100)}
                </span>
                <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                  <span>{article.source}</span>
                  <span>
                    {formatRelativeTime(
                      article.published_at ?? article.collected_at,
                    )}
                  </span>
                  {article.read_state && article.read_state !== "unread" && (
                    <span className="text-xs text-gray-400">{article.read_state}</span>
                  )}
                </div>
                {article.summary && (
                  <p className="mt-1 text-xs text-gray-500 line-clamp-2">
                    {truncate(article.summary, 150)}
                  </p>
                )}
                <div className="flex items-center gap-1 mt-1">
                  {article.tags.slice(0, 3).map((t) => (
                    <Badge key={t} label={t} />
                  ))}
                </div>
              </div>

              {/* State controls */}
              <div className="flex items-center gap-1 shrink-0">
                {article.liked === 1 ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleLike.mutate({
                        articleId: article.article_id,
                        liked: false,
                      });
                    }}
                    className="text-yellow-500 text-sm"
                    title="Unlike"
                  >
                    ★
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleLike.mutate({
                        articleId: article.article_id,
                        liked: true,
                      });
                    }}
                    className="text-gray-300 text-sm hover:text-yellow-500"
                    title="Like"
                  >
                    ☆
                  </button>
                )}
                {isRead ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      updateState.mutate({
                        articleId: article.article_id,
                        readState: "unread",
                      });
                    }}
                    disabled={updateState.isPending}
                    className="text-xs text-blue-500 hover:text-blue-700"
                    title="Mark unread"
                  >
                    ✓
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      updateState.mutate({
                        articleId: article.article_id,
                        readState: "read",
                      });
                    }}
                    disabled={updateState.isPending}
                    className="text-xs text-gray-400 hover:text-gray-600"
                    title="Mark read"
                  >
                    ✓
                  </button>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
