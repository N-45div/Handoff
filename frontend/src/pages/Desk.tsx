import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { TaskPreview } from "../components/TaskPreview";
import { VerdictRow } from "../components/VerdictRow";
import { buildTask, investigate, sample, villageDemo, type Investigate, type Task } from "../lib/api";

const chatFilters = ["all", "dropped", "unclaimed", "duplicate", "kept"];
const evidenceFilters = ["all", "not_done", "partial", "unclear", "kept"];

export function Desk() {
  const [params] = useSearchParams();
  const [swarm, setSwarm] = useState("Nightshift");
  const [body, setBody] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Investigate | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [filter, setFilter] = useState("all");

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
  const evidence = Boolean(result?.evidence);
  const filters = evidence ? evidenceFilters : chatFilters;
  const tiles: [string, number][] = evidence
    ? [
        ["Promises", result?.promises ?? 0],
        ["Not done", c.not_done ?? 0],
        ["Partial", c.partial ?? 0],
        ["Kept", c.kept ?? 0],
      ]
    : [
        ["Promises", result?.promises ?? 0],
        ["Dropped", c.dropped ?? 0],
        ["Unclaimed", c.unclaimed ?? 0],
        ["Kept", c.kept ?? 0],
      ];
  const rows = (result?.verdicts || []).filter((v) => filter === "all" || v.verdict === filter);

  return (
    <main className="mx-auto max-w-6xl px-5 py-10">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-zinc-500">Desk</p>
      <h1 className="mt-2 max-w-xl text-3xl font-medium tracking-tight">
        Who promised what, and did they do it?
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">
        Open the AI Village investigation, or paste your own swarm or coding-agent log. Village data is
        research only; secrets never leave in an exported task.
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
            <button type="button" className="btn-ghost" onClick={() => load("trace")}>
              Agent trace
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
          {task && <TaskPreview task={task} />}
          {!result && !task && !error && (
            <p className="text-sm text-zinc-500">No investigation yet.</p>
          )}
          {result && (
            <>
              <div className="grid grid-cols-2 gap-3">
                {tiles.map(([k, v]) => (
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
              {result.private && (
                <p className="mt-3 font-mono text-[11px] text-emerald-300/80">
                  {result.private.ok
                    ? `Read on this laptop · ${result.private.model ?? "local model"} via Meterless · ${result.private.named ?? 0} promises named · ${result.private.receipts?.length ?? 0} local receipts · nothing sent to a cloud`
                    : result.private.reason}
                </p>
              )}
              <p className="mt-3 font-mono text-[11px] text-zinc-500">
                {result.name} · {result.source} · {result.engine}
              </p>
              {result.nemotron?.why && (
                <div className="mt-4 border-t border-zinc-800 pt-3">
                  <p className="text-sm leading-relaxed text-zinc-200">{result.nemotron.why}</p>
                  {result.nemotron.model && (
                    <p className="mt-1 font-mono text-[11px] text-zinc-500">
                      {result.nemotron.model} ·{" "}
                      {result.nemotron.receipt?.kind === "local"
                        ? "on this laptop via Meterless"
                        : `${result.nemotron.receipt?.provider ?? "nvidia"} via Meterless`}
                      {result.nemotron.receipt?.receipt_id && ` · receipt ${result.nemotron.receipt.receipt_id}`}
                      {result.nemotron.receipt?.ms ? ` · ${(result.nemotron.receipt.ms / 1000).toFixed(1)} s` : ""}
                    </p>
                  )}
                </div>
              )}
              {(result.nemotron?.skipped || result.nemotron?.ok === false) && (
                <p className="mt-4 border-t border-zinc-800 pt-3 text-sm text-amber-300">
                  {result.nemotron.reason || "Nemotron did not answer. The Zetaris verdicts still stand."}
                </p>
              )}
              {result.memory && (
                <p className="mt-2 font-mono text-[11px] text-zinc-500">
                  {result.memory.ok === false
                    ? result.memory.reason
                    : `H-MEM · ${result.memory.count ?? 0} cases in memory${
                        result.memory.stored_now ? ` · ${result.memory.stored_now} stored now` : ""
                      }`}
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

      {result?.agents && result.agents.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm uppercase tracking-wide text-zinc-500">Who left work undone</h2>
          <table className="mt-3 w-full font-mono text-[12px]">
            <thead className="text-left text-zinc-500">
              <tr>
                <th className="py-1 font-normal">Agent</th>
                <th className="font-normal">Promises</th>
                <th className="font-normal">Not done</th>
                <th className="font-normal">Partial</th>
                <th className="font-normal">Kept</th>
                <th className="font-normal">Undone</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {result.agents.map((a) => (
                <tr key={a.agent}>
                  <td className="py-1.5">{a.agent}</td>
                  <td>{a.promises}</td>
                  <td>{a.not_done}</td>
                  <td>{a.partial}</td>
                  <td>{a.kept}</td>
                  <td>{Math.round(a.undone_rate * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
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
                {f.replace("_", " ")}
              </button>
            ))}
          </div>
          <ol className="mt-4 divide-y divide-zinc-800">
            {rows.slice(0, 80).map((v, i) => (
              <VerdictRow key={v.id || i} v={v} />
            ))}
          </ol>
        </section>
      )}
    </main>
  );
}
