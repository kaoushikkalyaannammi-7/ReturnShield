import React, { useState, useCallback, useEffect } from "react";
import { getTransactions } from "../api/client";

function RiskBadge({ label }) {
  const cls = label === "Genuine" ? "genuine" : label === "Mistaken" ? "mistaken" : "suspicious";
  return <span className={`badge badge-${cls}`}>{label}</span>;
}
function TierBadge({ tier }) {
  const cls = tier === "Low" ? "low" : tier === "Elevated" ? "elevated" : "high";
  return <span className={`badge badge-${cls}`}>{tier}</span>;
}

export default function TransactionsPage({ liveTransactions, onInspect }) {
  const [dbTransactions, setDbTransactions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [labelFilter, setLabelFilter] = useState("");
  const [tierFilter, setTierFilter] = useState("");
  const [page, setPage] = useState(0);
  const LIMIT = 50;

  const fetchTx = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: page * LIMIT, limit: LIMIT };
      if (search) params.search = search;
      if (labelFilter) params.label = labelFilter;
      if (tierFilter) params.tier = tierFilter;
      const res = await getTransactions(params);
      setDbTransactions(res.transactions || []);
      setTotal(res.total || 0);
    } catch (e) {
      setDbTransactions([]);
    } finally {
      setLoading(false);
    }
  }, [page, search, labelFilter, tierFilter]);

  useEffect(() => { fetchTx(); }, [fetchTx]);
  // Refresh when new live transactions arrive
  useEffect(() => {
    if (liveTransactions.length > 0) fetchTx();
  }, [liveTransactions.length]);

  const displayTx = dbTransactions.length > 0 ? dbTransactions : liveTransactions;

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Live Transactions</div>
          <div className="page-subtitle">{total} total records</div>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={fetchTx}>↻ Refresh</button>
      </div>
      <div className="page-body">
        {/* Filters */}
        <div className="flex gap-3 mb-4" style={{ flexWrap: "wrap" }}>
          <input
            className="form-input"
            style={{ flex: "1", minWidth: "200px" }}
            placeholder="Search customer, product, city, ref…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          />
          <select className="form-select" value={labelFilter} onChange={(e) => { setLabelFilter(e.target.value); setPage(0); }}>
            <option value="">All Labels</option>
            <option value="Genuine">Genuine</option>
            <option value="Mistaken">Mistaken</option>
            <option value="Suspicious">Suspicious</option>
          </select>
          <select className="form-select" value={tierFilter} onChange={(e) => { setTierFilter(e.target.value); setPage(0); }}>
            <option value="">All Tiers</option>
            <option value="Low">Low</option>
            <option value="Elevated">Elevated</option>
            <option value="High">High</option>
          </select>
        </div>

        {loading ? (
          <div className="loading-overlay"><div className="spinner" /><span>Loading transactions…</span></div>
        ) : displayTx.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">⟳</div>
            <div className="empty-state-text">No transactions found. Start a simulation to generate traffic.</div>
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ref ID</th>
                  <th>Customer</th>
                  <th>Product</th>
                  <th>City</th>
                  <th>Price (₹)</th>
                  <th>Prediction</th>
                  <th>Risk Score</th>
                  <th>Tier</th>
                  <th>Action</th>
                  <th>Time (ms)</th>
                </tr>
              </thead>
              <tbody>
                {displayTx.map((tx) => (
                  <tr key={tx.transaction_id} className={tx._isNew ? "new-entry" : ""} onClick={() => onInspect(tx)}>
                    <td className="text-mono">{tx.request_id}</td>
                    <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>{tx.customer_name}</td>
                    <td>{tx.product_name}</td>
                    <td>{tx.city}</td>
                    <td>₹{Number(tx.item_price || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}</td>
                    <td><RiskBadge label={tx.predicted_label} /></td>
                    <td style={{ color: tx.risk_score >= 65 ? "var(--status-suspicious-text)" : tx.risk_score >= 35 ? "var(--status-mistaken-text)" : "var(--status-genuine-text)", fontWeight: 600 }}>
                      {Number(tx.risk_score || 0).toFixed(1)}
                    </td>
                    <td><TierBadge tier={tx.risk_tier} /></td>
                    <td style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{tx.recommended_action}</td>
                    <td>{Number(tx.total_ms || tx.total_latency_ms || 0).toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {total > LIMIT && (
          <div className="flex gap-3 items-center" style={{ marginTop: "var(--space-4)", justifyContent: "flex-end" }}>
            <button className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
              Page {page + 1} of {Math.ceil(total / LIMIT)}
            </span>
            <button className="btn btn-secondary btn-sm" disabled={(page + 1) * LIMIT >= total} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        )}
      </div>
    </>
  );
}
