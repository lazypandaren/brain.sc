# Build & package (macOS)

## Why package it

End users should get a double-clickable **Brain.app** plus a `brain` CLI without hand-rolling a venv. The `.pkg` installs into `/usr/local/lib/brain-tools` and wires `/usr/local/bin/brain`.

## Prerequisites

- macOS with Xcode CLT (for packaging scripts)
- Network once to fetch Python deps into the staging tree (see `scripts/macos/build-installer.sh`)

## Build

From the repo root:

```bash
./scripts/macos/build-installer.sh
```

Output:

```text
dist/macos/BrainTools-<version>-<arch>.pkg
```

## Install / upgrade

```bash
# Fresh install
sudo installer -pkg dist/macos/BrainTools-*.pkg -target /

# In-place upgrade (vault untouched)
./scripts/macos/upgrade.sh dist/macos/BrainTools-*.pkg
# or, after CLI is installed:
brain upgrade --pkg /path/to/BrainTools-*.pkg
```

Dev hot-patch (no pkg):

```bash
sudo bash scripts/macos/hot-patch-desktop.sh
```

## Verify

```bash
brain --version    # expect 0.3.0+
brain doctor
brain desktop      # or open Brain.app
```

Close the window → menu-bar 🧠 should remain. Open Brain.app again → window should show. Quit only via 🧠 → Quit.

## What is not in the package

- Your vault (Google Drive / local path)
- `~/.config/brain/` (ports, root pointer, machine wrap key / Keychain item)
- Secrets inside `secure/*.enc`
