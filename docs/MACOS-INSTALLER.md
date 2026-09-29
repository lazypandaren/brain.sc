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
