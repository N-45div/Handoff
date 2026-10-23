# Handoff

An agent that turns a raw swarm or coding-agent **transcript into a task** a lab can train on: instruction, OpenEnv episode, promise verifier.

Chat is the contract. Promises are kept / dropped / unclaimed / duplicate. That grade **is** the reward. Raw JSONL is not the product. Village dumps are research-only and never listed.

```bash
pip install -r requirements.txt
python -m handoff.app
```

API (Zetaris):

```bash
python -m handoff.app
```

Product site (Vite):

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — landing. Desk: http://127.0.0.1:5173/desk. Vite proxies `/api` to the FastAPI process on :8787.

- **Load ops swarm / coding log** — Nightshift or a Cursor-shaped PR transcript (extra keys ignored)
- **Investigate** — why the swarm stalled (Track 02)
- **Build task** — instruction + episode + verifier; seller list price, Handoff takes 20%. Secrets (`hf_`, `sk-`, `.env`) are refused
- **Village research** — three post-Alibi weeks in Zetaris. Not a task. Not for sale.

Verdicts: kept, dropped, unclaimed, duplicate.

**Track:** Open Agent Hackathon 2026 — Track 02, The Agent That Can Explain Why.

Week timeline, competitor notes, and the catalog / OpenEnv POC: [ROADMAP.md](ROADMAP.md).

**Catalog:** listed **tasks**, not dumps. Seller sets list price; Handoff takes 20%. Village is never listed.

```bash
python -m handoff.task
python -m handoff.mcp_server
```

Cursor MCP: this repo’s `.cursor/mcp.json`, or copy [mcp.example.json](mcp.example.json). Primary tool: `handoff_build_task`.

Ask: *why did the swarm stall on goal X?*

- Who promised what to whom
- Who kept it, dropped it, duplicated it, or never picked it up
- Whether a promise written into an agent's memory was kept more often than one said only in chat

## This is not Alibi

Alibi (prior work, pre-22 Oct 2026) checks **claims about the past** against the claiming agent's own log. Handoff is new work: it checks **promises between agents** against later computer-use turns. Do not copy Alibi into this tree. Dataset-loader idea only is carried over (stream gated tables, never commit them).

## Zetaris (Cursor + UI)

Use Zetaris’s own Cursor guide, not a homemade client: [Connecting Cursor to Zetaris](https://zetaris.github.io/getting-started/docs/connections/cursor-connection.html). The recipes live in a clone at `C:\Users\DivijN\zetaris-getting-started` (`AGENTS.md` + `scripts/preflight.py`). Credentials go in **`.env.local` only**, never in a prompt.

**UI (beginner route, no extra tools):** after the local Docker stack is up, open [http://localhost:3000](http://localhost:3000), sign in, SQL Editor, run `SELECT 1 AS one;` then `SHOW LIGHTNING DATABASES`. Create the REST key in the GUI: Management → API Tokens. Org ID is Management → Organisation.

**Docker:** Docker Desktop is already running. Images are not public. Download `zetaris-platform.zip` from Zetaris Cloud → [Start Free / Run locally](https://www.zetaris.com/cloud), then:

```bash
docker login zetarishackathon.azurecr.io
# unzip into a folder that is not Downloads
docker compose pull
docker compose up -d
```

Read-only preflight (REST) from the getting-started clone, after `.env.local` has a key:

```bash
python C:\Users\DivijN\zetaris-getting-started\scripts\preflight.py
```

Local stack is running. SQL Workspace `SELECT 1 AS one` returned `1`.

```bash
python -m handoff.slice
python -m handoff.register
python -m handoff.investigate
python -m handoff.report
python -m handoff.cu_slice
python -m handoff.register
python -m handoff.confirm
```

Chat lives in `HANDOFF.promises`. Computer-use **sessions** (~43 MB, three weeks) live in `HANDOFF.cu_sessions`. Do not download `computer_use_turns.jsonl.gz` (2.8 GB) until you need screen-level proof.

## Data

Uses the gated [AI Village dataset](https://huggingface.co/datasets/aidigestorg/ai-village) for research/analysis only. Do not train on it. Cite AI Digest / AI Village. Keep dumps in `./data` (gitignored).

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # add HF_TOKEN
python -m handoff.fetch catalog
python -m handoff.rank
```

Judges need their own Hugging Face access to rerun the Village path.

## License

Code in this repository is yours. Village rows are not redistributed here.
