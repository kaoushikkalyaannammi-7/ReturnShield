import React, { useState, useEffect, useCallback, useRef } from "react";
import { getReady } from "./api/client";
import { useSSE, usePolling, useToast } from "./hooks/index";
import OverviewPage from "./pages/Overview";
import TransactionsPage from "./pages/Transactions";
import SimulationPage from "./pages/Simulation";
import AnalyticsPage from "./pages/Analytics";
import InvestigationPage from "./pages/Investigation";

const NAV_ITEMS = [
  { id: "overview", label: "Overview", icon: "⬡" },
  { id: "transactions", label: "Live Transactions", icon: "⟳" },
  { id: "simulation", label: "Traffic Simulation", icon: "⚡" },
  { id: "analytics", label: "Risk Analytics", icon: "◈" },
];

function StatusDot({ ok }) {
  return <span className={`status-dot ${ok === null ? "loading" : ok ? "online" : "offline"}`} />;
}

export default function App() {
  const [page, setPage] = useState("overview");
  const [readiness, setReadiness] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [selectedTx, setSelectedTx] = useState(null);
  const { toasts, toast } = useToast();

  // Check readiness
  const checkReady = useCallback(async () => {
    try {
      const r = await getReady();
      setReadiness(r);
    } catch {
      setReadiness({ ready: false, model_loaded: false, redis_connected: false, mongodb_connected: false });
    }
  }, []);

  usePolling(checkReady, 10000);

  // SSE live events
  const handleEvent = useCallback((event, isHistory = false) => {
    if (event.type === "transaction") {
      const tx = { ...event.data, _isNew: !isHistory };
      setTransactions((prev) => {
        // Deduplicate
        const exists = prev.some((t) => t.transaction_id === tx.transaction_id);
        if (exists) return prev;
        return [tx, ...prev].slice(0, 500);
      });
    }
  }, []);

  const sseConnected = useSSE(handleEvent);

  // Investigation
  const handleInspect = useCallback((tx) => {
    setSelectedTx(tx);
    setPage("investigation");
  }, []);

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🛡</div>
          <div>
            <div className="sidebar-logo-text">ReturnShield</div>
            <div className="sidebar-logo-sub">Risk Platform</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              onClick={() => setPage(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-status">
          <div className="sidebar-status-title">Service Status</div>
          <div className="status-dot-row">
            <StatusDot ok={readiness?.model_loaded ?? null} />
            <span>Model</span>
          </div>
          <div className="status-dot-row">
            <StatusDot ok={readiness?.redis_connected ?? null} />
            <span>Redis</span>
          </div>
          <div className="status-dot-row">
            <StatusDot ok={readiness?.mongodb_connected ?? null} />
            <span>MongoDB</span>
          </div>
          <div className="status-dot-row">
            <StatusDot ok={sseConnected} />
            <span>Live Stream</span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        {page === "overview" && (
          <OverviewPage liveTransactions={transactions} onInspect={handleInspect} />
        )}
        {page === "transactions" && (
          <TransactionsPage liveTransactions={transactions} onInspect={handleInspect} />
        )}
        {page === "simulation" && <SimulationPage toast={toast} />}
        {page === "analytics" && <AnalyticsPage />}
        {page === "investigation" && (
          <InvestigationPage tx={selectedTx} toast={toast} onBack={() => setPage("transactions")} />
        )}
      </main>

      {/* Toast container */}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>{t.msg}</div>
        ))}
      </div>
    </div>
  );
}
