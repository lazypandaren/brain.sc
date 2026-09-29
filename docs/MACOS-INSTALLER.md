# macOS installer

Один артефакт: **`BrainTools-<version>-<arch>.pkg`**

Пакет **self-contained**: всередині bundled CPython 3.12 + vendored wheels.
На машині користувача **не потрібні** Homebrew, Xcode CLT і системний Python.

```bash
./scripts/macos/build-installer.sh
# → dist/macos/BrainTools-0.1.2-arm64.pkg
```

| | |
|--|--|
| Встановлення | подвійний клік на `.pkg` або `sudo installer -pkg … -target /` |
| **Апгрейд** | той самий `.pkg` поверх існуючого — **без uninstall**. CLI: `brain upgrade --pkg …` або `./scripts/macos/upgrade.sh` |
| Куди ставить | **`/Applications/Brain.app`** + `/usr/local/bin/brain` + `/usr/local/lib/brain-tools` |
| Запуск | Launchpad → **Brain**, або `brain ui` / `brain desktop` |
| Автозапуск UI | `brain autostart on` (LaunchAgent `com.braintools.ui`) |
| Vault path | Google Drive / твоя папка — **не чіпається** при upgrade/uninstall |
| Залежності | **Немає** (Python у пакеті) |
| Видалення | `/usr/local/lib/brain-tools/uninstall.sh` |

## Upgrade (рекомендовано)

Не треба `rm -rf` і `pkgutil --forget`, якщо інсталяція здорова:

```bash
./scripts/macos/build-installer.sh
brain upgrade --pkg dist/macos/BrainTools-0.1.2-arm64.pkg
# або
./scripts/macos/upgrade.sh dist/macos/BrainTools-0.1.2-arm64.pkg
```

Postinstall перестворює `.venv`, кладе новий `Brain.app`, оновлює wrapper. Vault і `~/.config/brain` лишаються.

Після апгрейду: перезапусти UI (`brain ui` / Brain.app) і за бажанням `brain agents install`.

## Clean reinstall (лише якщо зламалось)

```bash
sudo bash /usr/local/lib/brain-tools/uninstall.sh
sudo installer -pkg dist/macos/BrainTools-0.1.2-arm64.pkg -target /
```

Лог postinstall: `/tmp/braintools-install.log`.

Без підпису Apple Developer Gatekeeper може попередити → ПКМ → Open або:

```bash
sudo xattr -dr com.apple.quarantine BrainTools-*.pkg
```
