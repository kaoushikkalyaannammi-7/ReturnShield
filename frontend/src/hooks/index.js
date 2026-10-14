import { useState, useEffect, useRef, useCallback } from "react";

// ── useSSE: live event stream ────────────────────────────────────
export function useSSE(onEvent) {
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);
  const retryRef = useRef(null);

  const connect = useCallback(() => {
    const BASE = import.meta.env.VITE_API_URL || "";
    const es = new EventSource(`${BASE}/api/v1/events`);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => {
      setConnected(false);
      es.close();
      retryRef.current = setTimeout(connect, 3000);
    };
    es.onmessage = (e) => {
      try { onEvent(JSON.parse(e.data)); } catch {}
    };
    es.addEventListener("history", (e) => {
      try {
        const items = JSON.parse(e.data);
        items.forEach((item) => onEvent(item, true));
      } catch {}
    });
  }, [onEvent]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(retryRef.current);
      esRef.current?.close();
    };
  }, [connect]);

  return connected;
}

// ── usePolling: periodic refresh ─────────────────────────────────
export function usePolling(fn, interval = 3000, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    fn();
    const id = setInterval(fn, interval);
    return () => clearInterval(id);
  }, [fn, interval, enabled]);
}

// ── useToast ─────────────────────────────────────────────────────
export function useToast() {
  const [toasts, setToasts] = useState([]);
  const add = useCallback((msg, type = "info") => {
    const id = Date.now();
    setToasts((t) => [...t, { id, msg, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  return { toasts, toast: add };
}
