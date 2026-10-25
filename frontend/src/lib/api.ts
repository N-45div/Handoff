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
  verdict: string;
  from?: string;
  slice?: string;
  at?: string;
  quote?: string;
  why?: string;
  change?: string;
};

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
  memory?: { stored_now?: number; count?: number; cases?: { verdict?: string; quote?: string; from?: string }[] };
  nemotron?: { ok?: boolean; skipped?: boolean; why?: string; reason?: string };
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

export async function buildTask(swarm: string, body: string, file?: File | null) {
  const fd = new FormData();
  fd.set("swarm", swarm);
  fd.set("body", body);
  if (file) fd.set("file", file);
  const res = await fetch("/api/task", { method: "POST", body: fd });
  if (!res.ok) await readError(res);
  return res.json() as Promise<Task>;
}
