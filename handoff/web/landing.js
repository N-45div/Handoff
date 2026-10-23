const $ = (id) => document.getElementById(id);

async function health() {
  try {
    const h = await (await fetch("/api/health")).json();
    $("health").textContent = h.zetaris ? "Zetaris live" : `Zetaris down`;
  } catch {
    $("health").textContent = "desk unreachable";
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

async function loadCatalog() {
  try {
    const data = await (await fetch("/api/catalog")).json();
    $("listings").innerHTML = (data.listings || []).map((row) => `
      <article class="listing">
        <h3>${escapeHtml(row.title || row.id)}</h3>
        <p class="hint">${escapeHtml(row.notes || "")}</p>
        <p>List <b>$${Number(row.list_price_usd).toFixed(0)}</b> · seller <b>$${Number(row.seller_payout_usd).toFixed(0)}</b> · take 20%</p>
      </article>`).join("") || "<p class='hint'>No listings.</p>";
  } catch (err) {
    $("listings").textContent = String(err);
  }
}

health();
loadCatalog();
