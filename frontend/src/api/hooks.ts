import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { apiGet, apiPatch, apiPost, apiPut, apiDelete } from "./client";
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
  SourceCreateRequest,
  SourceResponse,
  SourceUpdateRequest,
  TagVocabularyResponse,
  TagsUpdateRequest,
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
  read_state?: string;
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
    onMutate: async ({ articleId, readState }) => {
      await qc.cancelQueries({ queryKey: ["articles"] });
      const allData = qc.getQueriesData({ queryKey: ["articles"] });
      const snapshots: [unknown, ArticlePageResponse][] = [];
      for (const [key, old] of allData) {
        if (!old || !("items" in old)) continue;
        snapshots.push([key, old]);
        qc.setQueryData(key, {
          ...old,
          items: old.items.map((a) =>
            a.article_id === articleId ? { ...a, read_state: readState } : a,
          ),
        });
      }
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.snapshots) {
        for (const [key, data] of ctx.snapshots) {
          qc.setQueryData(key, data);
        }
      }
    },
    onSettled: () => {
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
    onMutate: async ({ articleId, liked }) => {
      await qc.cancelQueries({ queryKey: ["articles"] });
      const allData = qc.getQueriesData({ queryKey: ["articles"] });
      const snapshots: [unknown, ArticlePageResponse][] = [];
      for (const [key, old] of allData) {
        if (!old || !("items" in old)) continue;
        snapshots.push([key, old]);
        qc.setQueryData(key, {
          ...old,
          items: old.items.map((a) =>
            a.article_id === articleId ? { ...a, liked: liked ? 1 : 0 } : a,
          ),
        });
      }
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.snapshots) {
        for (const [key, data] of ctx.snapshots) {
          qc.setQueryData(key, data);
        }
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["articles"] });
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

export function useCreateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SourceCreateRequest) =>
      apiPost<SourceResponse>("/sources", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });
}

export function useUpdateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, ...body }: SourceUpdateRequest & { key: string }) =>
      apiPut<SourceResponse>(`/sources/${encodeURIComponent(key)}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });
}

export function useDeleteSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) =>
      apiDelete(`/sources/${encodeURIComponent(key)}`),
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

// Tags
export function useTags() {
  return useQuery({
    queryKey: ["tags"],
    queryFn: () => apiGet<TagVocabularyResponse>("/tags"),
    staleTime: 60_000,
  });
}

export function useUpdateArticleTags() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      articleId,
      tags,
    }: {
      articleId: string;
      tags: string[];
    }) =>
      apiPatch<ArticleResponse>(
        "/articles/tags",
        { article_id: articleId },
        { tags } satisfies TagsUpdateRequest,
      ),
    onMutate: async ({ articleId, tags }) => {
      await qc.cancelQueries({ queryKey: ["articles"] });
      await qc.cancelQueries({ queryKey: ["tags"] });

      // Update articles list cache
      const allData = qc.getQueriesData({ queryKey: ["articles"] });
      const pageSnapshots: [unknown, ArticlePageResponse][] = [];
      for (const [key, old] of allData) {
        if (!old || !("items" in old)) continue;
        pageSnapshots.push([key, old]);
        qc.setQueryData(key, {
          ...old,
          items: old.items.map((a) =>
            a.article_id === articleId ? { ...a, tags } : a,
          ),
        });
      }

      // Update article detail cache
      const detailSnapshot = qc.getQueryData<ArticleResponse>(["articles", "detail", articleId]);
      if (detailSnapshot) {
        qc.setQueryData(["articles", "detail", articleId], {
          ...detailSnapshot,
          tags,
        });
      }

      return { pageSnapshots, detailSnapshot };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.pageSnapshots) {
        for (const [key, data] of ctx.pageSnapshots) {
          qc.setQueryData(key, data);
        }
      }
      if (ctx?.detailSnapshot && _vars) {
        qc.setQueryData(["articles", "detail", _vars.articleId], ctx.detailSnapshot);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}
