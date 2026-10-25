export type Listing = {
  id: string;
  title: string;
  notes?: string;
  license?: string;
  list_price_usd: number;
  platform_take_usd: number;
  seller_payout_usd: number;
};

export type Verdict = {
  id?: string;
  verdict: string;
  from?: string;
  slice?: string;
  at?: string;
  quote?: string;
  why?: string;
  change?: string;
  task?: string;
  turn_ids?: string[];
  turns_in_window?: string | number;
  judge_model?: string;
};

export type Turn = { id: string; created_at: string; action_type: string; action: string; output: string };

export type AgentRow = {
  agent: string;
  promises: number;
  kept: number;
  partial: number;
  not_done: number;
  unclear: number;
  undone_rate: number;
};

export type LedgerEntry = { action: string; actor: string; timestamp: number; newState?: { confidence?: number } };

export type Investigate = {
  name?: string;
  source?: string;
  engine?: string;
  warning?: string;
  task_blocked?: string;
  promises?: number;
  counts?: Record<string, number>;
  weeks?: { title: string; open: number; counts: Record<string, number> }[];
  verdicts?: Verdict[];
  improve?: Verdict[];
  evidence?: boolean;
  agents?: AgentRow[];
  memory?: { ok?: boolean; engine?: string; reason?: string; stored_now?: number; count?: number; cases?: { verdict?: string; quote?: string; from?: string }[] };
  nemotron?: { ok?: boolean; skipped?: boolean; why?: string; reason?: string; model?: string; route?: string };
  listing_blurb?: { ok?: boolean; text?: string; reason?: string };
};

export type Health = {
  zetaris?: boolean;
  nightshift?: boolean;
  nightshift_unauthorized?: boolean;
  nightshift_error?: string;
};

export type Task = {
  kind: string;
  title: string;
  prompt: string;
  license: string;
  for_sale: boolean;
  pricing?: { list_price_usd: number; platform_take_usd: number };
  verifier?: { passed: boolean; open: number };
  episode?: { steps?: unknown[]; terminal_reward?: number; reward_spec?: string };
};

async function readError(res: Response) {
  const data = await res.json().catch(() => ({}));
  throw new Error(data.detail || res.statusText);
}

export async function health() {
  const res = await fetch("/api/health");
  return res.json() as Promise<Health>;
}

export async function catalog() {
  const res = await fetch("/api/catalog");
  return res.json() as Promise<{ listings: Listing[] }>;
}

export async function sample(kind: string) {
  const res = await fetch(`/api/sample?kind=${encodeURIComponent(kind)}`);
  return res.json() as Promise<{ name: string; body: string }>;
}

export async function setPrice(id: string, list_price_usd: number) {
  const fd = new FormData();
  fd.set("listing_id", id);
  fd.set("list_price_usd", String(list_price_usd));
  const res = await fetch("/api/catalog/price", { method: "POST", body: fd });
  if (!res.ok) await readError(res);
  return res.json();
}

export async function investigate(swarm: string, body: string, file?: File | null) {
  const fd = new FormData();
  fd.set("swarm", swarm);
  fd.set("body", body);
  if (file) fd.set("file", file);
  const res = await fetch("/api/investigate", { method: "POST", body: fd });
  if (!res.ok) await readError(res);
  return res.json() as Promise<Investigate>;
}

export async function villageDemo() {
  const res = await fetch("/api/demo");
  if (!res.ok) await readError(res);
  return res.json() as Promise<Investigate>;
}

export async function citedTurns(ids: string[]) {
  const res = await fetch(`/api/turns?ids=${encodeURIComponent(ids.join(","))}`);
  if (!res.ok) await readError(res);
  return res.json() as Promise<{ turns: Turn[] }>;
}

export async function sendFeedback(promiseId: string, kind: "helpful" | "wrong") {
  const fd = new FormData();
  fd.set("promise_id", promiseId);
  fd.set("kind", kind);
  const res = await fetch("/api/feedback", { method: "POST", body: fd });
  if (!res.ok) await readError(res);
  return res.json() as Promise<{ memory: { confidence: number }; audit: { entries: LedgerEntry[] } }>;
}

export async function buildTask(swarm: string, body: string, file?: File | null) {
  const fd = new FormData();
  fd.set("swarm", swarm);
  fd.set("body", body);
  if (file) fd.set("file", file);
  const res = await fetch("/api/task", { method: "POST", body: fd });
  if (!res.ok) await readError(res);
  return res.json() as Promise<Task>;
}
