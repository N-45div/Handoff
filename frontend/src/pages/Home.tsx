import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { catalog, type Listing } from "../lib/api";

const snippet = `{
  "kind": "handoff-task",
  "prompt": "Keep every promise in this PR.",
  "verifier": "handoff-reward@0.1",
  "for_sale": true
}`;

export function Home() {
  const [listings, setListings] = useState<Listing[]>([]);

  useEffect(() => {
    catalog()
      .then((d) => setListings(d.listings || []))
      .catch(() => setListings([]));
  }, []);

  return (
    <main>
      <section className="mx-auto grid max-w-6xl gap-12 px-5 pb-20 pt-16 lg:grid-cols-2 lg:items-center lg:pt-24">
        <div>
          <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-zinc-500">
            Track 02 · Open Agent Hackathon
          </p>
          <h1 className="max-w-[12ch] text-[52px] font-medium leading-[1.05] tracking-tight sm:text-[64px]">
            Turn transcripts into lab tasks.
          </h1>
          <p className="mt-5 max-w-md text-[17px] leading-relaxed text-zinc-400">
            Handoff is the agent that scores promises in a swarm or coding-agent log, then emits a
            task: instruction, episode, verifier. Labs train on that. Dumps are not the product.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/desk"
              className="rounded-md bg-white px-4 py-2.5 text-[13px] font-medium text-zinc-950"
            >
              Open the desk
            </Link>
            <Link
              to="/desk?sample=coding"
              className="rounded-md border border-zinc-700 px-4 py-2.5 text-[13px] font-medium text-zinc-200 hover:border-zinc-500"
            >
              Try a coding log
            </Link>
          </div>
        </div>
        <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 shadow-[0_0_0_1px_rgba(255,255,255,0.04)]">
          <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-2.5 font-mono text-[11px] text-zinc-500">
            <span className="size-2 rounded-full bg-zinc-700" />
            handoff_build_task
          </div>
          <pre className="overflow-x-auto p-5 font-mono text-[13px] leading-6 text-zinc-300">
            {snippet}
          </pre>
        </div>
      </section>

      <section className="border-y border-zinc-800">
        <div className="mx-auto grid max-w-6xl gap-px bg-zinc-800 md:grid-cols-3">
          {[
            ["01", "Ingest", "JSONL or CSV. Speaker + content, or Cursor / Claude role blocks. Secrets never become a task."],
            ["02", "Score", "Kept, dropped, unclaimed, duplicate — cited from the log on Zetaris. That is why it stalled."],
            ["03", "Emit", "Instruction + OpenEnv episode + reward. Seller sets the price. Handoff takes 20%."],
          ].map(([n, t, d]) => (
            <article key={n} className="bg-zinc-950 px-6 py-10">
              <p className="font-mono text-[11px] text-zinc-500">{n}</p>
              <h2 className="mt-3 text-lg font-medium">{t}</h2>
              <p className="mt-2 text-sm leading-relaxed text-zinc-400">{d}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-20">
        <div className="grid gap-12 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-medium tracking-tight">Who it’s for</h2>
            <ul className="mt-6 space-y-4 text-[15px] leading-relaxed text-zinc-400">
              <li>
                <span className="text-white">Labs.</span> Consented tasks with a verifier, not
                scraped chat.
              </li>
              <li>
                <span className="text-white">Teams with traces.</span> List a task, set the price,
                keep 80%.
              </li>
              <li>
                <span className="text-white">Researchers.</span> Investigate why a swarm stalled.
                Village is research-only and never listed.
              </li>
            </ul>
          </div>
          <div className="rounded-xl border border-zinc-800 p-6">
            <p className="text-lg leading-snug text-zinc-200">
              Raw logs are worth little. The only way to make them worth anything is turning them
              into tasks agents can learn from.
            </p>
            <p className="mt-4 text-sm text-zinc-500">
              Not Alibi (prior work: past-claims audit). Not a JSONL marketplace.
            </p>
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-800 py-20">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-2xl font-medium tracking-tight">Demo catalog</h2>
          <p className="mt-2 text-sm text-zinc-500">
            Synthetic tasks. Not for training. Take is 20%.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {listings.map((row) => (
              <article key={row.id} className="rounded-xl border border-zinc-800 p-5">
                <h3 className="font-medium">{row.title}</h3>
                <p className="mt-2 text-sm text-zinc-500">{row.notes}</p>
                <p className="mt-4 font-mono text-sm text-zinc-300">
                  ${row.list_price_usd.toFixed(0)} list · ${row.seller_payout_usd.toFixed(0)} seller
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-zinc-800 py-8">
        <p className="mx-auto max-w-6xl px-5 text-sm text-zinc-600">
          Zetaris is the query engine. NVIDIA Nemotron explains why after SQL. AI Village is
          cited for research and is never sold.
        </p>
      </footer>
    </main>
  );
}
