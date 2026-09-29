# HANDOFF — стан проєкту для AI-агента

> Відкрий цю папку в Cursor/Codex/Claude і скажи «прочитай docs/HANDOFF.md
> і продовжимо» — агент матиме весь контекст без опису з нуля.

## Що це

Knowledge Brain: міжпроєктна картотека знань (Markdown vault на Google Drive)
+ CLI `brain` + нативний macOS застосунок (pywebview) з нейронним графом.
Мета: довгострокова памʼять для людини і AI-агентів з мінімальною витратою
токенів. Обґрунтування: `docs/WHY.md`, токен-економіка: `docs/TOKENS.md`.

## Стан на 2026-08-04 (v0.1.1)

Зроблено і працює:

- CLI: init / set-root / search / get / add / link / unlock / lock / passwd /
  doctor / reindex / catalog / remember / recipe / import / stats / agents install / ui / desktop.
- Шифрування secure-карток: Argon2id + AES-256-GCM (`src/brain/crypto.py`).
- UI (`ui/` + `src/brain/ui_server.py`): неоновий нейронний граф, пошук,
  створення/unlock мастер-пароля, Settings (шлях, ліміти, порт, TTL, імпорт .md,
  підключення агентів, reindex, doctor), Dashboard (токени + здоровʼя + теги),
  Feedback-опросник з артефактом у `feedback/`.
- Адаптери моделей: Cursor Skill, `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`
  (`src/brain/agents_install.py`, сніпети в `agents/snippets/`).
- macOS: self-contained `.pkg` з **bundled CPython 3.12** + vendored wheels
  (не потрібні Homebrew / Xcode CLT / системний Python).
- Тести: `tests/test_brain.py` (15), запускати `python3 -m pytest tests/ -q`.

## Куди продовжувати (backlog)

Див. `docs/BACKLOG.md`. Найгарячіше:

1. Мобільний доступ (Android) — хоча б read-only перегляд vault.
2. Merge-конфлікти Google Drive (зараз last-write-wins).
3. Авто-запуск recipes за розкладом (launchd).
4. Дашборд: «гарячі» картки, вартість токенів у грошах.
5. Фідбек Ігоря: розпарсити `feedback/feedback-*.md` → задачі.

## Ключові рішення (щоб не переривати)

- БД нема навмисно: індекс = `index/search.json` + `index/catalog.md`,
  перебудовується з .md (`docs/DECISIONS.md`).
- Агентський протокол: каталог → ≤3 картки TL;DR; secure не читати
  (`docs/PROTOCOL.md`).
- Секрети: мастер-пароль ніде не зберігається; `.machine_key` — локальний.

## Збірка релізу

```bash
./scripts/macos/build-installer.sh   # → dist/…/BrainTools-<ver>-arm64.pkg
```
