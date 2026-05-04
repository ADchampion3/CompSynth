import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import LoadingSkeleton from "./components/ui/LoadingSkeleton";

const DashboardPage = lazy(() => import("./components/dashboard/DashboardPage"));
const InboxPage = lazy(() => import("./components/inbox/InboxPage"));
const ArticleDetailPage = lazy(() => import("./components/article/ArticleDetailPage"));
const ReportsListPage = lazy(() => import("./components/reports/ReportsListPage"));
const ReportDetailPage = lazy(() => import("./components/reports/ReportDetailPage"));
const SourcesPage = lazy(() => import("./components/sources/SourcesPage"));
const SettingsPage = lazy(() => import("./components/settings/SettingsPage"));

function PageLoader() {
  return (
    <div className="p-6 md:p-8 max-w-3xl">
      <LoadingSkeleton lines={6} />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          index
          element={
            <Suspense fallback={<PageLoader />}>
              <DashboardPage />
            </Suspense>
          }
        />
        <Route
          path="inbox"
          element={
            <Suspense fallback={<PageLoader />}>
              <InboxPage />
            </Suspense>
          }
        />
        <Route
          path="articles/:articleId"
          element={
            <Suspense fallback={<PageLoader />}>
              <ArticleDetailPage />
            </Suspense>
          }
        />
        <Route
          path="reports"
          element={
            <Suspense fallback={<PageLoader />}>
              <ReportsListPage />
            </Suspense>
          }
        />
        <Route
          path="reports/:reportId"
          element={
            <Suspense fallback={<PageLoader />}>
              <ReportDetailPage />
            </Suspense>
          }
        />
        <Route
          path="sources"
          element={
            <Suspense fallback={<PageLoader />}>
              <SourcesPage />
            </Suspense>
          }
        />
        <Route
          path="settings"
          element={
            <Suspense fallback={<PageLoader />}>
              <SettingsPage />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}
