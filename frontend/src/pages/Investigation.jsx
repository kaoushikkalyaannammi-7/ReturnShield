import React, { useState, useEffect } from "react";
import { getTransaction, submitReview } from "../api/client";

const FEATURE_LABELS = {
  account_age_days: "Account Age (days)",
  total_past_orders: "Total Past Orders",
  historical_return_ratio: "Historical Return Ratio",
  past_inr_claims: "Past INR Claims",
  item_price: "Item Price (₹)",
  product_category_code: "Product Category",
  return_reason_code: "Return Reason",
  hours_since_delivery: "Hours Since Delivery",
  weight_discrepancy_grams: "Weight Discrepancy (g)",
  shared_identity_links: "Shared Identity Links",
  is_cod_order: "Cash on Delivery",
  purchased_in_sale: "Purchased During Sale",
};
const PRODUCT_CATS = { 1: "Electronics", 2: "Fashion/Apparel", 3: "Footwear", 4: "Home", 5: "Books" };
const RETURN_REASONS = { 1: "Wrong Size/Fit", 2: "Not Working", 3: "Empty Box/Missing", 4: "Physical Damage", 5: "Changed Mind" };

function ProbBar({ label, value, color }) {
  return (
    <div className="prob-row">
      <span className="prob-label">{label}</span>
      <div className="prob-bar-wrap">
        <div className="prob-bar-fill" style={{ width: `${(value * 100).toFixed(1)}%`, background: color }} />
      </div>
      <span className="prob-value">{(value * 100).toFixed(1)}%</span>
    </div>
  );
}

function RiskBar({ score }) {
  const cls = score >= 65 ? "high" : score >= 35 ? "elevated" : "low";
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Risk Score</span>
        <span style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: cls === "high" ? "var(--status-suspicious-text)" : cls === "elevated" ? "var(--status-mistaken-text)" : "var(--status-genuine-text)" }}>{score?.toFixed(1)} / 100</span>
      </div>
      <div className="risk-bar-wrap">
        <div className={`risk-bar-fill risk-bar-${cls}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

export default function InvestigationPage({ tx, toast, onBack }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reviewOutcome, setReviewOutcome] = useState("");
  const [reviewerId, setReviewerId] = useState("analyst-001");
  const [reviewNotes, setReviewNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!tx) return;
    setLoading(true);
    getTransaction(tx.transaction_id)
      .then(setDetail)
      .catch(() => setDetail(tx))
      .finally(() => setLoading(false));
  }, [tx?.transaction_id]);

  const handleReview = async () => {
    if (!reviewOutcome) { toast("Select an outcome", "error"); return; }
    setSubmitting(true);
    try {
      await submitReview(detail.transaction_id, { outcome: reviewOutcome, reviewer_id: reviewerId, notes: reviewNotes });
      toast("Review submitted", "success");
      setDetail(d => ({ ...d, review_status: "reviewed", review_outcome: reviewOutcome }));
    } catch (e) { toast(e.message, "error"); }
    finally { setSubmitting(false); }
  };

  if (!tx) return (
    <div className="page-body">
      <div className="empty-state">
        <div className="empty-state-icon">🔍</div>
        <div className="empty-state-text">Select a transaction from the table to investigate.</div>
        <button className="btn btn-secondary btn-sm" onClick={onBack}>← Back to Transactions</button>
      </div>
    </div>
  );

  const d = detail || tx;
  const proba = d.probabilities || d.prediction?.probabilities || {};
  const features = d.feature_snapshot || {};
  const behavioral = d.behavioral_evidence || {};
  const risk = d.risk || { score: d.risk_score, tier: d.risk_tier, recommended_action: d.recommended_action };

  return (
    <>
      <div className="page-header">
        <div>
          <button onClick={onBack} style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", marginBottom: "4px", background: "none", cursor: "pointer", border: "none" }}>← Back</button>
          <div className="page-title">Transaction Investigation</div>
          <div className="page-subtitle text-mono">{d.transaction_id}</div>
        </div>
      </div>
      <div className="page-body">
        {loading ? <div className="loading-overlay"><div className="spinner" /></div> : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-5)" }}>
            {/* Left column */}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
              {/* Transaction metadata */}
              <div className="card">
                <div className="card-header"><span className="card-title">Transaction</span>
                  <span className={`badge badge-${d.review_status === "reviewed" ? "genuine" : d.review_status === "pending" ? "mistaken" : "neutral"}`}>{d.review_status}</span>
                </div>
                <div className="drawer-grid">
                  {[
                    ["Request ID", d.request_id],
                    ["Customer", d.customer_name],
                    ["Product", d.product_name],
                    ["City", d.city],
                    ["Price", `₹${Number(d.item_price || 0).toLocaleString("en-IN")}`],
                    ["Category", PRODUCT_CATS[d.product_category_code] || d.product_category_code],
                    ["Reason", RETURN_REASONS[d.return_reason_code] || d.return_reason_code],
                    ["Created", d.created_at ? new Date(d.created_at).toLocaleString() : "—"],
                  ].map(([label, val]) => (
                    <div key={label} className="detail-row">
                      <span className="detail-label">{label}</span>
                      <span className="detail-value">{val}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Model Features */}
              <div className="card">
                <div className="card-header"><span className="card-title">Model Input Features</span></div>
                <div className="warning-box" style={{ marginBottom: "var(--space-3)" }}>
                  These are the 12 features used as model input. They do not prove abuse individually.
                </div>
                {Object.entries(FEATURE_LABELS).map(([key, label]) => {
                  const val = features[key];
                  let display = val == null ? "null (imputed)" : key === "product_category_code" ? PRODUCT_CATS[val] : key === "return_reason_code" ? RETURN_REASONS[val] : key === "is_cod_order" || key === "purchased_in_sale" ? (val ? "Yes" : "No") : String(val);
                  return (
                    <div key={key} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border-subtle)", fontSize: "var(--text-sm)" }}>
                      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
                      <span style={{ color: val == null ? "var(--text-muted)" : "var(--text-primary)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>{display}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right column */}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
              {/* Prediction */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title">Model Prediction</span>
                  <span className={`badge badge-${(d.predicted_label || "").toLowerCase()}`}>{d.predicted_label}</span>
                </div>
                <ProbBar label="Genuine" value={proba.Genuine || 0} color="var(--chart-genuine)" />
                <ProbBar label="Mistaken" value={proba.Mistaken || 0} color="var(--chart-mistaken)" />
                <ProbBar label="Suspicious" value={proba.Suspicious || 0} color="var(--chart-suspicious)" />
                <div className="info-box" style={{ marginTop: "var(--space-3)" }}>
                  Prediction is probabilistic. Suspicious classification warrants review, not automatic rejection.
                </div>
              </div>

              {/* Risk Policy */}
              <div className="card">
                <div className="card-header"><span className="card-title">Policy Decision</span></div>
                <div style={{ marginBottom: "var(--space-4)" }}>
                  <RiskBar score={risk.score || d.risk_score} />
                </div>
                {[
                  ["Risk Tier", risk.tier || d.risk_tier],
                  ["Recommended Action", risk.recommended_action || d.recommended_action],
                  ["Policy Version", d.policy_version || "1.0.0"],
                  ["Model Version", d.model_version || "—"],
                  ["Inference", `${d.inference_latency_ms?.toFixed(1) || "—"} ms`],
                  ["Total Latency", `${d.total_latency_ms?.toFixed(1) || "—"} ms`],
                ].map(([label, val]) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", fontSize: "var(--text-sm)", borderBottom: "1px solid var(--border-subtle)" }}>
                    <span style={{ color: "var(--text-muted)" }}>{label}</span>
                    <span style={{ color: "var(--text-primary)" }}>{val}</span>
                  </div>
                ))}
              </div>

              {/* Behavioral Evidence */}
              <div className="card">
                <div className="card-header"><span className="card-title">Behavioral Evidence (Redis)</span></div>
                {[
                  ["Requests (1h)", behavioral.recent_requests_1h],
                  ["Requests (24h)", behavioral.recent_requests_24h],
                  ["Amount (24h, ₹)", behavioral.recent_amount_24h?.toFixed(0)],
                  ["Shared Device Accounts", behavioral.shared_device_accounts],
                  ["Shared Identity Links", behavioral.shared_identity_links],
                  ["Repeated Attempts", behavioral.repeated_attempts],
                  ["Last Request (sec ago)", behavioral.time_since_last_request_seconds?.toFixed(0) ?? "First request"],
                ].map(([label, val]) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", fontSize: "var(--text-sm)", borderBottom: "1px solid var(--border-subtle)" }}>
                    <span style={{ color: "var(--text-muted)" }}>{label}</span>
                    <span style={{ color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>{val ?? "—"}</span>
                  </div>
                ))}
              </div>

              {/* Review */}
              {d.review_status !== "reviewed" && (
                <div className="card">
                  <div className="card-header"><span className="card-title">Analyst Review</span></div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                    <div className="form-group">
                      <label className="form-label">Reviewer ID</label>
                      <input className="form-input" value={reviewerId} onChange={e => setReviewerId(e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Outcome</label>
                      <select className="form-select" value={reviewOutcome} onChange={e => setReviewOutcome(e.target.value)}>
                        <option value="">Select outcome…</option>
                        <option value="confirmed_genuine">Confirmed Genuine</option>
                        <option value="confirmed_fraud">Confirmed Fraud</option>
                        <option value="escalated">Escalated</option>
                        <option value="cleared">Cleared</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Notes</label>
                      <textarea className="form-input" rows={3} value={reviewNotes} onChange={e => setReviewNotes(e.target.value)} style={{ resize: "vertical" }} />
                    </div>
                    <button className="btn btn-primary" onClick={handleReview} disabled={submitting}>
                      {submitting ? "Submitting…" : "Submit Review"}
                    </button>
                  </div>
                </div>
              )}
              {d.review_status === "reviewed" && (
                <div className="card">
                  <div className="card-header"><span className="card-title">Review Result</span></div>
                  <div style={{ color: "var(--status-genuine-text)", fontSize: "var(--text-sm)" }}>
                    Outcome: <strong>{d.review_outcome}</strong><br />
                    Reviewer: {d.reviewer_id}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
