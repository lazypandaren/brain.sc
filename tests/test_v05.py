"""Tests for Brain 0.5: hubs, agent snippets, desktop split, hot-patch."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.cards import read_card
from brain.hubs import create_hub, list_hubs, parse_aliases, suggest_hubs
from brain.index import rebuild_index
from brain.session import lock
from brain.vault import init_vault

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfgdir(tmp_path, monkeypatch):
    d = tmp_path / "cfg"
    d.mkdir()
    monkeypatch.setenv("BRAIN_CONFIG_DIR", str(d))
    lock()
    yield d
    lock()


def test_parse_aliases_from_tldr():
    aliases = parse_aliases(
        "Aliases: SimOffice, SIMSNG, elseveir, CHG\nWork tickets in docs/.",
        title="Elsevier-project",
        slug="elseveir-bridge",
    )
    lower = {a.lower() for a in aliases}
    assert "simoffice" in lower
    assert "simsng" in lower
    assert "elseveir-bridge" in lower


def test_create_hub_and_suggest(cfgdir, tmp_path):
    root = init_vault(tmp_path / "vault")
    create_hub(
        root,
        "acme-project",
        title="Acme",
        aliases=["ACME", "acme-repo", "TICK-"],
        project="acme",
        blurb="Demo hub",
    )
    rebuild_index(root)
    hubs = list_hubs(root)
    assert any(h.id == "acme-project" for h in hubs)
    card = read_card(root, "acme-project")
    assert "hub" in card.tags
    assert "Aliases:" in card.tldr

    hits = suggest_hubs(root, "working on ACME TICK-42 in acme-repo", limit=2)
    assert hits
    assert hits[0]["id"] == "acme-project"
    assert hits[0]["score"] > 0

    miss = suggest_hubs(root, "totally unrelated zucchini farming", limit=3)
    assert miss == [] or miss[0]["id"] != "acme-project" or miss[0]["score"] < hits[0]["score"]


def test_suggest_prefers_alias_over_noise(cfgdir, tmp_path):
    root = init_vault(tmp_path / "vault")
    create_hub(root, "brain-develop", aliases=["brain-tools", "lazypandaren/brain.sc"])
    create_hub(root, "elseveir-bridge", aliases=["Elsevier", "SimOffice", "SIMSNG"])
    rebuild_index(root)
    hits = suggest_hubs(root, "SIMSNG-6040 SimOffice promote", limit=1)
    assert hits[0]["id"] == "elseveir-bridge"


def test_agent_snippets_include_hub_contract():
    for name in (
        "cursor-brain-skill.md",
        "codex-brain.md",
        "claude-brain.md",
    ):
        text = (ROOT / "agents" / "snippets" / name).read_text(encoding="utf-8")
        assert "hub" in text.lower()
        assert "degree" in text.lower()


def test_desktop_split_modules_import():
    import brain.desktop as desktop
    import brain.desktop_cocoa as cocoa
    import brain.desktop_state as dstate

    assert callable(desktop.run_desktop)
    assert callable(desktop._show_window)
    assert callable(cocoa.patch_tray_lifecycle)
    assert callable(cocoa.menu_bar_image)
    assert callable(dstate.desk_log)


def test_hot_patch_sh_uses_sysconfig():
    text = (ROOT / "scripts" / "macos" / "hot-patch.sh").read_text(encoding="utf-8")
    assert "sysconfig.get_path" in text
    assert "python3.12/site-packages" not in text
    assert "hubs.py" in text


def test_sign_script_skips_without_identity():
    script = ROOT / "scripts" / "macos" / "sign-and-notarize.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "BRAIN_SIGN_IDENTITY" in text
    assert "notarytool" in text


def test_github_workflows_exist():
    assert (ROOT / ".github" / "workflows" / "test.yml").is_file()
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()
    rel = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "build-installer.sh" in rel
    assert "sign-and-notarize.sh" in rel
