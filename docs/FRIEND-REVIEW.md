# Brain — бриф для рев’ю (v0.1.0)

**Статус збірки:** `pip install -e .` ок, тести зелені, CLI `brain` працює.  
**macOS installer:** один файл `dist/macos/BrainTools-0.1.0-arm64.pkg` (`./scripts/macos/build-installer.sh`).  
**Код:** `~/Documents/projects/brain-tools`  
**Мета рев’ю:** порадити, що покращити далі (UX, безпека, архітектура, мобільний).

---

## Що це одним реченням

Особиста **міжпроєктна картотека знань** для людини + AI-агентів: Markdown на Google Drive, швидкий пошук, UI «мозок» зі зв’язками, шифрування чутливого, протокол щоб моделі не спалювали токени.

## Для кого

- Ти працюєш у кількох репо / з різними AI (Cursor, Codex, Claude).
- Хочеш одну пам’ять на Mac/Linux (Android UI — пізніше), синк через Drive.
- Агенту треба **знаходити** факти, а не читати весь архів.

## Функціонал (що вже є)

### Vault (дані)
- Папка-сховище: картки `.md`, індекси, inbox, secure, automations.
- Шлях задається з **CLI** (`brain init` / `set-root`) або **UI Settings**.
- Конфіг машини: `~/.config/brain/config.yaml` (не обов’язково в Drive).

### Картки знань
- Атомарні нотатки з YAML + **TL;DR** + Details.
- Зв’язки `links` (як синапси), теги, проєкти.
- Lean-каталог `index/catalog.md` + `search.json` для швидкого пошуку.

### CLI `brain`
`init`, `set-root`, `path`, `status`, `doctor`, `search`, `get`, `add`, `link`, `active`, `reindex`, `unlock`/`lock`/`passwd`, `ui`, `catalog`, `remember`, `recipe`, `agents install`.

### UI
- Локальний веб (`127.0.0.1`): force-directed граф нейронів, пошук, панель картки, unlock, Settings (шлях).

### Безпека
- Лише `secure/*.md.enc`: Argon2id + AES-256-GCM.
- Сесія unlock з TTL; fail-closed без пароля.
- Агент **не** просить мастер-пароль і не читає `.enc`.

### Мультимодельність
- Один протокол + адаптери: `AGENTS.md` (Codex), `CLAUDE.md` (Claude), Cursor Skill.
- `brain agents install` → сниппети в `~/.codex` / `~/.claude`.

### «Automations»-патерни (локально)
- Рецепти в `automations/` (`nightly-hygiene`, `after-session`, `token-safe-answer`).
- Коротка пам’ять прогонів: `core/memory.md` + `brain remember`.
- Verify: `brain doctor`.

## Переваги (чому не просто «папка з md»)

1. **Економія токенів:** роутер (catalog/search) → ≤3 TL;DR, заборона bulk-scan.
2. **Один vault на всі проєкти**, синкається Drive’ом; код окремо від даних.
3. **Працює з різними моделями** однаковими правилами.
4. **Візуальний граф** зв’язків — швидше бачити «сусідні» знання.
5. **Шифрування опційне** (не ламає пошук звичайних карток).
6. **Doctor + тести** — можна ловити розсинхрон індексу / биті лінки.
7. **Рецепти** — повторювані ритуали без залежності від хмарних Automations.

## Обмеження v0.1 (чесно)

- Немає нативного Android UI (поки Drive + md-редактор).
- Немає embeddings / semantic search.
- UI тільки localhost, без мультикористувацького сервера.
- Пошук lexical (title/tags/tldr), не «розуміння сенсу».
- Сесія ключа — файл у `~/.config/brain` (не OS keychain).
- Cursor Automations у хмарі не підключені «з коробки» — лише локальні recipes.

## Як другу швидко подивитись

```bash
cd ~/Documents/projects/brain-tools
python3 -m pip install -e .
brain init /tmp/brain-demo --password 'demo-pass'
brain search elseveir
brain catalog
brain recipe list
brain ui   # http://127.0.0.1:8765/
brain doctor
PYTHONPATH=src python3 -m pytest -q
```

## Питання до рев’юера (будь ласка, відповідай вільно)

1. Чи зрозумілий value prop за 30 секунд? Що плутає?
2. Чи правильний split: plaintext cards vs `secure/`?
3. Чого не вистачає для щоденного використання (inbox triage, OCR, voice, Telegram…)?
4. UI графа: wow чи зайве? Що змінити в UX?
5. Безпека: Argon2/GCM/session — що підкрутити першим?
6. Мультимодель (Codex/Claude/Cursor): чи достатньо тонких адаптерів?
7. Що зробити в v0.2 обов’язково vs nice-to-have?

---

Авторський контекст: продукт заточений під AI-агента як споживача знань + людину як редактора. Критика «зроби як Notion» ок, якщо поясниш, як не вбити token-economy.
