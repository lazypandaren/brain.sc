# Why Brain exists

## Problem

1. **Knowledge is scattered.** Decisions, how-tos, configs, and contacts live in AI chats, Slack threads, random notes, and ticket comments — then vanish.
2. **Agents are expensive when naive.** Dumping a whole folder into context burns tokens and still misses the right fact.
3. **Secrets and ops notes collide.** Mixing passwords with public runbooks is unsafe; keeping everything locked kills search.

## Solution

A **personal Markdown vault** plus a small CLI/UI:

- Cards with TL;DR-first structure for cheap reads
- Deterministic search / catalog for agents (no embeddings required)
- Optional `secure/` encryption for sensitive cards only
- Localhost neural UI + macOS desktop tray app
- Thin adapters so Cursor / Codex / Claude follow one protocol

## Benefits

| Benefit | What you get |
|---------|----------------|
| Token economy | Search → ≤3 TL;DR cards instead of vault dump |
| Durability | Survives chat resets and tool switches |
| Portability | Sync via Google Drive; plain `.md` forever |
| Safety | Secrets opt-in; UI on `127.0.0.1` only |
| Agent-ready | `brain agents install` wires protocol snippets |

## Non-goals (for now)

- Cloud-hosted UI
- Full-vault encryption
- Mobile-first app (later backlog)
- Embeddings-first search (optional later)
