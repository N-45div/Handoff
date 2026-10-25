// Handoff's memory: the Meterless H-MEM reference engine behind a local HTTP port.
// Every verdict Handoff confirms is stored with its provenance (the promise and the
// computer-use turns it was checked against). A reviewer marking a verdict wrong
// lowers its confidence through the trust ledger, so the audit trail stays complete.

import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadHMEM } from "./src/engine.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.HMEM_PORT ?? 8790);
const STATE = process.env.HMEM_DIR ?? path.join(here, "..", ".handoff", "hmem");

const { HMEM, source } = await loadHMEM();
const hmem = new HMEM({ persistDir: STATE, actor: "handoff" });

function brief(r: any) {
  return {
    id: r.id,
    content: r.content,
    layer: r.layer,
    confidence: r.confidence,
    tags: r.tags,
    source: r.source,
    provenance: r.provenance,
  };
}

async function body(req: http.IncomingMessage): Promise<any> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  const text = Buffer.concat(chunks).toString("utf-8");
  return text ? JSON.parse(text) : {};
}

function send(res: http.ServerResponse, code: number, payload: unknown) {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(payload));
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://127.0.0.1:${PORT}`);
  try {
    if (req.method === "GET" && url.pathname === "/health") {
      return send(res, 200, { ok: true, engine: "meterless-hmem-reference", source, memories: hmem.store.all().length });
    }
    if (req.method === "POST" && url.pathname === "/remember") {
      const b = await body(req);
      if (!b.content || !b.source) return send(res, 400, { error: "content and source are required" });
      const record = hmem.add({
        content: String(b.content),
        type: "factual",
        tags: Array.isArray(b.tags) ? b.tags.map(String) : [],
        confidence: typeof b.confidence === "number" ? b.confidence : 0.7,
        source: String(b.source),
        provenance: { origin: "document", learnedAt: Date.now(), label: String(b.label ?? b.source), refs: b.refs ?? [] },
      });
      return send(res, 200, brief(record));
    }
    if (req.method === "POST" && url.pathname === "/query") {
      const b = await body(req);
      const result = hmem.query(String(b.q ?? ""), { topN: Number(b.topN ?? 8), threshold: Number(b.threshold ?? 0.1) });
      return send(res, 200, {
        memories: result.memories.map((m: any) => ({ relevance: m.relevance, ...brief(m.memory) })),
        strategy: result.trace.strategy,
        reason: result.trace.retrievalReason,
      });
    }
    if (req.method === "POST" && url.pathname === "/feedback") {
      const b = await body(req);
      if (!hmem.store.get(String(b.id))) return send(res, 404, { error: "unknown memory" });
      hmem.feedback(String(b.id), b.kind);
      return send(res, 200, brief(hmem.store.get(String(b.id))));
    }
    if (req.method === "GET" && url.pathname.startsWith("/audit/")) {
      const id = decodeURIComponent(url.pathname.slice("/audit/".length));
      return send(res, 200, { id, entries: hmem.ledger.history(id) });
    }
    if (req.method === "GET" && url.pathname === "/stats") {
      return send(res, 200, { memories: hmem.store.all().length, ledger: hmem.ledger.stats() });
    }
    send(res, 404, { error: "not found" });
  } catch (err) {
    send(res, 500, { error: String((err as Error).message ?? err).slice(0, 300) });
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`H-MEM (${source}) on http://127.0.0.1:${PORT}, state ${STATE}`);
});
