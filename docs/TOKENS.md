# Token economy — why the Markdown catalog wins

## Short answer

Yes: a catalog of short MD cards + a router is the best agent format when the goal is **minimum tokens**.

Not “read all Markdown”, but **index → 1–3 cards**.

## Comparison

| Approach | Tokens per query | Downsides |
|----------|------------------|-----------|
| Full chat / session dump | Very high | Noise, stale facts |
| Vector DB / embeddings into the prompt | Medium–high | Infra; weaker offline / Drive story |
| **MD catalog (`index/catalog.md` + search)** | Low | Needs TL;DR discipline |
| One giant wiki | High | Agents pull extras |

## Mandatory read path

```
BRAIN.md (or brain status)
  → index/catalog.md  OR  brain search <q>
    → ≤3 × brain get <slug>   # TL;DR only
      → Details / --full only when needed
```

Never bulk-read `cards/`, `_raw/`, or `secure/*.enc`.
