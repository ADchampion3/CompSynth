// Types mirroring CompSynth backend Pydantic schemas

export type ReadState = "unread" | "read" | "later" | "ignored";
export type CrawlRunStatus =
  | "running"
  | "success"
  | "partial"
  | "failed"
  | "timed_out";
export type CrawlRunScope = "all" | "single";
export type SourceRunStatus = "running" | "success" | "failed";
export type SourceType = "rss" | "web" | "javascript";
export type SourceHealthStatus = "failed" | "stale" | "healthy";

export interface ErrorDetail {
  problem: string;
  cause: string;
  fix: string;
}

export interface ArticleResponse {
  article_id: string;
  source: string;
  url: string;
  title: string;
  summary: string;
  content: string;
  tags: string[];
  published_at: string | null;
  collected_at: string | null;
  liked: number;
}

export interface ArticleStateResponse {
  article_id: string;
  read_state: ReadState;
  user_note: string;
  last_viewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ArticlePageResponse {
  items: ArticleResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface ImportantArticleResponse {
  article: ArticleResponse;
  importance_score: number;
}

export interface ArticleStateUpdate {
  read_state: ReadState;
}

export interface ArticleLikeUpdate {
  liked: boolean;
}

export interface ArticleNoteUpdate {
  user_note: string;
}

export interface SelectorField {
  name: string;
  selector: string;
  type: string;
}

export interface SourceResponse {
  source_key: string;
  source_type: string;
  url: string;
  name: string | null;
  enabled: boolean;
  selectors: Record<string, string>[] | null;
  javascript: boolean;
}

export interface CrawlRunResponse {
  run_id: string;
  scope: string;
  status: CrawlRunStatus;
  started_at: string;
  finished_at: string | null;
  new_items: number;
  errors: string[];
  error_text: string | null;
}

export interface CrawlRunSourceResponse {
  id: number | null;
  run_id: string;
  source_key: string;
  source_type: string;
  source_url: string;
  status: SourceRunStatus;
  started_at: string;
  finished_at: string | null;
  new_items: number;
  error_text: string | null;
}

export interface CrawlRunDetailResponse {
  run: CrawlRunResponse;
  sources: CrawlRunSourceResponse[];
}

export interface ReportSummaryResponse {
  report_id: string;
  title: string;
  created_at: string;
}

export interface ReportDetailResponse extends ReportSummaryResponse {
  markdown: string;
}

export interface SourceHealthResponse {
  source_key: string;
  source_type: string;
  site_name: string;
  source_url: string;
  status: SourceHealthStatus;
  last_crawled_at: string;
  last_new_item_count: number;
  recent_zero_days: number;
  last_error: string | null;
}

export interface DashboardSummaryResponse {
  article_count: number;
  important_unread_count: number;
  important_unread: ImportantArticleResponse[];
  latest_crawl_run: CrawlRunResponse | null;
  failed_sources: CrawlRunSourceResponse[];
  unhealthy_sources: SourceHealthResponse[];
  stale_running_runs: CrawlRunResponse[];
}
