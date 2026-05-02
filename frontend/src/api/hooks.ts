import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { apiGet, apiPatch, apiPost } from "./client";
import type {
  ArticleLikeUpdate,
  ArticleNoteUpdate,
  ArticlePageResponse,
  ArticleResponse,
  ArticleStateResponse,
  ArticleStateUpdate,
  CrawlRunDetailResponse,
  CrawlRunResponse,
  DashboardSummaryResponse,
  ReadState,
  ReportDetailResponse,
  ReportSummaryResponse,
  SourceResponse,
} from "./types";

// Dashboard
export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiGet<DashboardSummaryResponse>("/dashboard"),
  });
}

// Articles
export interface ArticleFilters {
  limit?: number;
  offset?: number;
  source?: string;
  tag?: string;
  liked?: boolean;
  query?: string;
}

export function useArticles(filters: ArticleFilters) {
  return useQuery({
    queryKey: ["articles", filters],
    queryFn: () =>
      apiGet<ArticlePageResponse>(
        "/articles",
        filters as Record<string, string | number | boolean | undefined>,
      ),
  });
}

export function useArticleDetail(articleId: string | undefined) {
  return useQuery({
    queryKey: ["articles", "detail", articleId],
    queryFn: () =>
      apiGet<ArticleResponse>("/articles/detail", {
        article_id: articleId,
      }),
    enabled: !!articleId,
  });
}

export function useArticleState(articleId: string | undefined) {
  return useQuery({
    queryKey: ["articles", "state", articleId],
    queryFn: () =>
      apiGet<ArticleStateResponse>("/articles/state", {
        article_id: articleId,
      }),
    enabled: !!articleId,
  });
}

export function useUpdateArticleState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      articleId,
      readState,
    }: {
      articleId: string;
      readState: ReadState;
    }) =>
      apiPatch<ArticleStateResponse>(
        "/articles/state",
        { article_id: articleId },
        { read_state: readState } satisfies ArticleStateUpdate,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["articles"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateArticleLike() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      articleId,
      liked,
    }: {
      articleId: string;
      liked: boolean;
    }) =>
      apiPatch<ArticleResponse>(
        "/articles/like",
        { article_id: articleId },
        { liked } satisfies ArticleLikeUpdate,
      ),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["articles"] });
      qc.invalidateQueries({
        queryKey: ["articles", "detail", variables.articleId],
      });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateArticleNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      articleId,
      userNote,
    }: {
      articleId: string;
      userNote: string;
    }) =>
      apiPatch<ArticleStateResponse>(
        "/articles/note",
        { article_id: articleId },
        { user_note: userNote } satisfies ArticleNoteUpdate,
      ),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({
        queryKey: ["articles", "state", variables.articleId],
      });
    },
  });
}

export function useRelatedArticles(articleId: string | undefined) {
  return useQuery({
    queryKey: ["articles", "related", articleId],
    queryFn: () =>
      apiGet<{ items: ArticleResponse[]; total: number; implemented: boolean }>(
        "/articles/related",
        { article_id: articleId },
      ),
    enabled: !!articleId,
  });
}

// Sources
export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: () => apiGet<SourceResponse[]>("/sources"),
  });
}

export function useImportYaml() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<{ imported: number }>("/sources/import-yaml"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });
}

// Crawls
export function useStartCrawl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<{ status: string }>("/crawls"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crawls"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useCrawls(limit = 20) {
  return useQuery({
    queryKey: ["crawls", limit],
    queryFn: () => apiGet<CrawlRunResponse[]>("/crawls", { limit }),
  });
}

export function useCrawlDetail(runId: string | undefined) {
  return useQuery({
    queryKey: ["crawls", runId],
    queryFn: () =>
      apiGet<CrawlRunDetailResponse>(`/crawls/${encodeURIComponent(runId!)}`),
    enabled: !!runId,
  });
}

// Reports
export function useReports() {
  return useQuery({
    queryKey: ["reports"],
    queryFn: () => apiGet<ReportSummaryResponse[]>("/reports"),
  });
}

export function useReportDetail(reportId: string | undefined) {
  return useQuery({
    queryKey: ["reports", reportId],
    queryFn: () =>
      apiGet<ReportDetailResponse>(
        `/reports/${encodeURIComponent(reportId!)}`,
      ),
    enabled: !!reportId,
  });
}
