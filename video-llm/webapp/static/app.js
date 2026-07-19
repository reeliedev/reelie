// ── tiny helpers ───────────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const el = (t, c) => { const e = document.createElement(t); if (c) e.className = c; return e; };
const views = ["input", "processing", "result", "page", "error"];
function show(name) {
  views.forEach(v => $("#view-" + v).classList.toggle("active", v === name));
  window.scrollTo(0, 0);
}
function fmtTs(s) {
  s = Math.round(s || 0);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// session id (groups corrections) — persists across a demo session
const SESSION = localStorage.getItem("sess") ||
  (localStorage.setItem("sess", "s" + Date.now().toString(36)), localStorage.getItem("sess"));

let JOB = null;      // current job id
let DATA = null;     // normalized result payload
let STATE = {};      // per-product UI state {id:{removed}}
let detectTimer = null;

// friendly processing checklist (keys match backend stage names)
const STEPS = [
  { stage: "download", text: "Getting your video ready" },
  { stage: "transcribe", text: "Listening to the audio" },
  { stage: "frames", text: "Watching your video" },
  { stage: "extract", text: "Finding your products" },
  { stage: "assemble", text: "Putting your routine together" },
];

// scanning chips that flash over the video during processing (honest, generic)
const DETECTS = [
  "🔍 reading a label", "✨ product found", "🎨 matching a shade",
  "🧴 spotting packaging", "🗣 catching a mention", "🔗 matching a brand",
];

// ═════════════════════════ INPUT ═══════════════════════════════════════════
$("#url-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const url = $("#url-input").value.trim();
  if (!url) return showInputError("Paste a video link first.");
  startJob({ url });
});
$("#file-input").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (f) startJob({ file: f });
});
$("#try-again").addEventListener("click", () => { show("input"); $("#input-error").hidden = true; });

function showInputError(msg) {
  const e = $("#input-error"); e.textContent = msg; e.hidden = false;
}

// ═════════════════════════ START A JOB ═════════════════════════════════════
async function startJob({ url, file }) {
  try {
    let res;
    if (file) {
      const fd = new FormData();
      fd.append("file", file);
      res = await fetch("/api/jobs", { method: "POST", body: fd });
    } else {
      res = await fetch("/api/jobs", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
    }
    if (!res.ok) throw new Error("start failed");
    const { job_id } = await res.json();
    JOB = job_id;
    enterProcessing();
    listen(job_id);
  } catch (err) {
    showInputError("Something went wrong starting that. Try again?");
  }
}

// ═════════════════════════ PROCESSING ══════════════════════════════════════
function enterProcessing() {
  const ul = $("#proc-steps"); ul.innerHTML = "";
  STEPS.forEach(s => {
    const li = el("li"); li.dataset.stage = s.stage;
    const dot = el("span", "dot");
    const txt = el("span"); txt.textContent = s.text;
    li.append(dot, txt); ul.append(li);
  });
  $("#proc-pct").textContent = "0%";
  $("#proc-timebar").style.width = "0%";
  $("#proc-label").textContent = "Analyzing your video…";
  $("#proc-thumb-img").removeAttribute("src");
  $("#proc-detects").innerHTML = "";
  $("#proc-cached").hidden = true;
  show("processing");
  startDetects();
}

function startDetects() {
  stopDetects();
  let i = 0;
  const pop = () => {
    const d = el("span", "detect");
    d.innerHTML = `<i></i>${DETECTS[i % DETECTS.length]}`;
    // scatter within the video panel
    d.style.left = (6 + Math.round((i * 37) % 55)) + "%";
    d.style.top = (14 + Math.round((i * 53) % 60)) + "%";
    $("#proc-detects").append(d);
    setTimeout(() => d.remove(), 2600);
    i++;
  };
  pop();
  detectTimer = setInterval(pop, 1400);
}
function stopDetects() { if (detectTimer) { clearInterval(detectTimer); detectTimer = null; } }

function applyProgress(ev) {
  $("#proc-label").textContent = ev.label;
  $("#proc-pct").textContent = ev.pct + "%";
  $("#proc-timebar").style.width = ev.pct + "%";
  const items = [...$("#proc-steps").children];
  const idx = STEPS.findIndex(s => s.stage === ev.stage);
  items.forEach((li, i) => {
    li.classList.toggle("done", i < idx);
    li.classList.toggle("active", i === idx);
    li.querySelector(".dot").textContent = i < idx ? "✓" : "";
  });
}

function listen(jobId) {
  fetch(`/api/jobs/${jobId}`).then(r => r.json()).then(snap => {
    if (snap.thumbnail) $("#proc-thumb-img").src = snap.thumbnail;
    if (snap.cached) $("#proc-cached").hidden = false;
  }).catch(() => {});

  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.addEventListener("progress", (e) => applyProgress(JSON.parse(e.data)));
  es.addEventListener("done", (e) => {
    es.close(); stopDetects();
    DATA = JSON.parse(e.data).result;
    renderResult();
  });
  es.addEventListener("failed", () => { es.close(); stopDetects(); show("error"); });
  es.onerror = () => { es.close(); pollFallback(jobId); };
}

async function pollFallback(jobId) {
  try {
    const snap = await (await fetch(`/api/jobs/${jobId}`)).json();
    (snap.events || []).forEach(applyProgress);
    if (snap.state === "done") { stopDetects(); DATA = snap.result; return renderResult(); }
    if (snap.state === "error") { stopDetects(); return show("error"); }
    setTimeout(() => pollFallback(jobId), 500);
  } catch { stopDetects(); show("error"); }
}

// ═════════════════════════ APPROVAL SCREEN ═════════════════════════════════
function mediaEmbed(container) {
  container.innerHTML = "";
  if (DATA.youtube_id) {
    const f = el("iframe");
    f.src = `https://www.youtube.com/embed/${DATA.youtube_id}`;
    f.allow = "encrypted-media; picture-in-picture";
    f.allowFullscreen = true;
    container.append(f);
  } else if (DATA.thumbnail) {
    const img = el("img"); img.src = DATA.thumbnail; container.append(img);
  } else {
    const ph = el("div", "thumb-ph"); ph.textContent = "🎬"; container.append(ph);
  }
}

function renderResult() {
  STATE = {};
  $("#result-title").textContent = DATA.title || "Your Skincare Routine";
  const shown = DATA.products.filter(p => p.bucket !== "hidden");
  $("#result-meta").textContent = `${shown.length} products found · in routine order`;
  mediaEmbed($("#result-media"));

  const wrap = $("#cards"); wrap.innerHTML = "";
  shown.forEach((p, i) => {
    const c = card(p);
    c.style.animationDelay = (i * 0.07) + "s";   // stagger the card-in
    wrap.append(c);
  });
  show("result");
}

function badgeClass(p) {
  const l = (p.evidence_label || "").toLowerCase();
  return ["spoken", "shown", "both"].includes(l) ? l : "listed";
}

function card(p) {
  STATE[p.id] = STATE[p.id] || { removed: false };
  const c = el("div", "card " + (p.bucket === "review" ? "review" : ""));
  c.dataset.id = p.id;

  const ph = el("div", "thumb-ph"); ph.textContent = "🧴";
  const body = el("div", "card-body");

  if (p.brand) { const b = el("div", "brand"); b.textContent = p.brand; body.append(b); }
  const name = el("div", "pname"); name.textContent = p.product_name; body.append(name);
  if (p.variant_or_shade) {
    const v = el("div", "variant"); v.textContent = p.variant_or_shade; body.append(v);
  }

  const meta = el("div", "meta-row");
  const badge = el("span", "badge " + badgeClass(p)); badge.textContent = p.evidence_label;
  const ts = el("span", "ts"); ts.textContent = "⏱ " + fmtTs(p.timestamp_s);
  meta.append(badge, ts); body.append(meta);

  if (p.bucket === "confirmed") {
    const chk = el("div", "check"); chk.textContent = "✓"; c.append(chk);
  } else {
    const q = el("div", "confirm-q"); q.textContent = "Did you use this? Confirm to keep it.";
    body.append(q);
    const acts = el("div", "review-actions");
    const yes = el("button", "yes"); yes.textContent = "Yes";
    const no = el("button", "no"); no.textContent = "No";
    const edit = el("button"); edit.textContent = "Edit";
    yes.onclick = () => resolveReview(c, p, true);
    no.onclick = () => resolveReview(c, p, false);
    edit.onclick = () => openEdit(p, c);
    acts.append(yes, no, edit); body.append(acts);
  }

  c.append(ph, body);
  return c;
}

function resolveReview(c, p, kept) {
  logCorrection(kept ? "confirm" : "reject", p);
  const acts = c.querySelector(".review-actions"); if (acts) acts.remove();
  const q = c.querySelector(".confirm-q"); if (q) q.remove();
  const tag = el("div", "resolved-tag " + (kept ? "kept" : "dropped"));
  tag.textContent = kept ? "✓ Added to your routine" : "✕ Removed";
  c.querySelector(".card-body").append(tag);
  c.classList.toggle("removed", !kept);
  STATE[p.id].removed = !kept;
  if (kept) c.classList.remove("review");
}

// ═════════════════════════ EDIT / ADD ══════════════════════════════════════
let MODAL_CTX = null;
function openEdit(p, cardEl) {
  MODAL_CTX = { mode: "edit", product: p, cardEl };
  $("#modal-title").textContent = "Edit product";
  $("#f-name").value = p.product_name || "";
  $("#f-brand").value = p.brand || "";
  $("#f-variant").value = p.variant_or_shade || "";
  $("#modal").hidden = false;
}
function openAdd() {
  MODAL_CTX = { mode: "add" };
  $("#modal-title").textContent = "Add a product";
  $("#f-name").value = ""; $("#f-brand").value = ""; $("#f-variant").value = "";
  $("#modal").hidden = false;
}
$("#add-missing").onclick = openAdd;
$("#modal-cancel").onclick = () => { $("#modal").hidden = true; };
$("#modal-save").onclick = () => {
  const after = {
    product_name: $("#f-name").value.trim(),
    brand: $("#f-brand").value.trim(),
    variant_or_shade: $("#f-variant").value.trim(),
  };
  if (!after.product_name) { $("#f-name").focus(); return; }

  if (MODAL_CTX.mode === "edit") {
    const p = MODAL_CTX.product;
    const before = { product_name: p.product_name, brand: p.brand, variant_or_shade: p.variant_or_shade };
    Object.assign(p, after);
    logCorrection("edit", p, before, after);
    p.bucket = "confirmed";
    MODAL_CTX.cardEl.replaceWith(card(p));
  } else {
    const p = {
      id: "new_" + Date.now(), ...after, evidence_label: "Added by you",
      timestamp_s: 0, bucket: "confirmed", confidence: 1,
    };
    DATA.products.push(p);
    logCorrection("add", p, null, after);
    $("#cards").append(card(p));
  }
  $("#modal").hidden = true;
};

// ═════════════════════════ CORRECTIONS LOG ═════════════════════════════════
function logCorrection(action, product, before, after) {
  fetch(`/api/jobs/${JOB}/corrections`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action, session_id: SESSION, video_id: DATA && DATA.video_id,
      product, before, after,
    }),
  }).catch(() => {}); // logging must never break the demo
}

// ═════════════════════════ PAGE PREVIEW ════════════════════════════════════
$("#see-page").onclick = () => renderPage();
$("#back-to-approve").onclick = () => show("result");

function approvedProducts() {
  return DATA.products
    .filter(p => p.bucket !== "hidden" && !(STATE[p.id] && STATE[p.id].removed))
    .sort((a, b) => (a.timestamp_s || 0) - (b.timestamp_s || 0));
}

function slugify(s) {
  return (s || "routine").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 24);
}

function renderPage() {
  $("#page-title").textContent = DATA.title || "Your Skincare Routine";
  $("#page-url").textContent = "retrieva.me/you/" + slugify(DATA.title);
  mediaEmbed($("#page-media"));
  const wrap = $("#page-products"); wrap.innerHTML = "";
  approvedProducts().forEach(p => {
    const item = el("div", "shop-item");
    const ph = el("div", "shop-ph"); ph.textContent = "🧴";
    const info = el("div", "shop-info");
    if (p.brand) { const b = el("div", "b"); b.textContent = p.brand; info.append(b); }
    const n = el("div", "n");
    n.textContent = p.product_name + (p.variant_or_shade ? ` — ${p.variant_or_shade}` : "");
    info.append(n);
    const btn = el("button", "shop-btn"); btn.textContent = "Shop";
    btn.onclick = () => { btn.textContent = "✓ Saved"; };
    item.append(ph, info, btn);
    wrap.append(item);
  });
  show("page");
}
