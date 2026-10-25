import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { catalog, type Listing } from "../lib/api";

const receipt = [
  { verdict: "kept", who: "Mira", line: "I'll wire the /ready probe and post the result." },
  { verdict: "duplicate", who: "Atlas", line: "I'll cut the production traffic shift at 10:00." },
  { verdict: "unclaimed", who: "Reed", line: "Could you send the rollback runbook to #ops?" },
  { verdict: "dropped", who: "Atlas", line: "I will post the cutover receipt after lunch." },
];

const tone: Record<string, string> = {
  kept: "text-emerald-400",
  dropped: "text-orange-400",
  unclaimed: "text-amber-300",
  duplicate: "text-sky-300",
};

export function Home() {
  const [listings, setListings] = useState<Listing[]>([]);

  useEffect(() => {
    catalog()
      .then((d) => setListings(d.listings || []))
      .catch(() => setListings([]));
  }, []);

  return (
    <main>
      <section className="mx-auto grid max-w-6xl items-end gap-16 px-6 pb-16 pt-16 lg:grid-cols-[1.05fr_0.95fr] lg:pt-24">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-[#e07a3d]">
            Tasks for labs
          </p>
          <h1 className="mt-4 max-w-[11ch] font-serif text-[58px] font-normal leading-[0.95] tracking-tight sm:text-[76px]">
            A transcript is not a task.
          </h1>
          <p className="mt-6 max-w-md text-[18px] leading-relaxed text-[#c9c2b4]">
            Handoff reads who promised what, scores kept, dropped, unclaimed, and duplicate, then
            emits the instruction, episode, and verifier a lab can train on.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              to="/desk?sample=coding"
              className="bg-[#f3efe6] px-4 py-2.5 text-[14px] font-semibold text-[#12110e]"
            >
              Build a task
            </Link>
            <Link to="/desk" className="px-3 py-2.5 text-[14px] text-[#c9c2b4] underline-offset-4 hover:underline">
              Open the desk
            </Link>
          </div>
        </div>

        <div className="border border-[#2a2722] bg-[#1a1814]">
          <div className="flex items-baseline justify-between border-b border-[#2a2722] px-4 py-3">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#8d867a]">
              Nightshift · handoff-reward@0.1
            </p>
            <p className="font-mono text-[12px] text-[#f3efe6]">$50 · seller $40</p>
          </div>
          <ul>
            {receipt.map((row) => (
              <li key={row.line} className="grid grid-cols-[88px_1fr] gap-3 border-b border-[#2a2722] px-4 py-3 last:border-b-0">
                <span className={`font-mono text-[11px] uppercase tracking-wider ${tone[row.verdict]}`}>
                  {row.verdict}
                </span>
                <p className="text-[14px] leading-snug">
                  <span className="text-[#8d867a]">{row.who} · </span>
                  {row.line}
                </p>
              </li>
            ))}
          </ul>
          <p className="px-4 py-3 font-mono text-[12px] text-[#8d867a]">
            pass no · 3 open · take 20%
          </p>
        </div>
      </section>

      <section className="border-y border-[#2a2722]">
        <div className="mx-auto grid max-w-6xl md:grid-cols-3">
          {[
            ["01", "Ingest", "A swarm log or a Cursor-shaped session. Extra keys stay out. Secrets never become a task."],
            ["02", "Score", "Zetaris is the query engine. The grade is the evidence for why the swarm stalled."],
            ["03", "Explain", "Nemotron, via Nightshift, writes one cited paragraph from those rows. It does not run the SQL."],
          ].map(([n, title, body], i) => (
            <article key={n} className={`px-6 py-10 ${i ? "md:border-l md:border-[#2a2722]" : ""}`}>
              <p className="font-mono text-[11px] text-[#e07a3d]">{n}</p>
              <h2 className="mt-3 font-serif text-[28px] font-normal">{title}</h2>
              <p className="mt-2 text-[15px] leading-relaxed text-[#c9c2b4]">{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="flex items-end justify-between gap-6">
          <div>
            <h2 className="font-serif text-[36px] font-normal">Listed tasks</h2>
            <p className="mt-1 text-[15px] text-[#8d867a]">Synthetic. Not for training. You set the price. We take 20%.</p>
          </div>
        </div>
        <div className="mt-8 border border-[#2a2722]">
          {listings.map((row) => (
            <div key={row.id} className="grid gap-2 border-b border-[#2a2722] px-5 py-5 last:border-b-0 md:grid-cols-[1fr_auto] md:items-center">
              <div>
                <h3 className="text-[17px]">{row.title}</h3>
                <p className="mt-1 text-[14px] text-[#8d867a]">{row.notes}</p>
              </div>
              <p className="font-mono text-[13px]">
                ${row.list_price_usd.toFixed(0)}
                <span className="text-[#8d867a]"> · seller ${row.seller_payout_usd.toFixed(0)}</span>
              </p>
            </div>
          ))}
          {listings.length === 0 && (
            <p className="px-5 py-6 text-[14px] text-[#8d867a]">Catalog is loading from the API on port 8787.</p>
          )}
        </div>
      </section>

      <footer className="border-t border-[#2a2722] px-6 py-8">
        <p className="mx-auto max-w-6xl text-[13px] text-[#8d867a]">
          Village logs are research only and are never listed. Alibi is prior work.
        </p>
      </footer>
    </main>
  );
}
