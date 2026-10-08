#!/bin/bash
# Sign Brain.app + optionally notarize / staple a .pkg.
#
# Credentials are REQUIRED for real signing/notarization (Apple Developer).
# Without them the script exits 0 after printing SKIP — so CI can call it safely.
#
# Env (signing):
#   BRAIN_SIGN_IDENTITY   e.g. "Developer ID Application: …"
#   BRAIN_INSTALLER_ID    e.g. "Developer ID Installer: …" (for productsign)
#
# Env (notarization) — one of:
#   BRAIN_NOTARY_PROFILE  keychain profile from `xcrun notarytool store-credentials`
#   or APPLE_ID + APPLE_APP_SPECIFIC_PASSWORD + APPLE_TEAM_ID
#
# Usage:
#   ./scripts/macos/sign-and-notarize.sh [path/to/Brain.app] [path/to/BrainTools-….pkg]
set -euo pipefail

APP="${1:-/Applications/Brain.app}"
PKG="${2:-}"

SIGN_ID="${BRAIN_SIGN_IDENTITY:-}"
INSTALLER_ID="${BRAIN_INSTALLER_ID:-}"

if [[ -z "$SIGN_ID" ]]; then
  echo "SKIP: BRAIN_SIGN_IDENTITY unset — ad-hoc / unsigned build is fine for local use."
  echo "      For Menu Bar reliability on Sequoia+, sign+notarize with a Developer ID."
  exit 0
fi

if [[ ! -d "$APP" ]]; then
  echo "ERROR: app not found: $APP" >&2
  exit 1
fi

echo "==> codesign $APP"
codesign --force --deep --options runtime --timestamp \
  --sign "$SIGN_ID" \
  "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

if [[ -n "$PKG" ]]; then
  if [[ ! -f "$PKG" ]]; then
    echo "ERROR: pkg not found: $PKG" >&2
    exit 1
  fi
  if [[ -z "$INSTALLER_ID" ]]; then
    echo "WARN: BRAIN_INSTALLER_ID unset — skipping productsign (app signed only)"
  else
    SIGNED_PKG="${PKG%.pkg}-signed.pkg"
    echo "==> productsign → $SIGNED_PKG"
    productsign --sign "$INSTALLER_ID" "$PKG" "$SIGNED_PKG"
    PKG="$SIGNED_PKG"
  fi

  NOTARY_ARGS=()
  if [[ -n "${BRAIN_NOTARY_PROFILE:-}" ]]; then
    NOTARY_ARGS=(--keychain-profile "$BRAIN_NOTARY_PROFILE")
  elif [[ -n "${APPLE_ID:-}" && -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" && -n "${APPLE_TEAM_ID:-}" ]]; then
    NOTARY_ARGS=(
      --apple-id "$APPLE_ID"
      --password "$APPLE_APP_SPECIFIC_PASSWORD"
      --team-id "$APPLE_TEAM_ID"
    )
  else
    echo "SKIP notarization: set BRAIN_NOTARY_PROFILE or APPLE_ID/APPLE_APP_SPECIFIC_PASSWORD/APPLE_TEAM_ID"
    echo "Signed pkg: $PKG"
    exit 0
  fi

  echo "==> notarytool submit $PKG"
  xcrun notarytool submit "$PKG" --wait "${NOTARY_ARGS[@]}"
  echo "==> stapler"
  xcrun stapler staple "$PKG"
  if [[ -d "$APP" ]]; then
    xcrun stapler staple "$APP" 2>/dev/null || true
  fi
  echo "Notarized: $PKG"
fi

echo "Done."
