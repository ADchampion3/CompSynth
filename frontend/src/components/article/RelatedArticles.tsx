import { useRelatedArticles } from "../../api/hooks";

export default function RelatedArticles({
  articleId,
}: {
  articleId: string;
}) {
  const { data, isLoading } = useRelatedArticles(articleId);

  if (isLoading) return <div className="text-sm text-gray-400">Loading related...</div>;

  if (!data?.implemented || data.total === 0) {
    return (
      <div>
        <h3 className="text-xs font-semibold text-gray-500 mb-2">
          Related Articles
        </h3>
        <p className="text-sm text-gray-400">
          Related articles coming soon.
        </p>
      </div>
    );
  }

  return null;
}
