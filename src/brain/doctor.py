"""Health checks: path, index sync, links, crypto, bind safety."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from brain.cards import list_card_meta, parse_card
from brain.config import load_user_config, load_vault_config, resolve_root
from brain.index import index_path, load_index
from brain.paths import VAULT_MARKER, is_vault
from brain.session import is_unlocked


@dataclass
class DoctorReport:
    ok: bool = True
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.issues.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def run_doctor(root: Path | None = None) -> DoctorReport:
    report = DoctorReport()
    try:
        root = root or resolve_root()
    except Exception as e:
        report.fail(str(e))
        return report

    report.info.append(f"root={root}")
    if not is_vault(root):
        report.fail(f"Not a vault: {root}")
        return report
    if not (root / VAULT_MARKER).is_file():
        report.warn(f"Missing {VAULT_MARKER} (legacy?)")

    vcfg = load_vault_config(root)
    if not vcfg.get("crypto", {}).get("salt"):
        report.fail("vault config missing crypto.salt")
    secure_files = list((root / "secure").glob("*.md.enc")) if (root / "secure").is_dir() else []
    if secure_files and not vcfg.get("crypto", {}).get("verifier"):
        report.warn("secure cards present but no password verifier yet (unlock once to set)")

    # Index sync
    live = {c["id"]: c for c in list_card_meta(root)}
    indexed = {c["id"]: c for c in load_index(root)}
    for cid in live:
        if cid not in indexed:
            report.fail(f"index missing card: {cid}")
    for cid in indexed:
        if cid not in live:
            report.warn(f"index has stale card: {cid}")

    ip = index_path(root)
    if ip.is_file():
        try:
            json.loads(ip.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report.fail("search.json is not valid JSON")

    # Broken links (plaintext only unless unlocked)
    for p in sorted((root / "cards").glob("*.md")) if (root / "cards").is_dir() else []:
        try:
            card = parse_card(p.read_text(encoding="utf-8"), path=p)
        except Exception as e:
            report.fail(f"unreadable card {p.name}: {e}")
            continue
        for link in card.links:
            if link not in live:
                report.warn(f"broken link {card.id} → {link}")

    report.info.append(f"cards_plaintext={len(list((root/'cards').glob('*.md'))) if (root/'cards').is_dir() else 0}")
    report.info.append(f"cards_secure={len(secure_files)}")
    report.info.append(f"unlocked={is_unlocked()}")
    ucfg = load_user_config()
    port = int(ucfg.get("ui_port", 8765))
    if not (1 <= port <= 65535):
        report.fail(f"invalid ui_port: {port}")
    else:
        report.info.append(f"ui_port={port} (must bind 127.0.0.1 only)")

    from brain import __version__
    from brain.service import probe_ui, ui_is_running

    report.info.append(f"version={__version__}")
    running = ui_is_running(port if 1 <= port <= 65535 else None)
    report.info.append(f"ui_running={running}")
    probe = probe_ui(port if 1 <= port <= 65535 else None)
    report.info.append(f"ui_probe={probe.get('state')}")
    if probe.get("state") == "port_busy_non_brain":
        report.warn(
            f"Port {port} is open but not Brain API — stuck process or wrong service. "
            "Quit other listeners or change ui_port."
        )
    elif probe.get("state") == "brain_ok":
        report.info.append(f"ui_version={probe.get('version')}")
    elif not running:
        report.warn(
            "Brain UI is not running — start with `brain ui`, Brain.app, or `brain autostart on`"
        )

    try:
        from brain.keychain import backend_name

        report.info.append(f"session_wrap={backend_name()}")
    except Exception:
        report.info.append("session_wrap=file")

    try:
        from brain.desktop_ipc import show_request_path

        sp = show_request_path()
        if sp.is_file():
            report.warn(f"stale desktop show request file: {sp}")
    except Exception:
        pass

    cursor_skill = Path.home() / ".cursor" / "skills" / "brain" / "SKILL.md"
    if cursor_skill.is_file():
        report.info.append(f"cursor_skill={cursor_skill}")
    else:
        report.warn("Cursor skill missing — run `brain agents install --cursor`")

    try:
        from brain.autostart import is_enabled

        report.info.append(f"autostart={is_enabled()}")
    except Exception:
        pass

    return report
