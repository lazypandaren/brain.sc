"""In-place upgrade of the installed BrainTools package (no uninstall needed)."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from brain import __version__
from brain.errors import BrainError
from brain.resources import tools_home


def find_pkg(explicit: str | Path | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_file() or p.suffix != ".pkg":
            raise BrainError(f"Not a .pkg file: {p}")
        return p

    arch = platform.machine()  # arm64 / x86_64
    candidates: list[Path] = []
    roots = [
        Path.cwd() / "dist" / "macos",
        tools_home() / "dist" / "macos",
        Path.home() / "Downloads",
        Path.cwd(),
    ]
    for root in roots:
        if not root.is_dir():
            continue
        candidates.extend(root.glob(f"BrainTools-*-{arch}.pkg"))
        candidates.extend(root.glob("BrainTools-*.pkg"))

    # Prefer matching arch, then newest mtime
    def score(p: Path) -> tuple[int, float]:
        name = p.name
        arch_hit = 1 if arch in name else 0
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (arch_hit, mtime)

    if not candidates:
        raise BrainError(
            "Не знайдено BrainTools-*.pkg. Збери: ./scripts/macos/build-installer.sh "
            "або передай шлях: brain upgrade --pkg /path/to/BrainTools-….pkg"
        )
    candidates.sort(key=score, reverse=True)
    return candidates[0].resolve()


def run_upgrade(pkg: Path, *, dry_run: bool = False) -> list[str]:
    """Install/upgrade via macOS installer. Keeps vault + ~/.config/brain."""
    lines = [
        f"current_version={__version__}",
        f"pkg={pkg}",
        f"tools_home={tools_home()}",
    ]
    if dry_run:
        lines.append("dry_run=1 (sudo installer not executed)")
        return lines

    installer = shutil.which("installer")
    if not installer:
        raise BrainError("macOS `installer` not found")

    # Drop quarantine so Gatekeeper is less likely to block silent upgrade
    subprocess.run(
        ["sudo", "xattr", "-dr", "com.apple.quarantine", str(pkg)],
        check=False,
        capture_output=True,
    )

    cmd = ["sudo", installer, "-pkg", str(pkg), "-target", "/"]
    lines.append(f"running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.stdout.strip():
        lines.append(proc.stdout.strip())
    if proc.stderr.strip():
        lines.append(proc.stderr.strip())
    if proc.returncode != 0:
        raise BrainError(
            f"installer failed ({proc.returncode}). "
            "Якщо Gatekeeper блокує: sudo xattr -dr com.apple.quarantine <pkg>"
        )
    lines.append("upgrade_ok=1 (vault і ~/.config/brain збережені)")
    lines.append("Перезапусти Brain.app / brain ui щоб підхопити новий код.")
    return lines


def upgrade_hint() -> str:
    return (
        f"Встановлено brain {__version__}. "
        "Апгрейд без реінсталу: `brain upgrade --pkg BrainTools-….pkg` "
        "або `./scripts/macos/upgrade.sh path/to.pkg`. "
        "Clean reinstall лише якщо зламалось: uninstall.sh потім новий .pkg."
    )
