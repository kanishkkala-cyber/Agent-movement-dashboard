import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./layout/Shell";
import DailyOverviewPage from "./pages/DailyOverviewPage";
import TrackingPage from "./pages/TrackingPage";

export default function Root() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Shell />}>
          <Route index element={<Navigate to="/daily" replace />} />
          <Route path="daily" element={<DailyOverviewPage />} />
          <Route path="tracking" element={<TrackingPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
