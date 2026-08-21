import { useState, type ComponentType } from "react";
import "./App.css";
import logo from "./assets/keyswitch-logo.png";
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

// 页面组件引用（保持常驻挂载，切回时通过 active 触发重新加载）
const PAGES_ELEM: Record<string, ComponentType<{ active?: boolean }>> = {
  overview: OverviewPage,
  matrix: MatrixPage,
  providers: ProvidersPage,
  keys: KeysPage,
  apps: AppsPage,
  settings: SettingsPage,
};

function App() {
  const [page, setPage] = useState("overview");
  // 记录已访问过的页面：首次进入才挂载，之后常驻 DOM（display 显隐切换），
  // 切走不卸载、切回时通过 active 触发重新加载 —— 既不卡顿又能同步其它页面的修改
  const [visited, setVisited] = useState<Record<string, boolean>>({ overview: true });

  const open = (id: string) => {
    setPage(id);
    setVisited((v) => (v[id] ? v : { ...v, [id]: true }));
  };

  return (
    <div className="app">
      <nav className="nav">
        <div className="nav-brand">
          <img className="nav-logo" src={logo} alt="KeySwitch" />
          <div>
            <div className="nav-title">KeySwitch</div>
            <div className="nav-sub">API Key 管理器</div>
          </div>
        </div>
        {PAGES.map((p) => (
          <button
            key={p.id}
            className={`nav-btn${page === p.id ? " active" : ""}`}
            onClick={() => open(p.id)}
          >
            <span className="nav-icon">{p.icon}</span>
            {p.label}
          </button>
        ))}
        <div className="nav-footer">Rust / Tauri 2</div>
      </nav>
      <main className="content">
        {Object.entries(PAGES_ELEM).map(([id, Comp]) => (
          <div
            key={id}
            className="page-slot"
            style={{ display: page === id ? "block" : "none" }}
          >
            {visited[id] ? <Comp active={page === id} /> : null}
          </div>
        ))}
      </main>
    </div>
  );
}

export default App;
