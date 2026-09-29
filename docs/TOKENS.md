# Token economy — why Markdown catalog wins

## Short answer

**Так:** каталог коротких MD + роутер — найкращий формат для агента, якщо мета = **мінімум токенів**.

Не «прочитай усі MD», а **індекс → 1–3 картки**.

## Порівняння

| Підхід | Токени на запит | Мінуси |
|--------|-----------------|--------|
| Весь чат / session dump | Дуже високо | Шум, застаріле |
| Vector DB / embeddings у промпт | Середньо–високо | Потрібна інфра, гірше для офлайн/Drive |
| **Каталог MD (`index/catalog.md` + search)** | Низько | Треба дисципліна TL;DR |
| Одна гігантська wiki | Високо | Агент тягне зайве |

## Обов’язковий шлях читання

```
BRAIN.md (або brain status)
  → index/catalog.md  АБО  brain search <q>
    → ≤3 × brain get <slug>   # лише TL;DR
      → Details / --full лише якщо треба
```

Жорсткі ліміти: `max_cards_per_query` (default 3), ніколи `_raw/`, ніколи bulk `cards/`.

## Що запозичили з Cursor Automations (без хмари)

Див. [`AUTOMATIONS.md`](AUTOMATIONS.md): рецепти (trigger + instructions), memory прогонів, verify (`doctor`), scoped context.
