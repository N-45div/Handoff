import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import {
  buildTask,
  catalog,
  investigate,
  sample,
  setPrice,
  villageDemo,
  type Investigate,
  type Listing,
  type Task,
} from "../lib/api";

const filters = ["all", "dropped", "unclaimed", "duplicate", "kept"] as const;

export function Desk() {
  const [params] = useSearchParams();
  const [swarm, setSwarm] = useState("Nightshift");
  const [body, setBody] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Investigate | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [filter, setFilter] = useState<(typeof filters)[number]>("all");
  const [listings, setListings] = useState<Listing[]>([]);

  async function loadListings() {
    const data = await catalog();
    setListings(data.listings || []);
  }

  useEffect(() => {
    loadListings().catch(() => undefined);
  }, []);

  useEffect(() => {
    const kind = params.get("sample");
    if (kind === "coding" || kind === "nightshift") {
      sample(kind).then((s) => {
        setSwarm(s.name);
        setBody(s.body);
      });
    }
  }, [params]);

  async function load(kind: string) {
    const s = await sample(kind);
    setSwarm(s.name);
    setBody(s.body);
    setFile(null);
  }

  async function runInvestigate(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError("");
    setTask(null);
    try {
      setResult(await investigate(swarm, body, file));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runVillage() {
    setBusy(true);
    setError("");
    try {
      setResult(await villageDemo());
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runTask() {
    setBusy(true);
    setError("");
    try {
      const data = await buildTask(swarm, body, file);
      setTask(data);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${(data.title || "task").replace(/\s+/g, "-").toLowerCase()}-task.json`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const c = result?.counts || {};
  const rows = (result?.verdicts || []).filter((v) => filter === "all" || v.verdict === filter);

  return (
    <main className="mx-auto max-w-6xl px-5 py-10">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-zinc-500">Desk</p>
      <h1 className="mt-2 max-w-xl text-3xl font-medium tracking-tight">
        Investigate, then build the task.
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">
        Village is research-only. Secrets cannot become a task.
      </p>

      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        <form onSubmit={runInvestigate} className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <label className="text-[11px] uppercase tracking-wide text-zinc-500">
            Swarm name
            <input
              className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-sm"
              value={swarm}
              onChange={(e) => setSwarm(e.target.value)}
            />
          </label>
          <label className="mt-3 block text-[11px] uppercase tracking-wide text-zinc-500">
            Transcript
            <textarea
              className="mt-1 min-h-48 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs leading-5"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </label>
          <div className="mt-3 flex flex-wrap gap-2">
            <label className="cursor-pointer rounded-md border border-zinc-700 px-3 py-2 text-[12px] uppercase tracking-wide">
              Attach
              <input
                type="file"
                className="hidden"
                accept=".jsonl,.json,.csv,.txt"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
            <button type="button" className="btn-ghost" onClick={() => load("nightshift")}>
              Ops swarm
            </button>
            <button type="button" className="btn-ghost" onClick={() => load("coding")}>
              Coding log
            </button>
            <button type="button" className="btn-ghost" onClick={runVillage}>
              Village
            </button>
            <button type="submit" disabled={busy} className="btn-ghost">
              Investigate
            </button>
            <button type="button" disabled={busy} className="btn-solid" onClick={runTask}>
              Build task
            </button>
          </div>
        </form>

        <div className="rounded-xl border border-zinc-800 p-4">
          {error && <p className="text-sm text-red-400">{error}</p>}
          {task && (
            <div className="mb-4 text-sm text-zinc-300">
              <p className="text-zinc-400">{task.prompt}</p>
              <p className="mt-2 font-mono text-xs">
                pass {task.verifier?.passed ? "yes" : "no"} · open {task.verifier?.open} · $
                {task.pricing?.list_price_usd} list
              </p>
            </div>
          )}
          {!result && !task && !error && (
            <p className="text-sm text-zinc-500">No investigation yet.</p>
          )}
          {result && (
            <>
              <div className="grid grid-cols-2 gap-3">
                {[
                  ["Promises", result.promises ?? 0],
                  ["Dropped", c.dropped ?? 0],
                  ["Unclaimed", c.unclaimed ?? 0],
                  ["Kept", c.kept ?? 0],
                ].map(([k, v]) => (
                  <div key={String(k)} className="border-b border-zinc-800 pb-2">
                    <p className="text-2xl font-medium">{v}</p>
                    <p className="text-[11px] uppercase tracking-wide text-zinc-500">{k}</p>
                  </div>
                ))}
              </div>
              {result.task_blocked && (
                <p className="mt-3 text-sm text-amber-400">{result.task_blocked}</p>
              )}
              {result.warning && <p className="mt-3 text-sm text-amber-400">{result.warning}</p>}
              <p className="mt-3 font-mono text-[11px] text-zinc-500">
                {result.name} · {result.source} · {result.engine}
              </p>
              {result.nemotron?.why && (
                <p className="mt-4 border-t border-zinc-800 pt-3 text-sm leading-relaxed text-zinc-200">
                  {result.nemotron.why}
                </p>
              )}
              {result.nemotron?.skipped && (
                <p className="mt-4 border-t border-zinc-800 pt-3 text-sm text-amber-300">
                  {result.nemotron.reason || "Nemotron skipped. The Zetaris score still stands."}
                </p>
              )}
              {result.memory && (
                <p className="mt-2 font-mono text-[11px] text-zinc-500">
                  H-MEM stored {result.memory.stored_now ?? 0} open promises · {result.memory.count ?? 0} prior cases
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {result?.improve && result.improve.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm uppercase tracking-wide text-zinc-500">Next session</h2>
          <ul className="mt-3 divide-y divide-zinc-800">
            {result.improve.map((t, i) => (
              <li key={i} className="py-3">
                <span className={`badge ${t.verdict}`}>{t.verdict}</span>
                <span className="ml-2 text-sm text-zinc-400">{t.from}</span>
                <p className="mt-1 text-sm">{t.quote}</p>
                <p className="text-sm text-zinc-500">{t.change}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result && (
        <section className="mt-8">
          <div className="flex flex-wrap gap-2">
            {filters.map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={filter === f ? "btn-solid" : "btn-ghost"}
              >
                {f}
              </button>
            ))}
          </div>
          <ol className="mt-4 divide-y divide-zinc-800">
            {rows.slice(0, 80).map((v, i) => (
              <li key={i} className="py-4">
                <div className="flex flex-wrap gap-3 font-mono text-[11px] text-zinc-500">
                  <span className={`badge ${v.verdict}`}>{v.verdict}</span>
                  <span>{v.from}</span>
                  <span>{v.at?.slice(0, 19)}</span>
                </div>
                <p className="mt-2 text-[15px]">{v.quote}</p>
                <p className="mt-1 text-sm text-zinc-500">{v.why}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="mt-16 border-t border-zinc-800 pt-10">
        <h2 className="text-xl font-medium">Listed tasks</h2>
        <p className="mt-1 text-sm text-zinc-500">Seller sets the list price. Take is 20%.</p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {listings.map((row) => (
            <article key={row.id} className="rounded-xl border border-zinc-800 p-5">
              <h3 className="font-medium">{row.title}</h3>
              <p className="mt-2 text-sm text-zinc-500">{row.notes}</p>
              <p className="mt-3 font-mono text-sm">
                ${row.list_price_usd.toFixed(0)} · seller ${row.seller_payout_usd.toFixed(0)}
              </p>
              <form
                className="mt-3 flex gap-2"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const input = e.currentTarget.elements.namedItem("price") as HTMLInputElement;
                  await setPrice(row.id, Number(input.value));
                  await loadListings();
                }}
              >
                <input
                  name="price"
                  type="number"
                  min={0}
                  step="0.01"
                  defaultValue={row.list_price_usd}
                  className="w-28 rounded-md border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-sm"
                />
                <button type="submit" className="btn-ghost">
                  Update
                </button>
              </form>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
