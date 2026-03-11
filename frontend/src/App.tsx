import { Suspense, lazy } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const GroupsPage = lazy(() => import("./pages/GroupsPage"));
const GroupDetailPage = lazy(() => import("./pages/GroupDetailPage"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const ImportPage = lazy(() => import("./pages/ImportPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function App() {
  return (
    <Suspense fallback={<div className="p-4 text-sm text-[--color-text-muted]">Loading page\u2026</div>}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="groups" element={<GroupsPage />} />
          <Route path="groups/:id" element={<GroupDetailPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
