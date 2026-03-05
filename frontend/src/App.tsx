import { Suspense, lazy } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const GroupsPage = lazy(() => import("./pages/GroupsPage"));
const GroupDetailPage = lazy(() => import("./pages/GroupDetailPage"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const ImportPage = lazy(() => import("./pages/ImportPage"));

function App() {
  return (
    <Suspense fallback={<div className="p-4 text-sm text-gray-500">Loading page...</div>}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="groups" element={<GroupsPage />} />
          <Route path="groups/:id" element={<GroupDetailPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="import" element={<ImportPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
