# Automations ideas → Brain (local)

Cursor Automations = cloud agents on schedule/events (GitHub, Slack, cron, webhooks) with instructions, tools, memory, and self-check.

We **do not duplicate** Cursor’s cloud product. We borrow patterns that help a knowledge vault:

| Automations | In Brain |
|-------------|---------|
| Trigger + instructions | `automations/*.md` recipes |
| Scoped context (no/single/multi repo) | recipe `scope:` + `core/projects.md` |
| Memory across runs | `core/memory.md` (short learnings) |
| Verify output | `brain doctor` / recipe `verify: doctor` |
| Plain-language setup | human recipes + `brain recipe run` |
| Always-on maintenance | recipe `nightly-hygiene` (reindex + doctor + inbox hint) |

## Optional: wire to Cursor Automations later

A Cursor Automation can cron/Slack-trigger with:

> Run in brain-tools: `brain recipe run nightly-hygiene`. Follow vault `PROTOCOL`. Do not read secure/.

That remains optional — Brain works fully offline without it.
