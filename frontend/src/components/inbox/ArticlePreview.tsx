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
      <div className="flex items-center justify-center h-full text-sm text-ink-4">
        Select an article to preview
      </div>
    );
  }

  return (
    <div className="p-5 space-y-4">
      <h2 className="font-display text-lg font-bold leading-snug text-ink">
        {article.title || "(untitled)"}
      </h2>
      <div className="flex items-center gap-2 text-xs text-ink-4">
        <span>{article.source}</span>
        <span>
          {formatRelativeTime(article.published_at ?? article.collected_at)}
        </span>
      </div>
      {article.summary && (
        <p className="text-sm text-ink-2 leading-relaxed whitespace-pre-wrap">
          {article.summary}
        </p>
      )}
      <Link
        to={`/articles/${encodeURIComponent(article.article_id)}`}
        className="inline-block text-sm text-accent-text hover:underline font-medium"
      >
        Read full article →
      </Link>
    </div>
  );
}
