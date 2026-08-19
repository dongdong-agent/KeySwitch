import { useState } from "react";
import "./App.css";
import {
  OverviewPage,
  MatrixPage,
  ProvidersPage,
  KeysPage,
  AppsPage,
  SettingsPage,
} from "./pages";

const PAGES = [
  { id: "overview", icon: "📊", label: "总览" },
  { id: "matrix", icon: "🔑", label: "Key 配置" },
  { id: "providers", icon: "🏷️", label: "Provider" },
  { id: "keys", icon: "🔐", label: "Key 池" },
  { id: "apps", icon: "📦", label: "应用" },
  { id: "settings", icon: "⚙️", label: "设置" },
];

function App() {
  const [page, setPage] = useState("overview");

  return (
    <div className="app">
      <nav className="nav">
        <div className="nav-brand">
          <span className="nav-logo">🔑</span>
          <div>
            <div className="nav-title">KeySwitch</div>
            <div className="nav-sub">API Key 管理器</div>
          </div>
        </div>
        {PAGES.map((p) => (
          <button
            key={p.id}
            className={`nav-btn${page === p.id ? " active" : ""}`}
            onClick={() => setPage(p.id)}
          >
            <span className="nav-icon">{p.icon}</span>
            {p.label}
          </button>
        ))}
        <div className="nav-footer">Rust / Tauri 2</div>
      </nav>
      <main className="content">
        {page === "overview" && <OverviewPage />}
        {page === "matrix" && <MatrixPage />}
        {page === "providers" && <ProvidersPage />}
        {page === "keys" && <KeysPage />}
        {page === "apps" && <AppsPage />}
        {page === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}

export default App;
