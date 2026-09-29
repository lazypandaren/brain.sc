"""Install/sync model-native instruction snippets (Codex, Claude)."""

from __future__ import annotations

from pathlib import Path

from brain.errors import BrainError
from brain.resources import snippets_dir

SNIPPETS = snippets_dir()

MARKER_BEGIN = "<!-- brain-tools:begin -->"
MARKER_END = "<!-- brain-tools:end -->"


def _snippet(name: str) -> str:
    path = SNIPPETS / name
    if not path.is_file():
        raise BrainError(f"Missing snippet: {path}")
    return path.read_text(encoding="utf-8").strip() + "\n"


def _merge_marked(existing: str, block: str) -> str:
    block = f"{MARKER_BEGIN}\n{block.rstrip()}\n{MARKER_END}\n"
    if MARKER_BEGIN in existing and MARKER_END in existing:
        pre = existing.split(MARKER_BEGIN, 1)[0].rstrip()
        post = existing.split(MARKER_END, 1)[1].lstrip()
        parts = [p for p in (pre, block, post) if p]
        return "\n\n".join(parts).rstrip() + "\n"
    if existing.strip():
        return existing.rstrip() + "\n\n" + block
    return block


def install_codex(*, home: Path | None = None) -> Path:
    """Merge brain snippet into ~/.codex/AGENTS.md."""
    base = home or Path.home() / ".codex"
    base.mkdir(parents=True, exist_ok=True)
    target = base / "AGENTS.md"
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    target.write_text(_merge_marked(existing, _snippet("codex-brain.md")), encoding="utf-8")
    return target


def install_claude(*, home: Path | None = None) -> Path:
    """Merge brain snippet into ~/.claude/CLAUDE.md."""
    base = home or Path.home() / ".claude"
    base.mkdir(parents=True, exist_ok=True)
    target = base / "CLAUDE.md"
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    target.write_text(_merge_marked(existing, _snippet("claude-brain.md")), encoding="utf-8")
    return target


def install_cursor(*, home: Path | None = None) -> Path:
    """Write the Cursor Skill to ~/.cursor/skills/brain/SKILL.md (full overwrite)."""
    base = home or Path.home() / ".cursor"
    target = base / "skills" / "brain" / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_snippet("cursor-brain-skill.md"), encoding="utf-8")
    return target


def vault_agent_files() -> dict[str, str]:
    """Short copies for vault root (Drive) — model-native entry points."""
    return {
        "AGENTS.md": (
            "# AGENTS.md — this vault\n\n"
            "1. Read `BRAIN.md` + `core/active.md`.\n"
            "2. `brain search <q>` then ≤3× `brain get` (TL;DR).\n"
            "3. Never read `secure/*.enc` or `_raw/`; never ask for master password.\n"
            "4. Write-back: mid-session → `brain active --set \"…\"`. "
            "Do not auto-save. When wrapping useful work → always ask "
            "чи записати (`brain add` / `brain remember`).\n"
            "5. Tooling repo: `~/Documents/projects/brain-tools` "
            "(`docs/PROTOCOL.md`, `AGENTS.md`, `CLAUDE.md`).\n"
        ),
        "CLAUDE.md": (
            "# CLAUDE.md — this vault\n\n"
            "Token-efficient retrieval only: search → few cards → TL;DR first.\n"
            "Do not decrypt secure cards or solicit the master password.\n"
            "Write-back: `brain active` as scratch; always propose save at wrap-up "
            "(user may forget). Full guide: brain-tools `CLAUDE.md`.\n"
        ),
    }
