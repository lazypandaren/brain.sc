# macOS installer

Single artifact: **`BrainTools-<version>-<arch>.pkg`**

The package is **self-contained**: bundled CPython 3.12 + vendored wheels.
End machines do **not** need Homebrew, Xcode CLT, or a system Python.

```bash
./scripts/macos/build-installer.sh
# → dist/macos/BrainTools-<version>-<arch>.pkg
```

| | |
|--|--|
| Install | Double-click `.pkg` or `sudo installer -pkg … -target /` |
| **Upgrade** | Same `.pkg` over existing install — **no uninstall**. CLI: `brain upgrade --pkg …` or `./scripts/macos/upgrade.sh` |
| Layout | **`/Applications/Brain.app`** + `/usr/local/bin/brain` + `/usr/local/lib/brain-tools` |
| Launch | Launchpad → **Brain**, or `brain ui` / `brain desktop` |
| Autostart UI | `brain autostart on` (LaunchAgent `com.braintools.ui`) |
| Vault path | Google Drive / your folder — **untouched** on upgrade/uninstall |
| Dependencies | **None** (Python inside the package) |
| Remove | `/usr/local/lib/brain-tools/uninstall.sh` |

Full build notes: [`BUILD.md`](BUILD.md).

## Sign & notarize (optional, recommended on Sequoia+)

Unsigned Python hosts often show up as `python3.12` in **System Settings → Menu Bar**, and status items can vanish. Prefer a signed `Brain.app`:

```bash
export BRAIN_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export BRAIN_INSTALLER_ID="Developer ID Installer: Your Name (TEAMID)"
# either:
export BRAIN_NOTARY_PROFILE="BrainNotary"   # xcrun notarytool store-credentials
# or: APPLE_ID / APPLE_APP_SPECIFIC_PASSWORD / APPLE_TEAM_ID

./scripts/macos/build-installer.sh
./scripts/macos/sign-and-notarize.sh dist/macos/stage/Applications/Brain.app \
  dist/macos/BrainTools-<version>-<arch>.pkg
```

Without credentials the script **exits 0 with SKIP** (safe for CI).

## CI release

Push tag `v0.5.0` (or any `v*`) → GitHub Actions builds the `.pkg`, optionally signs when repo secrets are set, and attaches it to the GitHub Release.
