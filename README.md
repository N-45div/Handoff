# Handoff

Post-mortem desk for **any** agent swarm. Chat is the contract. Computer-use logs are whether anyone actually did the work.

```bash
pip install -r requirements.txt
python -m handoff.app
```

Open http://127.0.0.1:8787

- **Load sample swarm** — synthetic Nightshift transcript, no Village dump required
- **Load Village demo** — three post-Alibi weeks already in Zetaris (`HANDOFF.promises`)
- **Investigate** — paste or attach JSONL/CSV (`speaker`, `content`, optional `created_at` / `goal`). Handoff registers a FILESTORE table, then scores promises over Lightning REST

Verdicts: kept, dropped, unclaimed, duplicate.

**Track:** Open Agent Hackathon 2026 — Track 02, The Agent That Can Explain Why.

Week timeline, competitor notes, and the catalog / OpenEnv POC: [ROADMAP.md](ROADMAP.md).

**Catalog (demo):** seller sets a list price; Handoff takes 20%. Nightshift only. Village is never listed.

```bash
python -m handoff.env_export
python -m handoff.mcp_server
```

Cursor MCP: copy [mcp.example.json](mcp.example.json) into your MCP config (`cwd` must be this repo).

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
