"""Tests for Brain 0.4: wiki-links, backlinks, daily notes, orphan flag."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from brain.cards import Card, add_link, parse_card, read_card, write_card
from brain.daily import backlinks, daily_slug, ensure_daily
from brain.index import rebuild_index
from brain.recipes import get_recipe, run_recipe, seed_automations
from brain.session import lock
from brain.ui_server import graph_payload
from brain.vault import init_vault
from brain.wikilinks import extract_wikilink_slugs, normalize_wikilink_target


@pytest.fixture
def cfgdir(tmp_path, monkeypatch):
    d = tmp_path / "cfg"
    d.mkdir()
    monkeypatch.setenv("BRAIN_CONFIG_DIR", str(d))
    lock()
    yield d
    lock()


def test_wikilink_extract_and_normalize():
    assert normalize_wikilink_target("elseveir-bridge") == "elseveir-bridge"
    assert normalize_wikilink_target("Elsevier Bridge") == "elsevier-bridge"
    body = "See [[elseveir-bridge]] and [[how-to-use-brain|protocol]] plus [[Bad Link!]]."
    slugs = extract_wikilink_slugs(body)
    assert "elseveir-bridge" in slugs
    assert "how-to-use-brain" in slugs
    assert "bad-link" in slugs


def test_parse_merges_wikilinks_into_frontmatter_links(cfgdir, tmp_path):
    text = """---
id: note-a
title: Note A
tags: []
projects: []
links:
  - existing-link
secure: false
updated: "2026-01-01"
---

# TL;DR
Hello

## Details
Also see [[elseveir-bridge]] and [[existing-link]].
"""
    card = parse_card(text)
    assert "existing-link" in card.links
    assert "elseveir-bridge" in card.links
    assert card.links.count("existing-link") == 1


def test_backlinks_and_add_link_writes_wikilink(cfgdir, tmp_path):
    vault = init_vault(tmp_path / "v4")
    write_card(
        vault,
        Card(
            id="alpha",
            title="Alpha",
            body="# TL;DR\nA\n\n## Details\n\nx\n",
        ),
    )
    write_card(
        vault,
        Card(
            id="beta",
            title="Beta",
            body="# TL;DR\nB\n\n## Details\n\n[[alpha]]\n",
        ),
    )
    rebuild_index(vault)
    bl = backlinks(vault, "alpha")
    assert any(b["id"] == "beta" for b in bl)

    add_link(vault, "alpha", "how-to-use-brain")
    alpha = read_card(vault, "alpha")
    assert "how-to-use-brain" in alpha.links
    assert "[[how-to-use-brain]]" in alpha.body


def test_daily_note_and_recipe(cfgdir, tmp_path):
    vault = init_vault(tmp_path / "vd")
    seed_automations(vault)
    today = date.today()
    card = ensure_daily(vault, today)
    assert card.id == daily_slug(today)
    assert "daily" in card.tags
    # idempotent
    again = ensure_daily(vault, today)
    assert again.id == card.id

    prev = ensure_daily(vault, today - timedelta(days=1))
    # refresh today to pick up prev link only on create — create next day note
    nxt = ensure_daily(vault, today + timedelta(days=1))
    assert daily_slug(today) in nxt.links or f"[[{daily_slug(today)}]]" in nxt.body

    r = get_recipe(vault, "daily-note")
    assert r.id == "daily-note"
    result = run_recipe(vault, "daily-note")
    assert any("daily=" in line for line in result["log"])
    assert prev.id.startswith("daily-")


def test_graph_orphan_flag(cfgdir, tmp_path):
    vault = init_vault(tmp_path / "vg")
    write_card(
        vault,
        Card(id="lonely", title="Lonely", body="# TL;DR\nAlone\n\n## Details\n\n.\n"),
    )
    rebuild_index(vault)
    g = graph_payload(vault)
    lonely = next(n for n in g["nodes"] if n["id"] == "lonely")
    assert lonely["orphan"] is True
    hubbish = next(n for n in g["nodes"] if n["id"] == "how-to-use-brain")
    assert hubbish["orphan"] is False


def test_version_0_4():
    from brain import __version__

    assert __version__.startswith("0.4")
