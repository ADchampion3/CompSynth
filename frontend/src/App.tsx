import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import DashboardPage from "./components/dashboard/DashboardPage";
import InboxPage from "./components/inbox/InboxPage";
import ArticleDetailPage from "./components/article/ArticleDetailPage";
import ReportsListPage from "./components/reports/ReportsListPage";
import ReportDetailPage from "./components/reports/ReportDetailPage";
import SourcesPage from "./components/sources/SourcesPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="inbox" element={<InboxPage />} />
        <Route path="articles/:articleId" element={<ArticleDetailPage />} />
        <Route path="reports" element={<ReportsListPage />} />
        <Route path="reports/:reportId" element={<ReportDetailPage />} />
        <Route path="sources" element={<SourcesPage />} />
      </Route>
    </Routes>
  );
}
