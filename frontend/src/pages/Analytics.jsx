import React, { useState, useCallback } from "react";
import { getMetricsSummary, getMetricsTimeseries } from "../api/client";
import { usePolling } from "../hooks/index";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const COLORS = {
  Genuine: "var(--chart-genuine)",
  Mistaken: "var(--chart-mistaken)",
  Suspicious: "var(--chart-suspicious)",
};

export default function AnalyticsPage() {
  const [summary, setSummary] = useState(null);
  const [timeseries, setTimeseries] = useState([]);

  const fetchData = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([getMetricsSummary(), getMetricsTimeseries(60)]);
      setSummary(s);
      // Process timeseries into chart data
      const byMinute = {};
      for (const item of t.series || []) {
        const minute = item._id.minute;
        if (!byMinute[minute]) byMinute[minute] = { time: minute.slice(11,16), Genuine: 0, Mistaken: 0, Suspicious: 0 };
        byMinute[minute][item._id.label] = (byMinute[minute][item._id.label] || 0) + item.count;
      }
      setTimeseries(Object.values(byMinute).sort((a,b) => a.time.localeCompare(b.time)));
    } catch {}
  }, []);

  usePolling(fetchData, 10000);

  const pieData = summary ? [
    { name: "Genuine", value: summary.genuine_count },
    { name: "Mistaken", value: summary.mistaken_count },
    { name: "Suspicious", value: summary.suspicious_count },
  ] : [];

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Risk Analytics</div>
          <div className="page-subtitle">Aggregated metrics from real model decisions</div>
        </div>
      </div>
      <div className="page-body">
        {/* Summary metrics */}
        <div className="metric-grid mb-6">
          {[
            ["Total Processed", summary?.total_processed, ""],
            ["Genuine", summary?.genuine_count, "var(--chart-genuine)"],
            ["Mistaken", summary?.mistaken_count, "var(--chart-mistaken)"],
            ["Suspicious", summary?.suspicious_count, "var(--chart-suspicious)"],
            ["Avg Risk Score", summary?.avg_risk_score?.toFixed(1), ""],
            ["Avg Latency", summary?.avg_latency_ms?.toFixed(0) + " ms", ""],
          ].map(([label, val, color]) => (
            <div key={label} className="metric-card">
              <div className="metric-label">{label}</div>
              <div className="metric-value" style={color ? { color } : {}}>{val ?? "—"}</div>
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-5)", marginBottom: "var(--space-5)" }}>
          {/* Pie chart */}
          <div className="chart-container">
            <div className="chart-title">Prediction Distribution</div>
            {pieData.every(d => d.value === 0) ? (
              <div className="empty-state" style={{ height: 220 }}>
                <div className="empty-state-text">No data yet</div>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}>
                    {pieData.map((entry) => <Cell key={entry.name} fill={COLORS[entry.name]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", borderRadius: "6px" }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Time series */}
          <div className="chart-container">
            <div className="chart-title">Predictions by Minute (Last 60 min)</div>
            {timeseries.length === 0 ? (
              <div className="empty-state" style={{ height: 220 }}><div className="empty-state-text">No data yet</div></div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={timeseries} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
                  <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
                  <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", borderRadius: "6px" }} />
                  <Legend wrapperStyle={{ fontSize: "11px" }} />
                  <Bar dataKey="Genuine" fill="var(--chart-genuine)" stackId="a" />
                  <Bar dataKey="Mistaken" fill="var(--chart-mistaken)" stackId="a" />
                  <Bar dataKey="Suspicious" fill="var(--chart-suspicious)" stackId="a" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="warning-box">
          ⚠️ Metrics represent decisions from this session only. Model evaluation was conducted on a held-out test set (Macro F1=0.92) — see dataset_audit.md for limitations. The weight_discrepancy_grams feature shows near-perfect label separation in training data; real-world performance may differ.
        </div>
      </div>
    </>
  );
}
