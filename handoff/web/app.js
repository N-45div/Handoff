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
    + (data.task_blocked ? `<p class="warn">${data.task_blocked}</p>` : "")
    + `<p class="hint">${data.name || ""} · ${data.source || ""} · ${data.engine || ""}</p>`;

  $("weeks").innerHTML = (data.weeks || []).map((w) => `
    <div class="week">
      <h3>${w.title}</h3>
      <p>${w.open} open · kept ${w.counts.kept} · dropped ${w.counts.dropped} · unclaimed ${w.counts.unclaimed} · duplicate ${w.counts.duplicate}</p>
    </div>`).join("");

  $("filters").hidden = false;
  const tips = data.improve || [];
  $("improve").hidden = tips.length === 0;
  $("improve").innerHTML = tips.map((t) => `
    <li>
      <span class="badge ${t.verdict}">${t.verdict}</span>
      <span>${escapeHtml(t.from || "")}</span>
      <p class="quote">${escapeHtml(t.quote || "")}</p>
      <p class="why">${escapeHtml(t.change || "")}</p>
    </li>`).join("");
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
  const s = await (await fetch("/api/sample?kind=nightshift")).json();
  $("swarm").value = s.name;
  $("body").value = s.body;
});

$("load-coding").addEventListener("click", async () => {
  const s = await (await fetch("/api/sample?kind=coding")).json();
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

async function loadCatalog() {
  try {
    const data = await (await fetch("/api/catalog")).json();
    $("listings").innerHTML = (data.listings || []).map((row) => `
      <article class="listing">
        <h3>${escapeHtml(row.title || row.id)}</h3>
        <p class="hint">${escapeHtml(row.notes || "")} · ${escapeHtml(row.license || "")}</p>
        <p>List <b>$${Number(row.list_price_usd).toFixed(2)}</b> · take 20% = <b>$${Number(row.platform_take_usd).toFixed(2)}</b> · seller <b>$${Number(row.seller_payout_usd).toFixed(2)}</b></p>
        <form class="price" data-id="${escapeHtml(row.id)}">
          <label>Set price (USD)
            <input name="list_price_usd" type="number" min="0" step="0.01" value="${Number(row.list_price_usd)}" />
          </label>
          <button type="submit">Update</button>
        </form>
      </article>`).join("") || "<p class='hint'>No listings.</p>";
  } catch (err) {
    $("listings").textContent = String(err);
  }
}

$("listings").addEventListener("submit", async (e) => {
  const form = e.target.closest("form.price");
  if (!form) return;
  e.preventDefault();
  const fd = new FormData();
  fd.set("listing_id", form.dataset.id);
  fd.set("list_price_usd", form.list_price_usd.value);
  const res = await fetch("/api/catalog/price", { method: "POST", body: fd });
  if (!res.ok) {
    $("listings").textContent = "Price update failed";
    return;
  }
  await loadCatalog();
});

function downloadJson(name, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

$("build-task").addEventListener("click", async () => {
  const fd = new FormData($("ingest"));
  $("build-task").disabled = true;
  $("stats").textContent = "Building a task from this transcript…";
  try {
    const res = await fetch("/api/task", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    const v = data.verifier || {};
    const ep = data.episode || {};
    $("stats").classList.remove("empty");
    $("stats").innerHTML = `<p class="hint">${escapeHtml(data.prompt || "")}</p>
      <p>pass ${v.passed ? "yes" : "no"} · open ${v.open ?? 0} · steps ${(ep.steps || []).length} · terminal ${ep.terminal_reward}
      · list $${(data.pricing || {}).list_price_usd} · take $${(data.pricing || {}).platform_take_usd}</p>`;
    $("env-meta").textContent = `${data.kind} · ${data.license} · for_sale ${data.for_sale}`;
    downloadJson(`${(data.title || "task").replace(/\s+/g, "-").toLowerCase()}-task.json`, data);
  } catch (err) {
    $("stats").textContent = String(err);
  } finally {
    $("build-task").disabled = false;
  }
});

$("export-env").addEventListener("click", async () => {
  $("export-env").disabled = true;
  try {
    const s = await (await fetch("/api/sample?kind=nightshift")).json();
    const fd = new FormData();
    fd.set("swarm", s.name);
    fd.set("body", s.body);
    const res = await fetch("/api/task", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    $("env-meta").textContent = `${data.title} · ${data.episode?.reward_spec} · terminal ${data.episode?.terminal_reward} · ${data.license}`;
    downloadJson("nightshift-task.json", data);
  } catch (err) {
    $("env-meta").textContent = String(err);
  } finally {
    $("export-env").disabled = false;
  }
});

health();
loadCatalog();

const sample = new URLSearchParams(location.search).get("sample");
if (sample === "coding") {
  $("load-coding").click();
} else if (sample === "nightshift") {
  $("load-sample").click();
}
