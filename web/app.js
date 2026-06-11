// Artvee Gallery — 纯静态前端 (no build, no framework)
// 数据从 web/data/*.json fetch。所有筛选/排序/搜索都在客户端完成。

const STATE = {
  artworks: [],
  stats: null,
  filter: { q: "", category: "", artist: "", recent: "", sort: "newest" },
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function fmtDate(iso) {
  if (!iso) return "";
  // Trim fractional seconds for compact display
  return iso.replace("T", " ").replace(/\..*$/, "");
}

function daysSince(iso) {
  if (!iso) return Infinity;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return Infinity;
  return (Date.now() - t) / (1000 * 60 * 60 * 24);
}

function fillStats() {
  if (!STATE.stats) return;
  const c = STATE.stats.counts || {};
  $$("#stats .num").forEach((el) => {
    const k = el.dataset.k;
    if (k === "last_downloaded_at") el.textContent = fmtDate(STATE.stats.last_downloaded_at) || "—";
    else el.textContent = c[k] ?? "—";
  });
}

function uniqueValues(key) {
  return Array.from(new Set(STATE.artworks.map((a) => a[key]).filter(Boolean))).sort((a, b) =>
    a.localeCompare(b)
  );
}

function fillSelect(sel, values, allLabel) {
  const cur = sel.value;
  sel.innerHTML = `<option value="">${allLabel}</option>` +
    values.map((v) => `<option value="${escapeAttr(v)}">${escapeHtml(v)}</option>`).join("");
  if (cur && values.includes(cur)) sel.value = cur;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

function applyFilters() {
  const f = STATE.filter;
  const q = f.q.trim().toLowerCase();
  let list = STATE.artworks.filter((a) => {
    if (f.category && a.category !== f.category) return false;
    if (f.artist && a.artist !== f.artist) return false;
    if (f.recent && daysSince(a.downloaded_at) > Number(f.recent)) return false;
    if (q) {
      const hay = [a.title, a.artist, a.category, a.source_url, a.tags].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  if (f.sort === "newest") {
    list.sort((a, b) => (b.downloaded_at || "").localeCompare(a.downloaded_at || ""));
  } else if (f.sort === "title") {
    list.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
  } else if (f.sort === "artist") {
    list.sort((a, b) => (a.artist || "").localeCompare(b.artist || ""));
  }
  return list;
}

function renderGrid() {
  const list = applyFilters();
  const grid = $("#grid");
  $("#visible-count").textContent = `${list.length} / ${STATE.artworks.length}`;
  if (list.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1;color:#6b7280;padding:40px;text-align:center;">
      没有匹配项。试试清空搜索 / 调整筛选。
    </div>`;
    return;
  }
  grid.innerHTML = list.map((a) => {
    const tags = (a.tags || "").split(";").filter(Boolean).slice(0, 3);
    const date = fmtDate(a.downloaded_at);
    return `
      <article class="card" data-id="${escapeAttr(a.id)}">
        <img class="thumb" loading="lazy"
             src="${escapeAttr(a.thumb_256 || a.image_path)}"
             onerror="this.onerror=null;this.src='${escapeAttr(a.image_path)}';"
             alt="${escapeAttr(a.title || a.id)}" />
        <div class="meta">
          <div class="title">${escapeHtml(a.title || a.id)}</div>
          <div class="artist">${escapeHtml(a.artist || "—")}</div>
          <div class="tags">
            ${(a.category ? `<span class="tag">${escapeHtml(a.category)}</span>` : "")}
            ${tags.map((t) => `<span class="tag">${escapeHtml(t.trim())}</span>`).join("")}
          </div>
          <div class="foot">
            <span>${escapeHtml(date)}</span>
            <span>${escapeHtml(a.download_variant || "")}</span>
          </div>
        </div>
      </article>
    `;
  }).join("");

  // Click handlers
  $$(".card").forEach((el) => {
    el.addEventListener("click", () => openDetail(el.dataset.id));
  });
}

function openDetail(id) {
  const a = STATE.artworks.find((x) => x.id === id);
  if (!a) return;
  const det = $("#detail");
  $("#detail-img").src = a.thumb_512 || a.image_path;
  $("#detail-img").alt = a.title || a.id;
  $("#detail-meta").innerHTML = `
    <h2>${escapeHtml(a.title || a.id)}</h2>
    <div class="row"><span class="k">艺术家</span><span class="v">${escapeHtml(a.artist || "—")}</span></div>
    <div class="row"><span class="k">分类</span><span class="v">${escapeHtml(a.category || "—")}</span></div>
    <div class="row"><span class="k">变体</span><span class="v">${escapeHtml(a.download_variant || "—")}</span></div>
    <div class="row"><span class="k">下载时间</span><span class="v">${escapeHtml(fmtDate(a.downloaded_at) || "—")}</span></div>
    <div class="row"><span class="k">tags</span><span class="v">${escapeHtml(a.tags || "—")}</span></div>
    <div class="row"><span class="k">usage</span><span class="v">${escapeHtml(a.usage_note || "—")}</span></div>
    <div class="row"><span class="k">原图</span><span class="v path">${escapeHtml(a.image_path || "")}</span></div>
    <div class="row"><span class="k">512 缩略</span><span class="v path">${escapeHtml(a.thumb_512 || "—")}</span></div>
    <div class="row"><span class="k">元数据</span><span class="v path">${escapeHtml(a.metadata_path || "—")}</span></div>
    <div class="row"><span class="k">source</span><span class="v"><a href="${escapeAttr(a.source_url)}" target="_blank" rel="noopener">${escapeHtml(a.source_url || "—")}</a></span></div>
  `;
  det.hidden = false;
}

function closeDetail() { $("#detail").hidden = true; }

function wireEvents() {
  $("#q").addEventListener("input", (e) => { STATE.filter.q = e.target.value; renderGrid(); });
  $("#f-category").addEventListener("change", (e) => { STATE.filter.category = e.target.value; renderGrid(); });
  $("#f-artist").addEventListener("change", (e) => { STATE.filter.artist = e.target.value; renderGrid(); });
  $("#f-recent").addEventListener("change", (e) => { STATE.filter.recent = e.target.value; renderGrid(); });
  $("#sort").addEventListener("change", (e) => { STATE.filter.sort = e.target.value; renderGrid(); });
  $("#detail-close").addEventListener("click", closeDetail);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDetail(); });
}

async function load() {
  try {
    const [arts, stats] = await Promise.all([
      fetch("data/artworks.json").then((r) => r.json()),
      fetch("data/gallery_stats.json").then((r) => r.json()),
    ]);
    STATE.artworks = arts;
    STATE.stats = stats;
  } catch (e) {
    $("#grid").innerHTML = `<div style="grid-column:1/-1;color:#b91c1c;padding:40px;">
      加载数据失败：${escapeHtml(String(e))}。<br/>
      请先运行：<code>python3 scripts/build_artvee_gallery.py --mode local</code>
    </div>`;
    return;
  }
  fillStats();
  fillSelect($("#f-category"), uniqueValues("category"), "全部分类");
  fillSelect($("#f-artist"), uniqueValues("artist"), "全部艺术家");
  renderGrid();
  wireEvents();
}

document.addEventListener("DOMContentLoaded", load);
