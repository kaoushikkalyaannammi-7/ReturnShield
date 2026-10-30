/**
 * ReturnShield API Client
 * Centralized fetch wrapper for all backend calls.
 */
const BASE = import.meta.env.VITE_API_URL || "";
const ADMIN_KEY = import.meta.env.VITE_ADMIN_KEY || "sim-admin-key-changeme";


async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({
      detail: res.statusText,
    }));

    const detail = err.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail != null
          ? JSON.stringify(detail)
          : `HTTP ${res.status}`;

    throw new Error(message);
  }

  return res.json();
}


function adminHeaders() {
  return { "X-Admin-Key": ADMIN_KEY };
}

// ── Health ──────────────────────────────────────────────────────
export const getHealth = () => apiFetch("/api/v1/health");
export const getReady = () => apiFetch("/api/v1/ready");
export const getModelInfo = () => apiFetch("/api/v1/model/info");

// ── Transactions ────────────────────────────────────────────────
export const getTransactions = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return apiFetch(`/api/v1/transactions${q ? "?" + q : ""}`);
};
export const getTransaction = (id) => apiFetch(`/api/v1/transactions/${id}`);

// ── Metrics ─────────────────────────────────────────────────────
export const getMetricsSummary = () => apiFetch("/api/v1/metrics/summary");
export const getMetricsTimeseries = (minutes = 60) =>
  apiFetch(`/api/v1/metrics/timeseries?minutes=${minutes}`);

// ── Simulation ──────────────────────────────────────────────────
export const getSimStatus = () => apiFetch("/api/v1/simulation/status");
export const getSimMetrics = () => apiFetch("/api/v1/simulation/metrics");
export const startSim = (config) =>
  apiFetch("/api/v1/simulation/start", {
    method: "POST", body: JSON.stringify(config), headers: adminHeaders(),
  });
export const stopSim = () =>
  apiFetch("/api/v1/simulation/stop", { method: "POST", headers: adminHeaders() });
export const pauseSim = () =>
  apiFetch("/api/v1/simulation/pause", { method: "POST", headers: adminHeaders() });
export const resumeSim = () =>
  apiFetch("/api/v1/simulation/resume", { method: "POST", headers: adminHeaders() });
export const resetSim = () =>
  apiFetch("/api/v1/simulation/reset", { method: "POST", headers: adminHeaders() });

// ── Reviews ─────────────────────────────────────────────────────
export const submitReview = (txId, data) =>
  apiFetch(`/api/v1/reviews/${txId}`, {
    method: "POST", body: JSON.stringify(data), headers: adminHeaders(),
  });
