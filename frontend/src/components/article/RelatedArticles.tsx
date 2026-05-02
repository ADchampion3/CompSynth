import { useRelatedArticles } from "../../api/hooks";

export default function RelatedArticles({
  articleId,
}: {
  articleId: string;
}) {
  const { data, isLoading } = useRelatedArticles(articleId);

  if (isLoading) {
    return (
      <div className="text-sm text-ink-4">Loading related…</div>
    );
  }

  if (!data?.implemented || data.total === 0) {
    return (
      <section>
        <h3 className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 mb-2">
          Related Articles
        </h3>
        <p className="text-sm text-ink-4">Related articles coming soon.</p>
      </section>
    );
  }

  return null;
}
