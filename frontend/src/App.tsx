import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import GroupsPage from "./pages/GroupsPage";
import GroupDetailPage from "./pages/GroupDetailPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import ImportPage from "./pages/ImportPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="groups" element={<GroupsPage />} />
        <Route path="groups/:id" element={<GroupDetailPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="import" element={<ImportPage />} />
      </Route>
    </Routes>
  );
}

export default App;
