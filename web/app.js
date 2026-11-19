/* Sravanam — Audiobookshelf-style web player (vanilla JS, no build) */
const $ = (s) => document.querySelector(s);
let TOKEN = localStorage.getItem("sravanam_token") || "";
let ME = null;            // {id,name,email,is_admin}
let CATALOG = [];         // all series
let itemCache = {};       // id -> item

const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtDur = (s) => { if (!s) return ""; const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return h ? `${h}h ${m}m` : `${m}m`; };

/* ---------------- API ---------------- */
async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (TOKEN) headers["Authorization"] = "Bearer " + TOKEN;
  const r = await fetch(path, { ...opts, headers });
  if (r.status === 401) { signOut(); throw new Error("unauthorized"); }
  return r;
}
async function apiJson(path, opts = {}) {
  const r = await api(path, opts);
  return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) };
}

/* ---------------- auth UI ---------------- */
function showLogin() { $("#loginScreen").style.display = "grid"; $("#app").hidden = true; $("#player").hidden = true; }
function signOut() { TOKEN = ""; localStorage.removeItem("sravanam_token"); ME = null; showLogin(); }

async function doAuth(e) {
  e.preventDefault();
  const email = $("#fieldEmail").value.trim(), pass = $("#fieldPassword").value;
  const register = $("#tabRegister").classList.contains("active");
  if (register && !$("#fieldName").value.trim()) { alert("Enter your name"); return; }
  const path = register ? "/auth/register" : "/auth/login";
  const body = register ? { name: $("#fieldName").value.trim(), email, password: pass } : { email, password: pass };
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { alert(d.detail || "Something went wrong"); return; }
  TOKEN = d.access_token; localStorage.setItem("sravanam_token", TOKEN);
  await enterApp();
}

async function enterApp() {
  const { ok, data } = await apiJson("/auth/me");
  if (!ok) { signOut(); return; }
  ME = data;
  $("#loginScreen").style.display = "none";
  $("#app").hidden = false;
  $("#userName").textContent = ME.name || ME.email;
  $("#userEmail").textContent = ME.email;
  $("#userAvatar").textContent = (ME.name || ME.email || "?").charAt(0).toUpperCase();
  $("#adminNavBtn").hidden = !ME.is_admin;
  await refreshCatalog();
  go("home");
}

async function refreshCatalog() {
  const { data } = await apiJson("/catalog/series");
  CATALOG = data;
}

/* ---------------- navigation ---------------- */
function go(view, arg) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  const btn = document.querySelector(`.nav-item[data-view="${view}"]`);
  if (btn) btn.classList.add("active");
  if (view === "home") renderHome();
  else if (view === "browse") renderBrowse($("#searchInput").value || "");
  else if (view === "series") renderSeries(arg);
  else if (view === "requests") renderRequests();
  else if (view === "admin") renderAdmin();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------------- home ---------------- */
async function renderHome() {
  $("#screenTitle").textContent = "Home";
  $("#screenSub").textContent = "";
  const groups = groupBy(CATALOG, "category");
  const html = [`<div class="hero">
      <div class="heru-om">ॐ</div>
      <h3>Pravachanam, freely.</h3>
      <p>Listen to Chaganti Koteswara Rao's Ramayanam and Mahabharatam — ad-free, resume anywhere, request your next discourse. Everything is free; a voluntary sustainer pass keeps the road open.</p>
    </div>`];

  // Continue listening
  try {
    const { data: prog } = await apiJson("/progress");
    const rows = [];
    for (const p of prog.slice(0, 8)) {
      const it = await item(p.item_id);
      if (!it) continue;
      rows.push({ ...p, item: it });
    }
    if (rows.length) {
      html.push(`<div class="section"><div class="section-head"><h3>Continue listening</h3></div><div class="shelf">` +
        rows.map((r) => shelfCard(r.item, r.position_s)).join("") +
        `</div></div>`);
    }
  } catch (_) {}

  // Collections
  if (Object.keys(groups).length) {
    html.push(`<div class="section"><div class="section-head"><h3>Collections</h3></div><div class="shelf">` +
      Object.entries(groups).map(([cat, list]) => {
        const n = list.reduce((a, s) => a + s.item_count, 0);
        return `<div class="shelf-card" onclick="goFilter('${esc(cat)}')">
          <div class="cover">🕉</div><div class="c-body">
          <div class="c-title">${esc(cat.replace(/_/g, " "))}</div>
          <div class="c-meta">${list.length} series · ${n} episodes</div></div></div>`;
      }).join("") + `</div></div>`);
  }

  // All series
  html.push(`<div class="section"><div class="section-head"><h3>All series</h3></div><div class="grid">` +
    CATALOG.map((s) => card(s)).join("") + `</div></div>`);
  $("#content").innerHTML = html.join("");
}

/* ---------------- browse ---------------- */
function renderBrowse(q = "") {
  $("#screenTitle").textContent = "Browse library";
  $("#screenSub").textContent = "";
  const list = q ? CATALOG.filter((s) => (s.title + " " + s.speaker).toLowerCase().includes(q.toLowerCase())) : CATALOG;
  const groups = groupBy(list, "category");
  let html = "";
  for (const cat of Object.keys(groups)) {
    html += `<div class="category-label">${esc(cat.replace(/_/g, " "))}</div><div class="grid">` +
      groups[cat].map(card).join("") + `</div>`;
  }
  $("#content").innerHTML = html || '<div class="empty">Nothing matches that search.</div>';
}

/* ---------------- series detail ---------------- */
async function renderSeries(id) {
  const { ok, data } = await apiJson(`/catalog/series/${id}`);
  if (!ok) { $("#content").innerHTML = '<div class="empty">Series not found.</div>'; return; }
  $("#screenTitle").textContent = data.series.title;
  $("#screenSub").textContent = `${data.series.speaker} · ${data.items.length} episodes`;
  $("#content").innerHTML = `
    <div class="item-hero"><div class="big-om">🕉</div><div>
      <h3>${esc(data.series.title)}</h3>
      <div class="meta-line">${esc(data.series.speaker)} · ${data.items.length} episodes · ${fmtDur(data.items.reduce((a, i) => a + i.duration_s, 0))}</div>
    </div></div>
    <div class="list">` + data.items.map((it, ix) => `
      <div class="item" data-item-id="${it.id}">
        <span class="num">${it.index_no || ix + 1}</span>
        <span class="t">${esc(it.title)}</span>
        <span class="dur">${fmtDur(it.duration_s)}</span>
        <span class="play-ind">▶</span>
      </div>`).join("") + `</div>`;
  document.querySelectorAll(".item").forEach((row) => {
    row.onclick = () => playItemById(+row.dataset.itemId);
  });
}

/* ---------------- requests ---------------- */
async function renderRequests() {
  $("#screenTitle").textContent = "Requests";
  $("#screenSub").textContent = "";
  let mine = "";
  try {
    const { data } = await apiJson("/requests/mine");
    mine = data.length ? `<div class="section"><div class="section-head"><h3>My requests</h3></div>` +
      data.map((r) => `<div class="item" style="cursor:default"><span class="t">${esc(r.title)}</span><span class="dur"><span class="badge ${esc(r.status)}">${esc(r.status)}</span></span></div>`).join("") +
      `</div>` : "";
  } catch (_) {}
  $("#content").innerHTML = `
    <div class="req-form">
      <h4>Request a discourse</h4>
      <p class="muted">Tell us what you'd like — we'll try to bring it into the library.</p>
      <form id="requestForm">
        <input id="reqTitle" placeholder="e.g. Srimad Bhagavatam — Ninth Skandham" required/>
        <textarea id="reqNotes" placeholder="Notes / speaker / link (optional)"></textarea>
        <button class="btn primary" type="submit">Send request</button>
      </form>
      <div id="reqResult" class="muted" style="margin-top:10px"></div>
    </div>
    ${mine}`;
  $("#requestForm").onsubmit = async (ev) => {
    ev.preventDefault();
    const { ok } = await apiJson("/requests", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: $("#reqTitle").value.trim(), notes: $("#reqNotes").value.trim() }) });
    $("#reqResult").textContent = ok ? "Thank you — your request is in the queue." : "Could not send — try again.";
    if (ok) { $("#reqTitle").value = ""; $("#reqNotes").value = ""; renderRequests(); }
  };
}

/* ---------------- admin ---------------- */
async function renderAdmin() {
  if (!ME || !ME.is_admin) { $("#content").innerHTML = '<div class="empty">Forbidden.</div>'; return; }
  $("#screenTitle").textContent = "Admin";
  $("#screenSub").textContent = "";
  const { data: sum } = await apiJson("/admin/summary");
  $("#content").innerHTML = `
    <div class="stat-cards">
      <div class="stat"><div class="n">${sum.users}</div><div class="l">Users</div></div>
      <div class="stat"><div class="n">${sum.series}</div><div class="l">Series</div></div>
      <div class="stat"><div class="n">${sum.items}</div><div class="l">Episodes</div></div>
      <div class="stat"><div class="n">${sum.speakers}</div><div class="l">Speakers</div></div>
      <div class="stat"><div class="n">${sum.downloads}</div><div class="l">Downloads</div></div>
      <div class="stat"><div class="n">${sum.open_requests}</div><div class="l">Open requests</div></div>
    </div>
    <div class="section"><div class="section-head"><h3>Requests queue</h3><button class="btn ghost" id="ingestBtn">⟳ Re-scan catalogue</button></div>
      <div id="reqTable"></div>
    </div>`;
  $("#ingestBtn").onclick = async () => {
    $("#ingestBtn").disabled = true; $("#ingestBtn").textContent = "Scanning…";
    const { ok } = await apiJson("/admin/ingest", { method: "POST" });
    await refreshCatalog();
    $("#ingestBtn").disabled = false; $("#ingestBtn").textContent = ok ? "⟳ Re-scan (done)" : "⟳ Re-scan (failed)";
  };
  const { data: reqs } = await apiJson("/admin/requests");
  $("#reqTable").innerHTML = reqs.length ? `
    <table class="table"><thead><tr><th>#</th><th>Title</th><th>Requester</th><th>Status</th><th>Action</th></tr></thead><tbody>` +
    reqs.map((r) => `<tr>
      <td>${r.id}</td><td>${esc(r.title)}${r.notes ? `<div class="sub">${esc(r.notes)}</div>` : ""}</td>
      <td>${esc(r.requester)}</td>
      <td><span class="badge ${esc(r.status)}">${esc(r.status)}</span></td>
      <td><select data-rid="${r.id}">
        ${["open", "accepted", "added", "declined"].map((s) => `<option value="${s}" ${s === r.status ? "selected" : ""}>${s}</option>`).join("")}
      </select></td>
    </tr>`).join("") + `</tbody></table>` : '<div class="empty">No requests yet.</div>';
  document.querySelectorAll("#reqTable select").forEach((sel) => {
    sel.onchange = async () => {
      const { ok } = await apiJson(`/admin/requests/${sel.dataset.rid}`, { method: "PATCH",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: sel.value }) });
      if (ok) renderAdmin();
    };
  });
}

/* ---------------- helpers ---------------- */
function groupBy(arr, key) { const g = {}; for (const x of arr) (g[x[key]] = g[x[key]] || []).push(x); return g; }
function card(s) {
  return `<div class="card" onclick="go('series',${s.id})">
    <div class="c-title">${esc(s.title)}</div>
    <div class="c-meta">${esc(s.speaker)} · ${s.item_count} episodes</div></div>`;
}
function shelfCard(it, posSeconds) {
  const pct = it.duration_s ? Math.min(100, Math.round((posSeconds / it.duration_s) * 100)) : 0;
  return `<div class="shelf-card" onclick="go('series',${it.series_id})">
    <div class="cover">🕉</div><div class="c-body">
    <div class="c-title">${esc(it.title)}</div>
    <div class="c-meta">${fmtDur(it.duration_s)}</div>
    <div class="progress-shell"><div class="bar" style="width:${pct}%"></div></div></div></div>`;
}

async function item(id) {
  if (itemCache[id]) return itemCache[id];
  try { const { ok, data } = await apiJson(`/catalog/items/${id}`); if (ok) itemCache[id] = data; return ok ? data : null; } catch (_) { return null; }
}

/* ---------------- search ---------------- */
let searchTimer = null;
$("#searchInput").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => renderBrowse($("#searchInput").value.trim()), 200);
});

/* ---------------- player ---------------- */
let currentItem = null;
const audio = $("#audio");

async function playItemById(id) {
  const it = await item(id); if (!it) return;
  await playItem(it);
}
async function playItem(it) {
  currentItem = it;
  $("#nowTitle").textContent = it.title;
  $("#nowSeries").textContent = "";
  try { const sd = (await apiJson(`/catalog/series/${it.series_id}`)).data; $("#nowSeries").textContent = sd.series.title; } catch (_) {}
  audio.src = `/media/${it.id}/stream?token=${encodeURIComponent(TOKEN)}`;
  $("#player").hidden = false;
  $("#dlLink").href = `/media/${it.id}/download?token=${encodeURIComponent(TOKEN)}`;
  $("#dlLink").setAttribute("download", (it.title.replace(/\s+/g, "_") + ".mp3"));
  try {
    const { data: prog } = await apiJson("/progress");
    const p = prog.find((x) => x.item_id === it.id);
    if (p && p.position_s > 10) audio.currentTime = p.position_s;
  } catch (_) {}
  audio.play();
}

let lastSave = 0;
audio.addEventListener("timeupdate", () => {
  if (Math.floor(audio.currentTime) - lastSave >= 15) { lastSave = Math.floor(audio.currentTime); save(currentItem, audio.currentTime); }
});
audio.addEventListener("pause", () => save(currentItem, audio.currentTime));
audio.addEventListener("ended", () => { if (currentItem) playItemById(currentItem.id); save(currentItem, 0); });
async function save(it, pos) {
  if (!it || !pos) return;
  try { await api(`/progress/${it.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ position_s: Math.round(pos) }) }); } catch (_) {}
}

/* filtered jump from home collection card */
window.goFilter = (cat) => { renderBrowse(cat.replace(/_/g, " ")); }
/* NOTE: `function go()` above is already global (window.go), so inline onclick
   handlers like go('series',N) resolve it directly. Do NOT add `window.go = ...`
   here — that arrow calls go(), which is itself: infinite recursion (RangeError). */

/* ---------------- init ---------------- */
document.querySelectorAll(".nav-item").forEach((b) => b.addEventListener("click", () => go(b.dataset.view)));
$("#logoutBtn").onclick = signOut;
$("#loginForm").addEventListener("submit", doAuth);
$("#tabLogin").onclick = () => { $("#tabLogin").classList.add("active"); $("#tabRegister").classList.remove("active"); $("#fieldName").hidden = true; };
$("#tabRegister").onclick = () => { $("#tabRegister").classList.add("active"); $("#tabLogin").classList.remove("active"); $("#fieldName").hidden = false; };

if (TOKEN) enterApp(); else showLogin();