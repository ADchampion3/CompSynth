import { useParams, Link } from "react-router-dom";
import { useArticleDetail, useArticleState } from "../../api/hooks";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";
import ArticleContent from "./ArticleContent";
import ArticleHeader from "./ArticleHeader";
import NotePanel from "./NotePanel";

export default function ArticleDetailPage() {
  const { articleId: rawId } = useParams();
  const articleId = rawId ? decodeURIComponent(rawId) : undefined;

  const {
    data: article,
    isLoading,
    error,
  } = useArticleDetail(articleId);
  const { data: state } = useArticleState(articleId);

  useDocumentTitle(article?.title ?? "");

  if (isLoading) {
    return (
      <div className="p-6 md:p-8 max-w-3xl mx-auto">
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error) return <div className="p-6 md:p-8 max-w-3xl mx-auto"><ErrorCard error={error} /></div>;

  if (!article) {
    return (
      <div className="p-6 md:p-8 max-w-3xl mx-auto text-center text-ink-3">
        Article not found.
        <Link to="/inbox" className="ml-2 text-accent-text hover:underline">
          Back to Inbox
        </Link>
      </div>
    );
  }

  return (
    <article className="p-6 md:p-8 max-w-3xl mx-auto">
      <Link
        to="/inbox"
        className="text-xs font-medium uppercase tracking-wider text-ink-4 hover:text-ink transition-colors"
      >
        ← Inbox
      </Link>

      <ArticleHeader article={article} state={state} />

      {/* Tags */}
      {article.tags.length > 0 && (
        <div className="flex gap-1.5 mt-5">
          {article.tags.map((t) => (
            <span
              key={t}
              className="rounded-sm bg-paper-3 px-2 py-0.5 text-[0.6875rem] font-medium text-ink-3"
            >
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Summary */}
      {article.summary && (
        <section className="mt-8 rounded-md bg-paper-2 p-5">
          <h3 className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 mb-2">
            Summary
          </h3>
          <p className="text-sm text-ink-2 leading-relaxed whitespace-pre-wrap font-display">
            {article.summary}
          </p>
        </section>
      )}

      {/* Content */}
      <ArticleContent url={article.url} content={article.content ?? ""} />

      <hr className="border-rule my-8" />

      <NotePanel articleId={article.article_id} state={state} />
    </article>
  );
}
