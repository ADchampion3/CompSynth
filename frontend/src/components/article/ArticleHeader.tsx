import { useState, useRef, useEffect } from "react";
import type { ArticleResponse, ArticleStateResponse } from "../../api/types";
import { useUpdateArticleLike, useUpdateArticleState, useUpdateArticleTags, useTags } from "../../api/hooks";
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
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          onClick={() =>
            toggleLike.mutate({
              articleId: article.article_id,
              liked: article.liked !== 1,
            })
          }
          className={`rounded-md px-3 py-2 text-xs font-medium border transition-colors min-h-[44px] ${
            article.liked === 1
              ? "border-warn/40 bg-warn-muted text-warn"
              : "border-rule text-ink-3 hover:bg-paper-2"
          }`}
          aria-label={article.liked === 1 ? "Unlike" : "Like"}
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
          className="rounded-md border border-rule px-3 py-2 text-xs font-medium text-ink-3 hover:bg-paper-2 transition-colors min-h-[44px]"
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
          className="rounded-md border border-rule px-3 py-2 text-xs font-medium text-ink-3 hover:bg-paper-2 transition-colors min-h-[44px]"
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
          className="rounded-md border border-rule px-3 py-2 text-xs font-medium text-ink-3 hover:bg-paper-2 transition-colors min-h-[44px]"
        >
          Ignore
        </button>

        {state && (
          <span className="text-[0.6875rem] text-ink-4 ml-1 uppercase tracking-wider">
            {state.read_state}
          </span>
        )}
      </div>

      {/* Tags */}
      <TagChips articleId={article.article_id} tags={article.tags} />
    </div>
  );
}

function TagChips({ articleId, tags }: { articleId: string; tags: string[] }) {
  const updateTags = useUpdateArticleTags();
  const { data: tagsData } = useTags();
  const vocabulary = tagsData?.tags ?? [];
  const [editing, setEditing] = useState(false);
  const [input, setInput] = useState("");

  const removeTag = (tag: string) => {
    const next = tags.filter((t) => t !== tag);
    updateTags.mutate({ articleId, tags: next });
  };

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (!trimmed || tags.includes(trimmed)) return;
    updateTags.mutate({ articleId, tags: [...tags, trimmed] });
    setInput("");
    setEditing(false);
  };

  const suggestions = vocabulary.filter(
    (v) => !tags.includes(v) && v.toLowerCase().includes(input.toLowerCase()),
  );

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-full border border-rule bg-paper-2 px-2.5 py-1 text-xs text-ink-2"
        >
          {tag}
          <button
            onClick={() => removeTag(tag)}
            className="text-ink-4 hover:text-warn transition-colors leading-none"
            aria-label={`Remove tag ${tag}`}
          >
            ×
          </button>
        </span>
      ))}
      {editing ? (
        <div className="relative">
          <input
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") addTag(input);
              if (e.key === "Escape") { setEditing(false); setInput(""); }
            }}
            onBlur={() => {
              if (input.trim()) addTag(input);
              else { setEditing(false); setInput(""); }
            }}
            placeholder="Add tag…"
            className="w-28 rounded-full border border-accent/40 bg-paper px-2.5 py-1 text-xs text-ink placeholder:text-ink-4 focus:outline-none"
          />
          {input.trim() && suggestions.length > 0 && (
            <div className="absolute top-full left-0 z-10 mt-1 w-48 rounded-md border border-rule bg-paper shadow-lg py-1">
              {suggestions.slice(0, 5).map((s) => (
                <button
                  key={s}
                  onMouseDown={(e) => { e.preventDefault(); addTag(s); }}
                  className="w-full text-left px-3 py-1.5 text-xs text-ink-2 hover:bg-paper-2"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="rounded-full border border-dashed border-rule px-2.5 py-1 text-xs text-ink-4 hover:border-accent hover:text-accent transition-colors"
        >
          + tag
        </button>
      )}
    </div>
  );
}
