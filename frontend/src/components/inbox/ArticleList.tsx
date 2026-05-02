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
  const markRead = useUpdateArticleState();
  const toggleLike = useUpdateArticleLike();

  return (
    <ul className="divide-y divide-gray-100">
      {articles.map((article) => {
        const isSelected = article.article_id === selectedId;

        return (
          <li
            key={article.article_id}
            className={`py-3 px-2 cursor-pointer hover:bg-gray-50 ${
              isSelected ? "bg-blue-50" : ""
            }`}
            onClick={() => onSelect(article)}
          >
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                {/* Mobile: link to full detail */}
                <Link
                  to={`/articles/${encodeURIComponent(article.article_id)}`}
                  onClick={(e) => e.stopPropagation()}
                  className="font-medium text-sm text-gray-900 hover:text-blue-700 md:hidden block"
                >
                  {truncate(article.title || "(untitled)", 80)}
                </Link>
                {/* Desktop: just title text */}
                <span className="font-medium text-sm text-gray-900 hidden md:block">
                  {truncate(article.title || "(untitled)", 100)}
                </span>
                <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                  <span>{article.source}</span>
                  <span>
                    {formatRelativeTime(
                      article.published_at ?? article.collected_at,
                    )}
                  </span>
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
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    markRead.mutate({
                      articleId: article.article_id,
                      readState: "read",
                    });
                  }}
                  disabled={markRead.isPending}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  ✓
                </button>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
