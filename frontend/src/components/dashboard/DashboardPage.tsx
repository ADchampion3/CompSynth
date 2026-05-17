import { useDashboard, useStartCrawl } from "../../api/hooks";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";
import CrawlStatusCard from "./CrawlStatusCard";
import ImportantUnreadList from "./ImportantUnreadList";
import SourceHealthList from "./SourceHealthList";

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard();
  const startCrawl = useStartCrawl();
  useDocumentTitle("Briefing");

  const isCrawling = startCrawl.isPending || data?.latest_crawl_run?.status === "running";

  if (isLoading) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-3xl">
        <LoadingSkeleton lines={3} />
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error) return <div className="p-6 md:p-8 max-w-3xl"><ErrorCard error={error} /></div>;

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl md:text-3xl font-bold text-ink leading-tight">
            Briefing
          </h1>
          <p className="mt-1 text-sm text-ink-3">
            {(data?.article_count ?? 0).toLocaleString()} articles indexed
            <span className="mx-2 text-rule-2">·</span>
            {data?.important_unread_count ?? 0} unread important
          </p>
        </div>
        <button
          onClick={() => { startCrawl.reset(); startCrawl.mutate(); }}
          disabled={isCrawling}
          className="shrink-0 rounded-md bg-accent px-4 py-2 text-sm font-medium text-paper hover:bg-accent-hover disabled:opacity-50 transition-colors min-h-[44px]"
        >
          {isCrawling ? "Crawling…" : "Run Crawl"}
        </button>
      </div>

      {startCrawl.isError && (
        <div className="rounded-md bg-warn-muted p-3 text-sm text-warn font-medium" aria-live="polite">
          {startCrawl.error.message}
        </div>
      )}

      {/* Latest crawl */}
      {data?.latest_crawl_run && (
        <section>
          <CrawlStatusCard run={data.latest_crawl_run} />
        </section>
      )}

      {/* Stale running runs */}
      {data?.stale_running_runs && data.stale_running_runs.length > 0 && (
        <div className="rounded-md bg-warn-muted p-3 text-sm text-warn font-medium">
          {data.stale_running_runs.length} crawl run(s) appear stuck
        </div>
      )}

      {/* Important unread */}
      <section>
        <ImportantUnreadList items={data?.important_unread ?? []} />
      </section>

      {/* Source health */}
      <SourceHealthList
        failedSources={data?.failed_sources ?? []}
        unhealthySources={data?.unhealthy_sources ?? []}
      />
    </div>
  );
}
