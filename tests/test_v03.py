"""Tests for Brain 0.3 features: topics import, probe, write-back helpers, wrap key."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.cards import read_card
from brain.crypto import KEY_LEN, machine_wrap_key
from brain.doctor import run_doctor
from brain.importer import import_topics, slugify
from brain.recipes import remember
from brain.service import probe_ui
from brain.session import lock
from brain.vault import init_vault


@pytest.fixture
def cfgdir(tmp_path, monkeypatch):
    d = tmp_path / "cfg"
    d.mkdir()
    monkeypatch.setenv("BRAIN_CONFIG_DIR", str(d))
    lock()
    yield d
    lock()


def test_version_is_semver_040_line():
    from brain import __version__

    # 0.3.x tests remain; package may be newer — accept 0.3+ for this module's dep checks
    parts = __version__.split(".")
    assert int(parts[0]) == 0
    assert int(parts[1]) >= 3


def test_deps_only_in_pyproject():
    root = Path(__file__).resolve().parents[1]
    assert (root / "pyproject.toml").is_file()
    assert not (root / "requirements.txt").exists()
    assert not (root / "requirements-runtime.txt").exists()
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "cryptography" in text
    assert "pywebview" in text


def test_slugify_topics():
    assert slugify("Hello World") == "hello-world"
    assert "win" in slugify("SCMO-Win2022")


def test_import_topics_summary(cfgdir, tmp_path):
    vault = init_vault(tmp_path / "v")
    topics = tmp_path / "topics"
    topics.mkdir()
    (topics / "sample-topic.md").write_text(
        "# Sample Topic\n\n"
        "First paragraph is the gist of this long note.\n\n"
        "## Deep dive\n\n" + ("x" * 2000) + "\n",
        encoding="utf-8",
    )
    result = import_topics(vault, topics, tag="elseveir-topic")
    assert result["count"] == 1
    assert "sample-topic" in result["imported"]
    card = read_card(vault, "sample-topic")
    assert "elseveir-topic" in card.tags
    assert "elseveir" in card.projects
    assert "gist" in card.tldr.lower() or "sample" in card.tldr.lower()
    assert len(card.body) < 2500  # truncated details

    # idempotent skip
    again = import_topics(vault, topics)
    assert again["count"] == 0
    assert any("exists" in s for s in again["skipped"])


def test_remember_writeback(cfgdir, tmp_path):
    vault = init_vault(tmp_path / "mem")
    remember(vault, "0.3 write-back works", source="test")
    text = (vault / "core" / "memory.md").read_text(encoding="utf-8")
    assert "0.3 write-back works" in text


def test_machine_wrap_key_stable(cfgdir):
    a = machine_wrap_key()
    b = machine_wrap_key()
    assert len(a) == KEY_LEN
    assert a == b


def test_probe_ui_down(cfgdir, monkeypatch):
    monkeypatch.setenv("BRAIN_CONFIG_DIR", str(cfgdir))
    # unlikely open high port
    from brain.config import save_user_config, load_user_config

    cfg = load_user_config()
    cfg["ui_port"] = 59999
    save_user_config(cfg)
    p = probe_ui(59999)
    assert p["state"] == "down"


def test_doctor_includes_probe_and_wrap(cfgdir, tmp_path):
    vault = init_vault(tmp_path / "doc")
    report = run_doctor(vault)
    assert report.ok, report.issues
    joined = " ".join(report.info)
    assert "session_wrap=" in joined
    assert "ui_probe=" in joined
