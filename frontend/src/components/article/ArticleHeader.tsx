import type { ArticleResponse, ArticleStateResponse } from "../../api/types";
import { useUpdateArticleLike, useUpdateArticleState } from "../../api/hooks";
import { safeHref } from "../../api/client";
import { formatDateTime } from "../../lib/format";

export default function ArticleHeader({
  article,
  state,
}: {
  article: ArticleResponse;
  state: ArticleStateResponse | undefined;
}) {
  const toggleLike = useUpdateArticleLike();
  const updateState = useUpdateArticleState();

  return (
    <div className="space-y-2">
      <h1 className="text-xl font-bold">{article.title || "(untitled)"}</h1>
      <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
        <span>{article.source}</span>
        {article.published_at && (
          <span>Published: {formatDateTime(article.published_at)}</span>
        )}
        {article.collected_at && (
          <span>Collected: {formatDateTime(article.collected_at)}</span>
        )}
        <a
          href={safeHref(article.url)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline"
        >
          Open Original ↗
        </a>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={() =>
            toggleLike.mutate({
              articleId: article.article_id,
              liked: article.liked !== 1,
            })
          }
          className={`rounded border px-3 py-1 text-sm ${
            article.liked === 1
              ? "border-yellow-400 bg-yellow-50 text-yellow-700"
              : "border-gray-300 text-gray-600 hover:bg-gray-50"
          }`}
        >
          {article.liked === 1 ? "★ Liked" : "☆ Like"}
        </button>

        {state?.read_state !== "read" ? (
          <button
            onClick={() =>
              updateState.mutate({
                articleId: article.article_id,
                readState: "read",
              })
            }
            className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
          >
            Mark Read
          </button>
        ) : (
          <button
            onClick={() =>
              updateState.mutate({
                articleId: article.article_id,
                readState: "unread",
              })
            }
            className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
          >
            Mark Unread
          </button>
        )}

        <button
          onClick={() =>
            updateState.mutate({
              articleId: article.article_id,
              readState: "later",
            })
          }
          className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
        >
          Read Later
        </button>

        <button
          onClick={() =>
            updateState.mutate({
              articleId: article.article_id,
              readState: "ignored",
            })
          }
          className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
        >
          Ignore
        </button>

        {state && (
          <span className="text-xs text-gray-400 ml-2">
            State: {state.read_state}
          </span>
        )}
      </div>
    </div>
  );
}
