import type { Task } from "../lib/api";

const tone: Record<string, string> = {
  kept: "text-emerald-400",
  partial: "text-amber-300",
  not_done: "text-orange-400",
  unclear: "text-[#8d867a]",
};

function reward(r: number | null) {
  if (r === null) return "not scored";
  return r > 0 ? `+${r}` : String(r);
}

export function TaskPreview({ task }: { task: Task }) {
  const rubric = task.verifier?.rubric || [];
  const evidence = task.grading === "evidence";
  return (
    <div className="mb-4 text-sm text-zinc-300">
      <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
        Task {task.version} · {evidence ? "graded on actions" : "graded on chat only"}
        {task.source?.store ? ` · ${task.source.store}` : ""}
      </p>
      <p className="mt-2 text-zinc-400">{task.prompt}</p>
      {evidence && rubric.length > 0 && (
        <ul className="mt-3 space-y-2">
          {rubric.slice(0, 8).map((r) => (
            <li key={r.id} className="font-mono text-xs leading-relaxed">
              <span className={`uppercase ${tone[r.verdict] || ""}`}>{r.verdict.replace("_", " ")}</span>{" "}
              <span className="text-zinc-300">{r.task}</span>
              <span className="text-zinc-500">
                {" "}
                · reward {reward(r.reward)}
                {r.cited?.length ? ` · cites ${r.cited.map((c) => c.id.slice(0, 10)).join(", ")}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 font-mono text-xs">
        pass {task.verifier?.passed ? "yes" : "no"}
        {evidence ? ` · score ${task.verifier?.score ?? "–"}` : ` · open ${task.verifier?.open}`}
        {task.pricing ? ` · $${task.pricing.list_price_usd} list` : " · not for sale"}
        {task.verifier?.spec ? ` · ${task.verifier.spec}` : ""}
      </p>
    </div>
  );
}
