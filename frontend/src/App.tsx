import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import TradesPage from "./pages/TradesPage";
import GroupsPage from "./pages/GroupsPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import ImportPage from "./pages/ImportPage";
import SettingsPage from "./pages/SettingsPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="trades" element={<TradesPage />} />
        <Route path="groups" element={<GroupsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}

export default App;
