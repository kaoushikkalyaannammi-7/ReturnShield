import React, { useState, useCallback } from "react";
import { getMetricsSummary } from "../api/client";
import { usePolling } from "../hooks/index";

function RiskBadge({ label }) {
  const cls = label === "Genuine" ? "genuine" : label === "Mistaken" ? "mistaken" : "suspicious";
  return <span className={`badge badge-${cls}`}>{label}</span>;
}

function TierBadge({ tier }) {
  const cls = tier === "Low" ? "low" : tier === "Elevated" ? "elevated" : "high";
  return <span className={`badge badge-${cls}`}>{tier}</span>;
}

function fmt(n, digits = 0) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: digits });
}

export default function OverviewPage({ liveTransactions, onInspect }) {
  const [metrics, setMetrics] = useState(null);

  const fetchMetrics = useCallback(async () => {
    try { setMetrics(await getMetricsSummary()); } catch {}
  }, []);
  usePolling(fetchMetrics, 5000);

  const recent = liveTransactions.slice(0, 8);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Overview</div>
          <div className="page-subtitle">Real-time refund risk monitoring</div>
        </div>
      </div>
      <div className="page-body">
        {/* Metric cards */}
        <div className="metric-grid">
          <div className="metric-card">
            <div className="metric-label">Processed</div>
            <div className="metric-value">{fmt(metrics?.total_processed)}</div>
            <div className="metric-sub">All-time transactions</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Suspicious</div>
            <div className="metric-value" style={{ color: "var(--status-suspicious-text)" }}>{fmt(metrics?.suspicious_count)}</div>
            <div className="metric-sub">Require review</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Pending Review</div>
            <div className="metric-value" style={{ color: "var(--status-mistaken-text)" }}>{fmt(metrics?.pending_review)}</div>
            <div className="metric-sub">Elevated + High tier</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Avg Risk Score</div>
            <div className="metric-value">{fmt(metrics?.avg_risk_score, 1)}</div>
            <div className="metric-sub">Out of 100</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Avg Latency</div>
            <div className="metric-value">{fmt(metrics?.avg_latency_ms, 0)} <span style={{ fontSize: "var(--text-sm)", fontWeight: 400 }}>ms</span></div>
            <div className="metric-sub">Total API latency</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Failure Rate</div>
            <div className="metric-value">{metrics ? (metrics.failure_rate * 100).toFixed(2) : "—"}<span style={{ fontSize: "var(--text-sm)", fontWeight: 400 }}>%</span></div>
            <div className="metric-sub">Processing errors</div>
          </div>
        </div>

        {/* Recent live transactions */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Recent Transactions</span>
            <span className="text-muted" style={{ fontSize: "var(--text-xs)" }}>Live stream — updates automatically</span>
          </div>
          {recent.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">↓</div>
              <div className="empty-state-text">No transactions yet. Start a simulation or submit a request.</div>
            </div>
          ) : (
            <div className="table-container" style={{ border: "none" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Request ID</th>
                    <th>Customer</th>
                    <th>Product</th>
                    <th>Price (₹)</th>
                    <th>Prediction</th>
                    <th>Risk Score</th>
                    <th>Tier</th>
                    <th>Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((tx) => (
                    <tr key={tx.transaction_id} className={tx._isNew ? "new-entry" : ""} onClick={() => onInspect(tx)}>
                      <td className="text-mono">{tx.request_id}</td>
                      <td style={{ color: "var(--text-primary)" }}>{tx.customer_name}</td>
                      <td>{tx.product_name}</td>
                      <td>₹{fmt(tx.item_price, 0)}</td>
                      <td><RiskBadge label={tx.predicted_label} /></td>
                      <td style={{ color: tx.risk_score >= 65 ? "var(--status-suspicious-text)" : tx.risk_score >= 35 ? "var(--status-mistaken-text)" : "var(--status-genuine-text)" }}>
                        {tx.risk_score?.toFixed(1)}
                      </td>
                      <td><TierBadge tier={tx.risk_tier} /></td>
                      <td>{tx.total_ms?.toFixed(0)}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
