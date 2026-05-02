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
    <div className="mt-4 space-y-3">
      <h1 className="font-display text-2xl md:text-3xl font-bold text-ink leading-tight">
        {article.title || "(untitled)"}
      </h1>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-ink-4">
        <span>{article.source}</span>
        {article.published_at && (
          <span>Published {formatDateTime(article.published_at)}</span>
        )}
        {article.collected_at && (
          <span>Collected {formatDateTime(article.collected_at)}</span>
        )}
        <a
          href={safeHref(article.url)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-text hover:underline"
        >
          Original ↗
        </a>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={() =>
            toggleLike.mutate({
              articleId: article.article_id,
              liked: article.liked !== 1,
            })
          }
          className={`rounded-md px-3 py-1 text-xs font-medium border transition-colors ${
            article.liked === 1
              ? "border-warn/40 bg-warn-muted text-warn"
              : "border-rule text-ink-3 hover:bg-paper-2"
          }`}
        >
          {article.liked === 1 ? "★ Liked" : "☆ Like"}
        </button>

        <button
          onClick={() =>
            updateState.mutate({
              articleId: article.article_id,
              readState: state?.read_state === "read" ? "unread" : "read",
            })
          }
          className="rounded-md border border-rule px-3 py-1 text-xs font-medium text-ink-3 hover:bg-paper-2 transition-colors"
        >
          {state?.read_state === "read" ? "Unread" : "Read"}
        </button>

        <button
          onClick={() =>
            updateState.mutate({
              articleId: article.article_id,
              readState: "later",
            })
          }
          className="rounded-md border border-rule px-3 py-1 text-xs font-medium text-ink-3 hover:bg-paper-2 transition-colors"
        >
          Later
        </button>

        <button
          onClick={() =>
            updateState.mutate({
              articleId: article.article_id,
              readState: "ignored",
            })
          }
          className="rounded-md border border-rule px-3 py-1 text-xs font-medium text-ink-3 hover:bg-paper-2 transition-colors"
        >
          Ignore
        </button>

        {state && (
          <span className="text-[0.6875rem] text-ink-4 ml-1 uppercase tracking-wider">
            {state.read_state}
          </span>
        )}
      </div>
    </div>
  );
}
