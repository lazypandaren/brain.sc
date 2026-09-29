# Automations ideas → Brain (local)

Cursor Automations = cloud agents on schedule/events (GitHub, Slack, cron, webhooks) with instructions, tools, memory, and self-check.

Ми **не дублюємо** хмарний продукт Cursor. Беремо патерни, корисні для knowledge vault:

| Automations | У Brain |
|-------------|---------|
| Trigger + instructions | `automations/*.md` recipes |
| Scoped context (no/single/multi repo) | recipe `scope:` + `core/projects.md` |
| Memory across runs | `core/memory.md` (короткі learnings) |
| Verify output | `brain doctor` / recipe `verify: doctor` |
| Plain-language setup | рецепти людською мовою + `brain recipe run` |
| Always-on maintenance | recipe `nightly-hygiene` (reindex + doctor + inbox hint) |

## Optional: wire to Cursor Automations later

У Cursor Automations можна зробити cron/Slack trigger з інструкцією:

> Run in brain-tools: `brain recipe run nightly-hygiene`. Follow vault `PROTOCOL`. Do not read secure/.

Vault path must be available to that cloud agent (or skip until Drive path is set).

## Recipe format

```yaml
---
id: nightly-hygiene
title: Nightly vault hygiene
trigger: schedule|manual|after-session
scope: vault-only
max_cards: 0
verify: doctor
---
# Instructions
1. brain reindex
2. brain doctor
3. If inbox/ non-empty — list filenames only (do not open bodies).
4. Append one line to core/memory.md if something failed.
```
