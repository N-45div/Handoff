# Handoff

Post-mortem investigator for agent swarms. Chat is the contract. Computer-use logs are whether anyone actually did the work.

**Track:** Open Agent Hackathon 2026 — Track 02, The Agent That Can Explain Why.

Ask: *why did the swarm stall on goal X?*

- Who promised what to whom
- Who kept it, dropped it, duplicated it, or never picked it up
- Whether a promise written into an agent's memory was kept more often than one said only in chat

## This is not Alibi

Alibi (prior work, pre-22 Oct 2026) checks **claims about the past** against the claiming agent's own log. Handoff is new work: it checks **promises between agents** against later computer-use turns. Do not copy Alibi into this tree. Dataset-loader idea only is carried over (stream gated tables, never commit them).

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
