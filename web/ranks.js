"use strict";

const Ranks = (() => {
  let ranks = [], styles = {};
  const escape = s => String(s ?? "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function configure(data) {
    ranks = data.ranks || [];
    styles = data.promotion_styles || {};
  }
  function resolve(value) {
    const key = typeof value === "object" && value ? value.rank_id || value.rank || value.title : value;
    return ranks.find(r => r.id === key || r.title === key);
  }
  function style(value) {
    const rank = resolve(value), palette = rank && styles[rank.id];
    return palette ? ["tone", "deep", "metal"].map(k => `--rank-${k}:${palette[k]}`).join(";") : "";
  }
  function url(id) {
    if (!id) return "";
    const art = typeof Media !== "undefined" && Media.choose("rank", id, "badge", { mode: "fixed", strict: true });
    return art ? art.u : "/assets/rank-badges/" + encodeURIComponent(id) + ".png";
  }
  function seal(id, cls = "captain-rank-stamp") {
    return id ? `<img class="${escape(cls)}" src="${escape(url(id))}" alt="" onerror="this.remove()">` : "";
  }
  function label(value) {
    const rank = resolve(value);
    const title = rank ? rank.title : typeof value === "object" && value ? value.rank || value.title : value;
    if (!title) return "";
    if (!rank) return escape(title);
    return `<span class="captain-rank" style="${escape(style(rank.id))}" title="${escape(title)}">${seal(rank.id)}<span class="captain-rank-title">${escape(title)}</span></span>`;
  }
  return { configure, resolve, style, url, seal, label };
})();
