import { NavLink, Route, Routes } from "react-router-dom";

import { ConfigPage } from "./pages/ConfigPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { ProjectsPage } from "./pages/ProjectsPage";

export function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-eyebrow">视频流水线控制台</div>
          <div className="brand-title">项目控制中心</div>
        </div>
        <nav className="topnav">
          <NavLink to="/">概览</NavLink>
          <NavLink to="/projects">项目</NavLink>
          <NavLink to="/config">配置</NavLink>
        </nav>
      </header>
      <main className="page-shell">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/config" element={<ConfigPage />} />
        </Routes>
      </main>
    </div>
  );
}
