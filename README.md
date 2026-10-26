# Handoff

**Handoff finds the promises AI agents make to each other and checks each one against what the agent actually did.**

Agents in a team say "I'll send it", "on it", "let me fix that". Read from chat alone, nearly all of those look kept, because the agent keeps talking. Handoff reads the agent's own computer-use log instead. Chat, executed actions and memory notes are separate sources, and Zetaris joins them in one SQL layer. NVIDIA Nemotron names each promise and judges it against the actions. Every verdict goes into Meterless H-MEM with its sources, so a reviewer can confirm it or mark it wrong.

## What it found in the AI Village

Three weeks of the [AI Village](https://theaidigest.org/village): "Finetune your leader!", "Organise an event!" and "Compete to be the best AI Assistant!" (May 26 to July 6, 2026). 22 agents from several labs (21 of them made promises), 9,614 agent chat messages, 213,113 computer actions and 15,372 memory notes.

| | Promises | Share |
|---|---:|---:|
| Kept: the work shows in the agent's own log within 24 hours | 345 | 54% |
| Partial: started, not finished | 120 | 19% |
| Not done: no action toward it in the next 24 hours | 143 | 22% |
| Unclear: the proof would only be on screen | 31 | 5% |
| **Total** | **639** | |

- Read from chat alone (did the agent say anything afterwards?), 95% of the 1,933 promise-like lines look kept.
- Kept rates by agent (20 or more promises each) range from 68% for Claude Opus 4.8 to 38% for GPT-5.1.
- The common failure, in the cited explanation Nemotron 3 Ultra writes from the verdict table: agents switch to unrelated work instead of finishing the pledged step, or start a script or checklist and never verify that it finished.
- How the 639 were found: 1,582 first-person lines ("I'll", "let me", "on it") became 895 concrete commitments. Then 256 were removed because Nemotron judged that the task belonged to another agent.
- Every "not done" verdict was judged a second time with up to 60 actions instead of 14. That changed 74 of 217. An earlier 60-promise sample showed about 1 in 4 "not done" verdicts were evidence a narrow first pass had not seen, which is why the second look exists.

## How it works

1. **One query layer.** The gated Village tables stream once into Parquet files in Zetaris's file store. Zetaris Lightning SQL reads them as `HANDOFF.promises` (chat), `HANDOFF.cu_turns` (computer actions), `HANDOFF.memories` (memory notes) and `HANDOFF.verdicts`. Every read in the app goes through Zetaris.
2. **Find promises.** A first-person pattern picks candidate lines. Nemotron 3.5 Lightning (thinking off) names the concrete task. Nemotron 3 Ultra checks that the speaker owns the task, not another agent, before any judging.
3. **Judge against actions.** For each promise, Handoff takes the agent's executed actions and later chat for the next 24 hours, ranks them against the task, and asks Nemotron 3 Ultra for kept, partial, not done or unclear, citing action ids. Only executed actions and tool output count. The agent's narration is shown as context and never proves anything. Every "not done" gets a second, wider look.
4. **Remember and review.** Each verdict goes into the [Meterless H-MEM](https://github.com/Meterless/Meterless/tree/main/engines/hmem) reference engine (`hmem/`), with the promise id and cited action ids as provenance. Confirm or Mark wrong on the desk changes the verdict's confidence through H-MEM's trust ledger, and the ledger keeps the history. The engine is the official H-MEM reference (`engines/hmem/reference`, Apache-2.0, unmodified, pulled by `npm run setup`); `npm test` in `hmem/` runs its own suite (10 of 10 pass), and `python -m handoff.hmem` checks the live engine: health, a recall, and one verdict's ledger.
5. **Explain.** Nemotron 3 Ultra writes one paragraph about why work slipped, using only the verdict table and citing promise ids.

Every model call goes through `handoff/llm.py` to the **Meterless Runtime** (Nightshift), which routes it to NVIDIA's hosted Nemotron and returns a signed compute receipt; each verdict keeps its receipt id. NVIDIA's trial endpoints rate-limit hard, so when Meterless keeps failing, the same Nemotron model on Nebius answers instead and the verdict is marked `nebius-fallback`. In the published run, 245 of the 639 final verdicts carry a Meterless receipt; the other 394 came from the same Nemotron 3 Ultra on the fallback, mostly while NVIDIA was rate-limiting or Nightshift was restarting. A Meterless-only re-run of those 394 was stopped when NVIDIA's trial endpoint answered nearly every call with 429. Nemotron 3 Super is not enabled on NVIDIA's trial account, so judging uses Ultra.

## The desk

`http://localhost:5173/desk`. **Village** opens the investigation: counts, who left work undone, the cited Nemotron paragraph, and every verdict. **Evidence** opens two columns: what the agent did (`HANDOFF.cu_turns`) and what it wrote in its memory (`HANDOFF.memories`, context only). **Agent trace** loads a small Claude Code-shaped sample, and **Build task** turns it, or any trace you paste or attach, into a training task (next section). A transcript with no actions is graded from chat only, and the task says so.

## Traces into training tasks

Labs train agents on tasks, not log dumps, and a task is only as good as its reward. Handoff turns an agent trace you own into a task whose reward comes from what the agent ran.

1. **Split talk from actions.** In a Claude Code session log, the agent's text and the messages it sends to other agents are talk; every tool call, with its result, is an action. Anything that looks like a secret is redacted on the way in (pattern matching, not a guarantee), and the finished task is checked again.
2. **Store and read through Zetaris.** Talk and actions become two Parquet FILESTORE tables and are read back through Lightning SQL. If Zetaris is not running, the trace is graded from memory and the task records that.
3. **Grade.** Nemotron 3.5 Lightning lists the commitments in each line (one line can hold two), and Nemotron 3 Ultra judges each against the actions the same agent ran afterwards, through Meterless, citing action ids. A promise with nothing after it in the trace is unclear, not not-done.
4. **Export** a task (`version 0.2`, reward spec `handoff-reward@0.2`):
   - `prompt`: the instruction for the agent being trained.
   - `verifier.rubric`: each promise with its task, verdict, reward, the cited actions, the judge's reason and the receipt of the call that judged it.
   - Rewards: kept +1, partial +0.25, not done −1; unclear is left unscored, so there is no reward without proof either way.
   - `episode`: talk and actions in time order, with each promise's reward on the step where it was made.

```bash
python -m handoff.tracecheck path/to/session.jsonl --name "my swarm"   # grades, prints the verdicts
```

The desk's **Build task**, the `/api/task` endpoint and the `handoff_build_task` MCP tool all build the same task. On the sample trace, the agent promised a test file, a posted pytest log and a RUN.md update; the task grades the first two kept and the third not done, for a score of 0.333. Village data is never listed for sale.

## Run it

You need Python 3.12, Node 20+, Docker Desktop, a local Zetaris install ([getting started](https://github.com/zetaris/getting-started)), Hugging Face access to the gated [AI Village dataset](https://huggingface.co/datasets/aidigestorg/ai-village), and [Nightshift](https://meterless.ai/) with an NVIDIA key (build.nvidia.com) added under Setup, Providers. A Nebius Token Factory key is optional, for the fallback.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env.local        # HF_TOKEN, ZETARIS_*, METERLESS_TOKEN, optional NEBIUS_API_KEY

# 1. Slice the three weeks and register them in Zetaris
python -m handoff.fetch catalog
python -m handoff.fetch chat
python -m handoff.slice
python -m handoff.cu_slice
python -m handoff.turns             # streams 2.8 GB once, keeps 213k rows
python -m handoff.memories          # streams 2.5 GB once, keeps 15k rows
python -m handoff.register

# 2. Judge
python -m handoff.evidence          # extract, owner check, judge (resumable)
python -m handoff.second_look --all
python -m handoff.evidence --summarize

# 3. Memory (separate terminal)
cd hmem && npm install && npm run setup && npm run serve

# 4. Publish, remember, explain, serve
python -m handoff.village publish
python -m handoff.village remember
python -m handoff.village why
python -m handoff.app
cd frontend && npm install && npm run dev

# Tests
python -m unittest discover -s tests
cd hmem && npm test
```

Zetaris runs locally in Docker (UI on :3000, REST on :8888). Credentials stay in `.env.local`.

## MCP

`.cursor/mcp.json` connects the Handoff MCP server to Cursor (`mcp.example.json` for other clients). The tools are:

| Tool | What it does |
|---|---|
| `handoff_demo` | The Village investigation |
| `handoff_cited_actions` | One verdict and the actions it cites |
| `handoff_investigate` | Score a pasted transcript |
| `handoff_open_promises` | Open promises from the last investigation |
| `handoff_improve` | What to change next session |
| `handoff_build_task` | Turn a trace you own into a training task, graded on the agent's actions when the trace has them |

Village data is never exported as a task.

## Limits

- The judge sees the 14 actions that best match the task, or 60 in the second look. Proof elsewhere in the log can be missed.
- The window is 24 hours, so work done later counts as not done.
- Screenshots are not read yet. "Unclear" often means the proof was only on screen.
- The owner check also removes some real promises. Its 256 removals have not been reviewed by hand.
- The pattern only finds first-person phrasing. Promises worded another way are not counted.
- An LLM judge can be wrong. That is why the desk records reviewer corrections in H-MEM instead of hiding them.
- Trace grading reads Claude Code session logs and plain JSONL (speaker/content lines, plus lines with an `action`). Other agent log formats need an adapter.
- Whether writing a promise into memory helps keep it was tested and was inconclusive. The notes mention nearly every task, so a keyword match cannot tell a to-do from a passing mention. Handoff does not claim that result.

## Data

The [AI Village dataset](https://huggingface.co/datasets/aidigestorg/ai-village) is from AI Digest and is gated. It is used here for research only: no training on it, cite AI Digest / AI Village. Slices stay in `./data`, which is gitignored. Rerunning the Village path needs your own Hugging Face access.

## Prior work

Alibi, an earlier separate project, checked agents' claims about the past against their logs. Handoff checks promises about the future and is new code; only the idea of streaming the gated tables was carried over.

## License

MIT. `hmem/src/engine.ts` comes from Meterless's agentathon starter (Apache-2.0).
