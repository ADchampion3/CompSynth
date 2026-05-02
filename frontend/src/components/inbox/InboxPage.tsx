import { useSearchParams } from "react-router-dom";
import { useArticles } from "../../api/hooks";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";
import EmptyState from "../ui/EmptyState";
import Pagination from "../ui/Pagination";
import FilterRail from "./FilterRail";
import ArticleList from "./ArticleList";
import ArticlePreview from "./ArticlePreview";
import { useState } from "react";
import type { ArticleResponse } from "../../api/types";

const PAGE_SIZE = 50;

export default function InboxPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedArticle, setSelectedArticle] =
    useState<ArticleResponse | null>(null);
  useDocumentTitle("Inbox");

  const rawOffset = Number(searchParams.get("offset") ?? 0);
  const offset =
    Number.isInteger(rawOffset) && rawOffset >= 0 ? rawOffset : 0;
  const source = searchParams.get("source") ?? undefined;
  const tag = searchParams.get("tag") ?? undefined;
  const likedParam = searchParams.get("liked");
  const liked = likedParam !== null ? likedParam === "true" : undefined;
  const query = searchParams.get("query") ?? undefined;
  const readState = searchParams.get("readState") ?? undefined;

  const { data, isLoading, error } = useArticles({
    limit: PAGE_SIZE,
    offset,
    source,
    tag,
    liked,
    query,
    read_state: readState,
  });

  function setFilter(key: string, value: string | undefined) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      next.delete("offset");
      return next;
    });
    setSelectedArticle(null);
  }

  function clearFilters() {
    setSearchParams(new URLSearchParams());
    setSelectedArticle(null);
  }

  function handlePageChange(newOffset: number) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("offset", String(newOffset));
      return next;
    });
    setSelectedArticle(null);
  }

  return (
    <div className="flex h-full">
      {/* Filter rail - desktop */}
      <div className="hidden md:block w-52 shrink-0 border-r border-rule overflow-auto p-5">
        <FilterRail
          source={source}
          tag={tag}
          liked={liked}
          query={query}
          readState={readState}
          onFilterChange={setFilter}
          onClear={clearFilters}
        />
      </div>

      {/* Article list */}
      <div className="flex-1 min-w-0 overflow-auto p-5 md:p-6">
        <div className="flex items-center justify-between mb-5">
          <h1 className="font-display text-xl md:text-2xl font-bold text-ink">
            Inbox
          </h1>
          {/* Mobile filter toggle */}
          <details className="md:hidden">
            <summary className="text-xs font-medium uppercase tracking-wider text-accent-text cursor-pointer">
              Filters
            </summary>
            <div className="mt-3 rounded-md border border-rule p-4 bg-paper">
              <FilterRail
                source={source}
                tag={tag}
                liked={liked}
                query={query}
                readState={readState}
                onFilterChange={setFilter}
                onClear={clearFilters}
              />
            </div>
          </details>
        </div>

        {isLoading && <LoadingSkeleton lines={8} />}
        {error && <ErrorCard error={error} />}
        {data && data.items.length === 0 && (
          <EmptyState message="No articles match your filters." />
        )}
        {data && data.items.length > 0 && (
          <>
            <ArticleList
              articles={data.items}
              selectedId={selectedArticle?.article_id}
              onSelect={setSelectedArticle}
            />
            <Pagination
              total={data.total}
              limit={PAGE_SIZE}
              offset={offset}
              onPageChange={handlePageChange}
            />
          </>
        )}
      </div>

      {/* Preview pane - desktop only */}
      <div className="hidden lg:block w-80 xl:w-96 shrink-0 border-l border-rule overflow-auto">
        <ArticlePreview article={selectedArticle} />
      </div>
    </div>
  );
}
