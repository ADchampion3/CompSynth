import { useDashboard } from "../../api/hooks";
import { useStartCrawl } from "../../api/hooks";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";
import CrawlStatusCard from "./CrawlStatusCard";
import ImportantUnreadList from "./ImportantUnreadList";
import SourceHealthList from "./SourceHealthList";

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard();
  const startCrawl = useStartCrawl();

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <LoadingSkeleton lines={4} />
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error) return <ErrorCard error={error} />;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <button
          onClick={() => startCrawl.mutate()}
          disabled={startCrawl.isPending}
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {startCrawl.isPending ? "Starting..." : "Run Crawl"}
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded border border-gray-200 p-4">
          <div className="text-sm text-gray-500">Total Articles</div>
          <div className="text-2xl font-bold">{data?.article_count ?? 0}</div>
        </div>
        <div className="rounded border border-gray-200 p-4">
          <div className="text-sm text-gray-500">Important Unread</div>
          <div className="text-2xl font-bold">
            {data?.important_unread_count ?? 0}
          </div>
        </div>
      </div>

      {/* Latest crawl */}
      {data?.latest_crawl_run && (
        <CrawlStatusCard run={data.latest_crawl_run} />
      )}

      {/* Stale running runs */}
      {data?.stale_running_runs && data.stale_running_runs.length > 0 && (
        <div className="rounded border border-yellow-300 bg-yellow-50 p-4">
          <div className="text-sm font-medium text-yellow-800">
            {data.stale_running_runs.length} crawl run(s) appear stuck
          </div>
        </div>
      )}

      {/* Important unread */}
      <ImportantUnreadList items={data?.important_unread ?? []} />

      {/* Source health */}
      <SourceHealthList
        failedSources={data?.failed_sources ?? []}
        unhealthySources={data?.unhealthy_sources ?? []}
      />
    </div>
  );
}
