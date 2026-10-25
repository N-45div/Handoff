# hmem

Handoff's case memory. It runs the [Meterless H-MEM](https://github.com/Meterless/Meterless/tree/main/engines/hmem) reference engine behind `http://127.0.0.1:8790`, so the Python app can store confirmed verdicts, recall earlier ones, and read each memory's trust-ledger history.

```bash
npm install
npm run setup   # vendors the H-MEM reference into vendor/hmem (gitignored)
npm run serve
```

| Route | What it does |
|---|---|
| `GET /health` | engine source and memory count |
| `POST /remember` | store a verdict with its provenance (`content`, `source`, `tags`, `refs`, `label`) |
| `POST /query` | ranked recall (`q`, `topN`, `threshold`) |
| `POST /feedback` | `helpful`, `not_helpful` or `wrong`; changes confidence through the ledger |
| `GET /audit/<id>` | the memory's append-only ledger history |

State lives in `../.handoff/hmem`. `src/engine.ts` comes from Meterless's agentathon starter (Apache-2.0).
