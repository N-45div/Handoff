import { useState } from "react";
import { citedTurns, memoryNote, sendFeedback, type MemoryNote, type Turn, type Verdict } from "../lib/api";

function evidenceLabel(n: number) {
  if (n === 0) return "Evidence";
  return `Evidence · ${n} ${n === 1 ? "action" : "actions"}`;
}

export function VerdictRow({ v }: { v: Verdict }) {
  const [turns, setTurns] = useState<Turn[] | null>(null);
  const [memo, setMemo] = useState<MemoryNote | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const ids = v.turn_ids || [];

  async function toggle() {
    if (!open && turns === null && v.id) {
      setBusy(true);
      try {
        const [t, m] = await Promise.all([
          ids.length ? citedTurns(ids) : Promise.resolve({ turns: [] as Turn[] }),
          memoryNote(v.id),
        ]);
        setTurns(t.turns);
        setMemo(m);
      } catch (err) {
        setNote(String(err));
      } finally {
        setBusy(false);
      }
    }
    setOpen(!open);
  }

  async function review(kind: "helpful" | "wrong") {
    if (!v.id) return;
    setBusy(true);
    try {
      const res = await sendFeedback(v.id, kind);
      const n = res.audit.entries.length;
      setNote(
        `${kind === "wrong" ? "Marked wrong" : "Confirmed"} in H-MEM · confidence ${res.memory.confidence.toFixed(2)} · ${n} ledger entries`,
      );
    } catch (err) {
      setNote(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="py-4">
      <div className="flex flex-wrap gap-3 font-mono text-[11px] text-zinc-500">
        <span className={`badge ${v.verdict}`}>{v.verdict.replace("_", " ")}</span>
        <span>{v.from}</span>
        <span>{v.at?.slice(0, 16)}</span>
        {v.turns_in_window !== undefined && <span>{v.turns_in_window} actions in the next 24 h</span>}
      </div>
      <p className="mt-2 text-[15px]">{v.quote}</p>
      {v.task && <p className="mt-1 text-sm text-zinc-300">Promised: {v.task}</p>}
      <p className="mt-1 text-sm text-zinc-500">{v.why}</p>
      {v.judge_model && (
        <p className="mt-1 font-mono text-[11px] text-zinc-600">
          judged by {v.judge_model.replace("nvidia/", "")}
          {v.receipt_id ? ` via Meterless · receipt ${v.receipt_id}` : ""}
        </p>
      )}
      {v.id && (
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" className="btn-ghost" disabled={busy} onClick={toggle}>
            {open ? "Hide evidence" : evidenceLabel(ids.length)}
          </button>
          <button type="button" className="btn-ghost" disabled={busy} onClick={() => review("helpful")}>
            Confirm
          </button>
          <button type="button" className="btn-ghost" disabled={busy} onClick={() => review("wrong")}>
            Mark wrong
          </button>
        </div>
      )}
      {note && <p className="mt-2 font-mono text-[11px] text-zinc-400">{note}</p>}
      {open && turns && (
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-zinc-500">What the agent did · HANDOFF.cu_turns</p>
            {turns.length === 0 && <p className="mt-2 text-sm text-zinc-500">No action was cited.</p>}
            <ol className="mt-2 space-y-2 border-l border-zinc-800 pl-3">
              {turns.map((t) => (
                <li key={t.id} className="font-mono text-[11px] leading-5 text-zinc-400">
                  <span className="text-zinc-500">{t.created_at?.slice(0, 16)} · {t.action_type}</span>
                  <p className="whitespace-pre-wrap break-words text-zinc-300">{t.action}</p>
                  {t.output && <p className="whitespace-pre-wrap break-words text-zinc-500">→ {t.output}</p>}
                </li>
              ))}
            </ol>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-zinc-500">
              What it wrote in its memory · HANDOFF.memories
            </p>
            <p className="mt-1 text-[11px] text-zinc-600">The agent's own account. Context, not evidence.</p>
            <p className="mt-2 whitespace-pre-wrap break-words text-[12px] leading-5 text-zinc-400">
              {memo?.found ? memo.excerpt : memo?.reason}
            </p>
          </div>
        </div>
      )}
    </li>
  );
}
