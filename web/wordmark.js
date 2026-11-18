"use strict";

function wordmarkHtml(name) {
  return `<span class="st-wordmark"><span class="st-wordmark-title">${String(name == null ? "" : name).replace(/[&<>"\']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "\'": "&#39;" }[c]))}</span>` +
    `<span class="st-wordmark-rule" aria-hidden="true">◆</span></span>`;
}
