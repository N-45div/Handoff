import { Link } from "react-router-dom";

// Real verdicts from the AI Village run (624 promises, June 2026 weeks). Ids match HANDOFF.verdicts.
const receipt = [
  {
    verdict: "kept",
    who: "GPT-5.5",
    line: "I'll fix only that stray fragment in Email 5 and leave the rest of the signed-off doc untouched.",
    proof: "find/replace on Email 5 in its own log",
  },
  {
    verdict: "partial",
    who: "GPT-5.5",
    line: "I'll update the Demo 2 docs/issues so Claude can lock the plan.",
    proof: "one issue updated, the docs were not",
  },
  {
    verdict: "not done",
    who: "Claude Opus 4.8",
    line: "I'll lead off Part 1 the moment you read the prompt.",
    proof: "no action toward it in the next 24 h",
  },
  {
    verdict: "unclear",
    who: "GPT-5",
    line: "I'll reassess after White's reply.",
    proof: "clicks only, the result was on screen",
  },
];

const tone: Record<string, string> = {
  kept: "text-emerald-400",
  partial: "text-amber-300",
  "not done": "text-orange-400",
  unclear: "text-[#8d867a]",
};

const numbers: [string, string][] = [
  ["624", "promises agents made to do work themselves"],
  ["44%", "kept, with the action in the agent's own log"],
  ["28%", "started, not finished"],
  ["25%", "no trace of the work within 24 hours"],
];

export function Home() {
  return (
    <main>
      <section className="mx-auto grid max-w-6xl items-end gap-16 px-6 pb-16 pt-16 lg:grid-cols-[1.05fr_0.95fr] lg:pt-24">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-[#e07a3d]">
            Post-mortems for agent teams
          </p>
          <h1 className="mt-4 max-w-[12ch] font-serif text-[58px] font-normal leading-[0.95] tracking-tight sm:text-[76px]">
            Your agents promised. Did they do it?
          </h1>
          <p className="mt-6 max-w-md text-[18px] leading-relaxed text-[#c9c2b4]">
            Handoff finds every promise agents make to each other in chat, then checks it against what
            each agent actually did on its own computer. Read from chat alone, 95% of them look kept.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to="/desk" className="bg-[#f3efe6] px-4 py-2.5 text-[14px] font-semibold text-[#12110e]">
              Open the desk
            </Link>
          </div>
        </div>

        <div className="border border-[#2a2722] bg-[#1a1814]">
          <div className="border-b border-[#2a2722] px-4 py-3">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#8d867a]">
              AI Village · four real verdicts
            </p>
          </div>
          <ul>
            {receipt.map((row) => (
              <li
                key={row.line}
                className="grid grid-cols-[88px_1fr] gap-3 border-b border-[#2a2722] px-4 py-3 last:border-b-0"
              >
                <span className={`font-mono text-[11px] uppercase tracking-wider ${tone[row.verdict]}`}>
                  {row.verdict}
                </span>
                <div>
                  <p className="text-[14px] leading-snug">
                    <span className="text-[#8d867a]">{row.who} · </span>
                    {row.line}
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-[#8d867a]">{row.proof}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="border-y border-[#2a2722]">
        <div className="mx-auto grid max-w-6xl grid-cols-2 md:grid-cols-4">
          {numbers.map(([n, label], i) => (
            <div key={n} className={`px-6 py-8 ${i ? "md:border-l md:border-[#2a2722]" : ""}`}>
              <p className="font-serif text-[40px] leading-none">{n}</p>
              <p className="mt-2 text-[14px] leading-snug text-[#c9c2b4]">{label}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl md:grid-cols-3">
        {[
          [
            "01",
            "One query layer",
            "Chat, 213,113 computer actions and 15,372 memory notes are separate sources. Zetaris joins them in one SQL layer.",
          ],
          [
            "02",
            "Judge against actions",
            "NVIDIA Nemotron names each promise, then checks it against what the agent ran. Its own narration never counts as proof.",
          ],
          [
            "03",
            "Remember and review",
            "Every verdict goes into Meterless H-MEM with its sources. Mark one wrong and the trust ledger records it.",
          ],
        ].map(([n, title, body], i) => (
          <article key={n} className={`px-6 py-10 ${i ? "md:border-l md:border-[#2a2722]" : ""}`}>
            <p className="font-mono text-[11px] text-[#e07a3d]">{n}</p>
            <h2 className="mt-3 font-serif text-[28px] font-normal">{title}</h2>
            <p className="mt-2 text-[15px] leading-relaxed text-[#c9c2b4]">{body}</p>
          </article>
        ))}
      </section>

      <footer className="border-t border-[#2a2722] px-6 py-8">
        <p className="mx-auto max-w-6xl text-[13px] text-[#8d867a]">
          AI Village data from AI Digest, used for research only. It is never exported as a training task.
        </p>
      </footer>
    </main>
  );
}
