"""Tests for path, crypto, vault lifecycle."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from brain.cards import Card, read_card, write_card
from brain.config import load_user_config, resolve_root, set_root
from brain.crypto import decrypt, derive_key, encrypt, generate_salt
from brain.doctor import run_doctor
from brain.errors import CryptoError, LockedError, PathValidationError
from brain.index import rebuild_index, search
from brain.paths import validate_root_path, validate_slug
from brain.session import lock, unlock
from brain.vault import init_vault


@pytest.fixture
def cfgdir(tmp_path, monkeypatch):
    d = tmp_path / "cfg"
    d.mkdir()
    monkeypatch.setenv("BRAIN_CONFIG_DIR", str(d))
    lock()
    yield d
    lock()


def test_validate_slug():
    assert validate_slug("abc-1") == "abc-1"
    with pytest.raises(PathValidationError):
        validate_slug("../x")
    with pytest.raises(PathValidationError):
        validate_slug("Has Caps")


def test_validate_root_absolute(tmp_path):
    with pytest.raises(PathValidationError):
        validate_root_path("relative/path")
    p = validate_root_path(tmp_path)
    assert p.is_absolute()


def test_crypto_roundtrip():
    salt = generate_salt()
    key = derive_key("test-password-ok", salt)
    blob = encrypt(b"hello brain", key)
    assert decrypt(blob, key) == b"hello brain"
    bad = derive_key("wrong", salt)
    with pytest.raises(CryptoError):
        decrypt(blob, bad)
    with pytest.raises(CryptoError):
        decrypt(blob[:-2], key)


def test_init_search_link(cfgdir, tmp_path):
    vault = tmp_path / "vault"
    root = init_vault(vault)
    assert (root / ".brain-vault").is_file()
    assert resolve_root() == root
    hits = search(root, "elseveir", limit=5)
    assert any(h["id"] == "elseveir-bridge" for h in hits)
    report = run_doctor(root)
    assert report.ok, report.issues


def test_secure_fail_closed(cfgdir, tmp_path):
    vault = tmp_path / "secvault"
    root = init_vault(vault, master_password="s3cret-pass")
    lock()
    with pytest.raises(LockedError):
        read_card(root, "secure-example")
    unlock(root, "s3cret-pass")
    card = read_card(root, "secure-example")
    assert card.secure
    assert "encrypted" in card.tldr.lower() or "secure" in card.body.lower()
    lock()


def test_set_root(cfgdir, tmp_path):
    a = init_vault(tmp_path / "a")
    b = init_vault(tmp_path / "b")
    set_root(b)
    assert resolve_root() == b
    set_root(a)
    assert load_user_config()["root"] == str(a)


def test_add_and_reindex(cfgdir, tmp_path):
    root = init_vault(tmp_path / "v")
    write_card(
        root,
        Card(
            id="aws-tip",
            title="AWS tip",
            tags=["aws"],
            body="# TL;DR\nUse profiles.\n",
        ),
    )
    rebuild_index(root)
    hits = search(root, "aws profiles", limit=3)
    assert hits and hits[0]["id"] == "aws-tip"


def test_vault_has_model_adapters(cfgdir, tmp_path):
    root = init_vault(tmp_path / "multi")
    assert (root / "AGENTS.md").is_file()
    assert (root / "CLAUDE.md").is_file()
    assert "brain search" in (root / "AGENTS.md").read_text(encoding="utf-8")


def test_agents_install(tmp_path):
    from brain.agents_install import install_claude, install_codex

    codex_home = tmp_path / "codex"
    claude_home = tmp_path / "claude"
    p1 = install_codex(home=codex_home)
    p2 = install_claude(home=claude_home)
    assert "brain search" in p1.read_text(encoding="utf-8")
    assert "brain search" in p2.read_text(encoding="utf-8")
    install_codex(home=codex_home)
    text = p1.read_text(encoding="utf-8")
    assert text.count("<!-- brain-tools:begin -->") == 1


def test_init_into_existing_drive_folder(cfgdir, tmp_path):
    """Google Drive folder may already exist and be empty / non-vault."""
    folder = tmp_path / "GoogleDrive" / "BrainSync"
    folder.mkdir(parents=True)
    (folder / "readme-from-drive.txt").write_text("sync ok\n", encoding="utf-8")
    root = init_vault(folder)
    assert (root / ".brain-vault").is_file()
    assert (folder / "readme-from-drive.txt").is_file()


def test_catalog_recipes_memory(cfgdir, tmp_path):
    from brain.recipes import list_recipes, remember, run_recipe, write_catalog

    root = init_vault(tmp_path / "auto")
    assert (root / "index" / "catalog.md").is_file()
    assert (root / "automations" / "nightly-hygiene.md").is_file()
    assert any(r.id == "token-safe-answer" for r in list_recipes(root))
    cat = write_catalog(root).read_text(encoding="utf-8")
    assert "how-to-use-brain" in cat
    remember(root, "prefer catalog over full cards scan", source="test")
    assert "prefer catalog" in (root / "core" / "memory.md").read_text(encoding="utf-8")
    result = run_recipe(root, "nightly-hygiene")
    assert any(x.startswith("ok: reindex") for x in result["log"])
    assert any("doctor" in x for x in result["log"])


def test_import_folder(cfgdir, tmp_path):
    from brain.importer import import_folder, slugify

    root = init_vault(tmp_path / "imp")
    src = tmp_path / "notes"
    src.mkdir()
    (src / "My Note.md").write_text("# Hello\n\nFirst paragraph here.\n", encoding="utf-8")
    (src / "Замітка.md").write_text("просто текст без заголовка\n", encoding="utf-8")
    (src / "with-fm.md").write_text(
        "---\ntitle: Old\n---\n# TL;DR\nalready has tldr\n", encoding="utf-8"
    )

    result = import_folder(root, src)
    assert result["count"] == 3
    assert slugify("My Note") == "my-note"

    card = read_card(root, "my-note")
    assert card.title == "Hello"
    assert "TL;DR" in card.body
    assert "imported" in card.tags
    # search finds imported content
    assert any(h["id"] == "my-note" for h in search(root, "hello", limit=5))


def test_stats_and_usage(cfgdir, tmp_path):
    from brain.stats import log_usage, usage_series, vault_stats

    root = init_vault(tmp_path / "stat")
    s = vault_stats(root)
    assert s["cards"] >= 1
    assert s["full_tokens"] > 0
    assert s["query_tokens"] < s["full_tokens"]
    assert 0 <= s["savings_pct"] <= 99

    log_usage(root, "search", 100, 5000)
    series = usage_series(root, days=3)
    assert len(series) == 3
    today = series[-1]
    assert today["served"] == 100
    assert today["saved"] == 4900


def test_save_feedback(cfgdir, tmp_path):
    from brain.feedback import save_feedback

    root = init_vault(tmp_path / "fb")
    path = save_feedback(
        root,
        {
            "tester": "igor",
            "install_ok": True,
            "score": "9",
            "top_fix": 'кнопка "пароль"',
            "would_use_daily": "no",
        },
        "Загалом норм.\nАле граф міг би бути щільніший.",
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "type: feedback" in text
    assert "install_ok: true" in text
    assert "would_use_daily: false" in text
    assert "score: 9" in text
    assert "first_run_clear: null" in text
    assert "Загалом норм." in text


def test_install_cursor_skill(cfgdir, tmp_path):
    from brain.agents_install import install_cursor

    target = install_cursor(home=tmp_path / ".cursor")
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "brain search" in text
