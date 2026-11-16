/* Shared helpers for the player screen and the harbor board. */
"use strict";

const COLORS = ["#b3261e", "#2d4a8a", "#2f7d5b", "#c58a1b", "#7a3b7d", "#1f7f8c", "#7a4a22", "#4f5d6b"];

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function money(n) {
  const v = Math.round(Number(n) || 0);
  return (v < 0 ? "-$" : "$") + Math.abs(v).toLocaleString("en-US");
}

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value);
  } catch (e) { /* private browsing: the token just lives for this page */ }
  return null;
}

async function loadInfo() {
  const r = await fetch("/api/info");
  return r.json();
}

/* Opens the live stream and calls onState with each new game state.
   The browser reconnects on its own if the server restarts. */
function listen(token, onState, onStatus) {
  const es = new EventSource("/events" + (token ? "?token=" + encodeURIComponent(token) : ""));
  es.onmessage = e => { onStatus(true); onState(JSON.parse(e.data)); };
  es.onerror = () => onStatus(false);
  return es;
}

function weatherBadge(level, names) {
  return '<span class="wx wx' + level + '">' + esc(names[level]) + "</span>";
}
