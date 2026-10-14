import React, { useState, useCallback, useEffect } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  getSimStatus, getSimMetrics, startSim, stopSim, pauseSim, resumeSim, resetSim
} from "../api/client";
import { usePolling } from "../hooks/index";

const SCENARIOS = ["mixed", "genuine", "mistaken", "suspicious", "coordinated"];

export default function SimulationPage({ toast }) {
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState({
    target_rps: 5,
    concurrency: 5,
    duration_seconds: 120,
    scenario: "mixed",
    scenario_pct_genuine: 60,
    scenario_pct_mistaken: 25,
    scenario_pct_suspicious: 15,
    seed: 42,
  });
  const [history, setHistory] = useState([]); // time series for charts

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getSimStatus();
      setStatus(s);
    } catch {}
  }, []);
  usePolling(fetchStatus, 2000);

  // Build chart history from metrics
  useEffect(() => {
    if (!status?.metrics) return;
    const m = status.metrics;
    if (m.generated > 0) {
      setHistory((h) => {
        const now = new Date().toLocaleTimeString();
        const last = [...h, {
          time: now,
          processed: m.processed,
          failed: m.failed,
          rps: m.achieved_rps,
          genuine: m.prediction_counts?.Genuine || 0,
          mistaken: m.prediction_counts?.Mistaken || 0,
          suspicious: m.prediction_counts?.Suspicious || 0,
        }].slice(-60);
        return last;
      });
    }
  }, [status?.metrics?.processed]);

  const pctTotal = config.scenario_pct_genuine + config.scenario_pct_mistaken + config.scenario_pct_suspicious;
  const pctValid = Math.abs(pctTotal - 100) < 0.5;

  const handleStart = async () => {
    if (config.scenario === "mixed" && !pctValid) {
      toast("Scenario percentages must sum to 100%", "error"); return;
    }
    try {
      await startSim(config);
      toast("Simulation started", "success");
    } catch (e) { toast(e.message, "error"); }
  };

  const handleStop = async () => {
    try { await stopSim(); toast("Simulation stopped", "info"); } catch (e) { toast(e.message, "error"); }
  };
  const handlePause = async () => {
    try { await pauseSim(); toast("Simulation paused", "info"); } catch (e) { toast(e.message, "error"); }
  };
  const handleResume = async () => {
    try { await resumeSim(); toast("Simulation resumed", "success"); } catch (e) { toast(e.message, "error"); }
  };
  const handleReset = async () => {
    if (!confirm("Reset presentation counters? MongoDB records are preserved.")) return;
    try { await resetSim(); setHistory([]); toast("Counters reset", "info"); } catch (e) { toast(e.message, "error"); }
  };

  const simState = status?.status || "stopped";
  const metrics = status?.metrics || {};

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Traffic Simulation</div>
          <div className="page-subtitle">Control live Locust load generation from this dashboard</div>
        </div>
      </div>
      <div className="page-body">
        {/* Status bar */}
        <div className="sim-status-bar">
          <div className={`sim-status-indicator ${simState}`} />
          <span style={{ fontWeight: 600, textTransform: "capitalize", fontSize: "var(--text-sm)" }}>{simState}</span>
          {status?.run_id && <span className="text-mono text-muted">{status.run_id}</span>}
          <span style={{ marginLeft: "auto", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            Real Locust HTTP requests → FastAPI → Redis → MongoDB
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-6)" }}>
          {/* Controls */}
          <div className="card">
            <div className="card-header"><span className="card-title">Configuration</span></div>

            <div className="sim-controls" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <div className="form-group">
                <label className="form-label">Target RPS</label>
                <input type="number" className="form-input" min={1} max={50}
                  value={config.target_rps}
                  onChange={(e) => setConfig(c => ({ ...c, target_rps: +e.target.value }))}
                  disabled={simState === "running"} />
              </div>
              <div className="form-group">
                <label className="form-label">Concurrency</label>
                <input type="number" className="form-input" min={1} max={20}
                  value={config.concurrency}
                  onChange={(e) => setConfig(c => ({ ...c, concurrency: +e.target.value }))}
                  disabled={simState === "running"} />
              </div>
              <div className="form-group">
                <label className="form-label">Duration (sec)</label>
                <input type="number" className="form-input" min={10} max={3600}
                  value={config.duration_seconds}
                  onChange={(e) => setConfig(c => ({ ...c, duration_seconds: +e.target.value }))}
                  disabled={simState === "running"} />
              </div>
              <div className="form-group">
                <label className="form-label">Random Seed</label>
                <input type="number" className="form-input"
                  value={config.seed}
                  onChange={(e) => setConfig(c => ({ ...c, seed: +e.target.value }))}
                  disabled={simState === "running"} />
              </div>
            </div>

            <div className="form-group mb-4">
              <label className="form-label">Scenario</label>
              <select className="form-select" value={config.scenario}
                onChange={(e) => setConfig(c => ({ ...c, scenario: e.target.value }))}
                disabled={simState === "running"}>
                {SCENARIOS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
              </select>
            </div>

            {config.scenario === "mixed" && (
              <div style={{ marginBottom: "var(--space-4)" }}>
                <div className="section-heading">Mixed scenario proportions</div>
                {[
                  ["scenario_pct_genuine", "Genuine %", "var(--chart-genuine)"],
                  ["scenario_pct_mistaken", "Mistaken %", "var(--chart-mistaken)"],
                  ["scenario_pct_suspicious", "Suspicious %", "var(--chart-suspicious)"],
                ].map(([key, label, color]) => (
                  <div key={key} className="prob-row" style={{ marginBottom: "var(--space-3)" }}>
                    <span className="prob-label" style={{ color, width: "110px" }}>{label}</span>
                    <input type="range" min={0} max={100} value={config[key]}
                      onChange={(e) => setConfig(c => ({ ...c, [key]: +e.target.value }))}
                      disabled={simState === "running"}
                      style={{ flex: 1, accentColor: color }} />
                    <span className="prob-value">{config[key]}%</span>
                  </div>
                ))}
                {!pctValid && (
                  <div className="warning-box">Percentages sum to {pctTotal.toFixed(0)}% — must equal 100%</div>
                )}
              </div>
            )}

            {/* Control buttons */}
            <div className="flex gap-2" style={{ flexWrap: "wrap" }}>
              {simState === "stopped" && (
                <button className="btn btn-primary" onClick={handleStart}>▶ Start</button>
              )}
              {simState === "running" && (<>
                <button className="btn btn-secondary" onClick={handlePause}>⏸ Pause</button>
                <button className="btn btn-danger" onClick={handleStop}>⏹ Stop</button>
              </>)}
              {simState === "paused" && (<>
                <button className="btn btn-primary" onClick={handleResume}>▶ Resume</button>
                <button className="btn btn-danger" onClick={handleStop}>⏹ Stop</button>
              </>)}
              <button className="btn btn-secondary btn-sm" onClick={handleReset} style={{ marginLeft: "auto" }}>↺ Reset Counters</button>
            </div>
          </div>

          {/* Live metrics */}
          <div className="card">
            <div className="card-header"><span className="card-title">Live Metrics</span></div>
            <div className="grid-2" style={{ marginBottom: "var(--space-5)" }}>
              {[
                ["Generated", metrics.generated || 0, ""],
                ["Processed", metrics.processed || 0, ""],
                ["Failed", metrics.failed || 0, "var(--status-suspicious-text)"],
                ["Achieved RPS", (metrics.achieved_rps || 0).toFixed(1), "var(--brand-primary)"],
              ].map(([label, val, color]) => (
                <div key={label} className="metric-card" style={{ padding: "var(--space-4)" }}>
                  <div className="metric-label">{label}</div>
                  <div className="metric-value" style={color ? { color } : {}}>{val}</div>
                </div>
              ))}
            </div>
            <div className="section-heading">Prediction Distribution</div>
            <div style={{ display: "flex", gap: "var(--space-4)", marginBottom: "var(--space-4)" }}>
              {[
                ["Genuine", "var(--chart-genuine)"],
                ["Mistaken", "var(--chart-mistaken)"],
                ["Suspicious", "var(--chart-suspicious)"],
              ].map(([label, color]) => {
                const count = metrics.prediction_counts?.[label] || 0;
                const total = (metrics.prediction_counts?.Genuine || 0) + (metrics.prediction_counts?.Mistaken || 0) + (metrics.prediction_counts?.Suspicious || 0);
                const pct = total > 0 ? (count / total * 100).toFixed(1) : "0.0";
                return (
                  <div key={label} style={{ flex: 1, textAlign: "center" }}>
                    <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, color }}>{count}</div>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{label} ({pct}%)</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Charts */}
        {history.length > 1 && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-5)", marginTop: "var(--space-5)" }}>
            <div className="chart-container">
              <div className="chart-title">Prediction Distribution Over Time</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={history} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
                  <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
                  <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", borderRadius: "6px" }} />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                  <Bar dataKey="genuine" fill="var(--chart-genuine)" name="Genuine" />
                  <Bar dataKey="mistaken" fill="var(--chart-mistaken)" name="Mistaken" />
                  <Bar dataKey="suspicious" fill="var(--chart-suspicious)" name="Suspicious" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-container">
              <div className="chart-title">Achieved RPS Over Time</div>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={history} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
                  <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
                  <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", borderRadius: "6px" }} />
                  <Line type="monotone" dataKey="rps" stroke="var(--chart-total)" strokeWidth={2} dot={false} name="RPS" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        <div className="info-box" style={{ marginTop: "var(--space-5)" }}>
          ℹ️ Locust generates real HTTP requests to the FastAPI backend. The API runs Redis behavioral checks and XGBoost inference for every request. Predictions shown above are real model outputs, not simulated values.
        </div>
      </div>
    </>
  );
}
