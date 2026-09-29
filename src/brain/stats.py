"""Vault stats, token-economy metrics, usage + write activity logs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from brain.cards import list_card_meta


def estimate_tokens(text_or_len: str | int) -> int:
    """Rough LLM token estimate: ~4 chars per token."""
    n = text_or_len if isinstance(text_or_len, int) else len(text_or_len)
    return max(1, n // 4)


def usage_path(root: Path) -> Path:
    return root / "index" / "usage.jsonl"


def activity_path(root: Path) -> Path:
    return root / "index" / "activity.jsonl"


def log_usage(root: Path, kind: str, served_tokens: int, naive_tokens: int) -> None:
    """Append one token-economy event (search/get). Never raises."""
    try:
        path = usage_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            "served": int(served_tokens),
            "naive": int(naive_tokens),
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def log_activity(root: Path, kind: str, *, slug: str = "", detail: str = "") -> None:
    """Append write/link/remember/active event. Updates dashboard on every write."""
    try:
        path = activity_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            "slug": slug or "",
            "detail": (detail or "")[:120],
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def usage_series(root: Path, days: int = 14) -> list[dict[str, Any]]:
    """Per-day token aggregates for the last N days (UTC; oldest first)."""
    buckets: dict[str, dict[str, int]] = {}
    today = _utc_today()
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        buckets[d] = {"served": 0, "naive": 0, "queries": 0}
    path = usage_path(root)
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                ev = json.loads(line)
                day = str(ev.get("ts", ""))[:10]
                if day in buckets:
                    buckets[day]["served"] += int(ev.get("served", 0))
                    buckets[day]["naive"] += int(ev.get("naive", 0))
                    buckets[day]["queries"] += 1
            except Exception:
                continue
    return [
        {"day": d, **v, "saved": max(0, v["naive"] - v["served"])}
        for d, v in buckets.items()
    ]


def activity_series(root: Path, days: int = 14) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Per-day write activity + recent raw events."""
    buckets: dict[str, dict[str, int]] = {}
    today = _utc_today()
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        buckets[d] = {"writes": 0, "links": 0, "remembers": 0, "other": 0}
    path = activity_path(root)
    recent: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                ev = json.loads(line)
                day = str(ev.get("ts", ""))[:10]
                kind = str(ev.get("kind") or "other")
                if day in buckets:
                    if kind in ("write", "add"):
                        buckets[day]["writes"] += 1
                    elif kind == "link":
                        buckets[day]["links"] += 1
                    elif kind == "remember":
                        buckets[day]["remembers"] += 1
                    else:
                        buckets[day]["other"] += 1
                recent.append(ev)
            except Exception:
                continue
    series = [
        {
            "day": d,
            **v,
            "total": v["writes"] + v["links"] + v["remembers"] + v["other"],
        }
        for d, v in buckets.items()
    ]
    return series, recent[-12:]


def _dir_bytes(path: Path, pattern: str) -> int:
    if not path.is_dir():
        return 0
    total = 0
    for p in path.glob(pattern):
        try:
            total += p.stat().st_size
        except OSError:
            continue
    return total


def cheap_full_tokens(root: Path) -> int:
    """File-size token budget without list_card_meta / decrypt (hot path)."""
    return (
        estimate_tokens(_dir_bytes(root / "cards", "*.md"))
        + estimate_tokens(_dir_bytes(root / "secure", "*.md.enc"))
        + estimate_tokens(_dir_bytes(root / "core", "*.md"))
    )


def _is_fresh(updated: str, *, hours: int = 24) -> bool:
    if not updated:
        return False
    try:
        # date-only → treat as start of that UTC day
        if len(updated) <= 10:
            d = date.fromisoformat(updated[:10])
            dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return (_utc_now() - dt) <= timedelta(hours=hours)
    except ValueError:
        return False


def vault_stats(root: Path) -> dict[str, Any]:
    meta = list_card_meta(root)
    ids = {c["id"] for c in meta}
    linked_to: set[str] = set()
    broken_links = 0
    tags: Counter[str] = Counter()
    stale_cards = 0
    fresh_24h = 0
    today = _utc_today()

    for c in meta:
        for t in c.get("tags") or []:
            tags[t] += 1
        for link in c.get("links") or []:
            if link in ids:
                linked_to.add(link)
            else:
                broken_links += 1
        upd = str(c.get("updated") or "")
        if _is_fresh(upd, hours=24):
            fresh_24h += 1
        try:
            if upd and (today - date.fromisoformat(upd[:10])).days > 90:
                stale_cards += 1
        except ValueError:
            pass

    orphans = sum(
        1
        for c in meta
        if not (c.get("links") or [])
        and c["id"] not in linked_to
        and not (
            c.get("secure")
            and str(c.get("tldr") or "").startswith("[secure")
        )
    )

    cards_dir = root / "cards"
    secure_dir = root / "secure"
    plaintext_chars = _dir_bytes(cards_dir, "*.md")
    secure_bytes = _dir_bytes(secure_dir, "*.md.enc")
    core_bytes = _dir_bytes(root / "core", "*.md")
    catalog = root / "index" / "catalog.md"
    catalog_chars = catalog.stat().st_size if catalog.is_file() else 0

    tldr_tokens = [estimate_tokens(c.get("tldr") or "") for c in meta] or [1]
    avg_tldr = sum(tldr_tokens) // len(tldr_tokens)

    plaintext_tokens = estimate_tokens(plaintext_chars)
    secure_tokens = estimate_tokens(secure_bytes)
    core_tokens = estimate_tokens(core_bytes)
    full_tokens = plaintext_tokens + secure_tokens + core_tokens
    catalog_tokens = estimate_tokens(catalog_chars)
    query_tokens = catalog_tokens + 3 * avg_tldr
    savings_pct = 0
    if full_tokens > 0:
        savings_pct = round(100 * (1 - query_tokens / max(full_tokens, 1)))
        savings_pct = max(0, min(99, savings_pct))

    inbox_dir = root / "inbox"
    inbox = (
        len([p for p in inbox_dir.iterdir() if p.is_file() and not p.name.startswith(".")])
        if inbox_dir.is_dir()
        else 0
    )

    memory_tail: list[str] = []
    mem = root / "core" / "memory.md"
    if mem.is_file():
        lines = [
            ln for ln in mem.read_text(encoding="utf-8", errors="ignore").splitlines()
            if ln.startswith("- ")
        ]
        memory_tail = lines[-5:]

    usage = usage_series(root, days=14)
    usage_queries = sum(u["queries"] for u in usage)
    usage_saved = sum(u["saved"] for u in usage)
    activity, recent_activity = activity_series(root, days=14)
    writes_today = activity[-1]["total"] if activity else 0
    writes_14d = sum(a["total"] for a in activity)

    return {
        "cards": len(meta),
        "secure": sum(1 for c in meta if c.get("secure")),
        "inbox": inbox,
        "broken_links": broken_links,
        "orphans": orphans,
        "stale_cards": stale_cards,
        "fresh_24h": fresh_24h,
        "plaintext_tokens": plaintext_tokens,
        "secure_tokens": secure_tokens,
        "core_tokens": core_tokens,
        "full_tokens": full_tokens,
        "catalog_tokens": catalog_tokens,
        "avg_tldr_tokens": avg_tldr,
        "query_tokens": query_tokens,
        "savings_pct": savings_pct,
        "top_tags": tags.most_common(10),
        "memory_tail": memory_tail,
        "usage": usage,
        "usage_queries_14d": usage_queries,
        "usage_saved_14d": usage_saved,
        "usage_tz": "UTC",
        "activity": activity,
        "writes_today": writes_today,
        "writes_14d": writes_14d,
        "recent_activity": recent_activity,
    }


def served_tokens_for_results(results: list[dict[str, Any]]) -> int:
    total = 0
    for r in results:
        total += estimate_tokens(str(r.get("title") or "")) + estimate_tokens(
            str(r.get("tldr") or "")
        )
    return total
