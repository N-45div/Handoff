const $ = (id) => document.getElementById(id);
let current = null;
let filter = "all";

async function health() {
  try {
    const h = await (await fetch("/api/health")).json();
    $("health").textContent = h.zetaris ? "Zetaris live · Lightning SQL" : `Zetaris down · ${h.error || "unreachable"}`;
  } catch {
    $("health").textContent = "desk unreachable";
  }
}

function render(data) {
  current = data;
  const c = data.counts || {};
  $("stats").classList.remove("empty");
  $("stats").innerHTML = [
    ["Promises", data.promises ?? 0],
    ["Dropped", c.dropped ?? 0],
    ["Unclaimed", c.unclaimed ?? 0],
    ["Kept", c.kept ?? 0],
  ].map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("")
    + (data.warning ? `<p class="warn">${data.warning}</p>` : "")
    + `<p class="hint">${data.name || ""} · ${data.source || ""} · ${data.engine || ""}</p>`;

  $("weeks").innerHTML = (data.weeks || []).map((w) => `
    <div class="week">
      <h3>${w.title}</h3>
      <p>${w.open} open · kept ${w.counts.kept} · dropped ${w.counts.dropped} · unclaimed ${w.counts.unclaimed} · duplicate ${w.counts.duplicate}</p>
    </div>`).join("");

  $("filters").hidden = false;
  paintFeed();
}

function paintFeed() {
  const rows = (current?.verdicts || []).filter((v) => filter === "all" || v.verdict === filter);
  $("feed").innerHTML = rows.slice(0, 80).map((v) => `
    <li>
      <div class="meta">
        <span class="badge ${v.verdict}">${v.verdict}</span>
        <span>${v.from || "unknown"}</span>
        <span>${v.slice || ""}</span>
        <span>${(v.at || "").slice(0, 19)}</span>
      </div>
      <p class="quote">${escapeHtml(v.quote || "")}</p>
      <p class="why">${escapeHtml(v.why || "")}</p>
    </li>`).join("") || "<li class='why'>Nothing in this filter.</li>";
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

$("filters").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  filter = btn.dataset.v;
  for (const b of $("filters").querySelectorAll("button")) b.classList.toggle("on", b === btn);
  paintFeed();
});

$("load-sample").addEventListener("click", async () => {
  const s = await (await fetch("/api/sample")).json();
  $("swarm").value = s.name;
  $("body").value = s.body;
});

$("load-village").addEventListener("click", async () => {
  $("run").disabled = true;
  try {
    render(await (await fetch("/api/demo")).json());
  } catch (err) {
    $("stats").textContent = String(err);
  } finally {
    $("run").disabled = false;
  }
});

$("ingest").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData($("ingest"));
  $("run").disabled = true;
  $("stats").textContent = "Registering in Zetaris and scoring promises…";
  try {
    const res = await fetch("/api/investigate", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    render(data);
  } catch (err) {
    $("stats").textContent = String(err);
  } finally {
    $("run").disabled = false;
  }
});

health();
