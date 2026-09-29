#!/bin/bash
# Build single macOS installer with Applications/Brain.app + bundled CPython
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ARCH="$(uname -m)"
DIST="${BRAIN_DIST:-$ROOT/dist/macos}"
STAGE="$DIST/stage"
SCRIPTS="$DIST/scripts"
IDENT="com.braintools.cli"
PLATFORM="macosx_11_0_${ARCH}"

# Standalone CPython (astral-sh/python-build-standalone) — no system Python needed at install time
PBS_TAG="${BRAIN_PBS_TAG:-20260728}"
PBS_PY_VER="${BRAIN_PBS_PY_VER:-3.12.13}"
case "$ARCH" in
  arm64) PBS_TARGET="aarch64-apple-darwin" ;;
  x86_64) PBS_TARGET="x86_64-apple-darwin" ;;
  *) echo "ERROR: unsupported arch $ARCH" >&2; exit 1 ;;
esac
PBS_NAME="cpython-${PBS_PY_VER}+${PBS_TAG}-${PBS_TARGET}-install_only.tar.gz"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${PBS_NAME}"
RUNTIME_CACHE="$ROOT/vendor/runtime-python"
RUNTIME_TGZ="$ROOT/vendor/${PBS_NAME}"

ensure_runtime_python() {
  if [[ -x "$RUNTIME_CACHE/python/bin/python3" ]]; then
    echo "==> Using cached runtime Python: $("$RUNTIME_CACHE/python/bin/python3" -V 2>&1)"
    return 0
  fi
  echo "==> Downloading bundled CPython ${PBS_PY_VER} (${PBS_TARGET})"
  mkdir -p "$ROOT/vendor"
  if [[ ! -f "$RUNTIME_TGZ" ]]; then
    curl -fL --retry 3 -o "$RUNTIME_TGZ" "$PBS_URL"
  fi
  rm -rf "$RUNTIME_CACHE"
  mkdir -p "$RUNTIME_CACHE"
  tar -xzf "$RUNTIME_TGZ" -C "$RUNTIME_CACHE"
  # tarball extracts as ./python
  if [[ ! -x "$RUNTIME_CACHE/python/bin/python3" ]]; then
    echo "ERROR: runtime python missing after extract" >&2
    ls -laR "$RUNTIME_CACHE" | head -40 >&2
    exit 1
  fi
  echo "==> Runtime ready: $("$RUNTIME_CACHE/python/bin/python3" -V 2>&1)"
}

ensure_runtime_python

BUILD_PY="${BRAIN_BUILD_PYTHON:-$RUNTIME_CACHE/python/bin/python3}"
VERSION="$("$BUILD_PY" -c "import re; t=open('$ROOT/pyproject.toml').read(); print(re.search(r'version\\s*=\\s*\\\"([^\\\"]+)\\\"', t).group(1))")"
PKG_NAME="BrainTools-${VERSION}-${ARCH}.pkg"

echo "==> Building BrainTools ${VERSION} (${ARCH}) with $BUILD_PY"
if ! rm -rf "$DIST" 2>/dev/null; then
  FALLBACK="$ROOT/dist/macos-$(date +%Y%m%d-%H%M%S)"
  echo "WARN: cannot clear $DIST (root-owned?). Building into $FALLBACK"
  DIST="$FALLBACK"
  STAGE="$DIST/stage"
  SCRIPTS="$DIST/scripts"
  rm -rf "$DIST"
fi
rm -rf "$ROOT/vendor/wheels"
mkdir -p "$STAGE/usr/local/lib/brain-tools" "$STAGE/Applications" "$SCRIPTS" "$ROOT/vendor/wheels"

if [[ ! -f "$ROOT/packaging/macos/AppIcon.icns" ]]; then
  echo "ERROR: missing packaging/macos/AppIcon.icns" >&2
  exit 1
fi

echo "==> Assembling Brain.app"
bash "$ROOT/packaging/macos/assemble-app.sh" "$VERSION" "$STAGE/Applications"

echo "==> Vendoring runtime wheels (deps from pyproject.toml)"
# Single source of truth: [project.dependencies] in pyproject.toml (no requirements*.txt)
"$BUILD_PY" -m pip download -d "$ROOT/vendor/wheels" setuptools wheel \
  $("$BUILD_PY" -c "
import re, pathlib
t = pathlib.Path(r'$ROOT/pyproject.toml').read_text()
m = re.search(r'dependencies\s*=\s*\[(.*?)\]', t, re.S)
assert m, 'project.dependencies missing in pyproject.toml'
print(' '.join(re.findall(r'[\"\\']([^\"\\']+)[\"\\']', m.group(1))))
") >/dev/null
for ver in 310 311 312 313 314; do
  "$BUILD_PY" -m pip download -d "$ROOT/vendor/wheels" \
    --only-binary=:all: \
    --python-version "$ver" \
    --platform "$PLATFORM" \
    --implementation cp \
    --abi "cp${ver}" \
    PyYAML cryptography cffi argon2-cffi argon2-cffi-bindings \
    >/dev/null 2>&1 || true
done
# pywebview / pyobjc for the bundled 3.12
"$BUILD_PY" -m pip download -d "$ROOT/vendor/wheels" \
  --only-binary=:all: \
  --python-version 312 \
  --platform "$PLATFORM" \
  --implementation cp \
  --abi cp312 \
  pywebview pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit \
  pyobjc-framework-Quartz pyobjc-framework-Security \
  pyobjc-framework-UniformTypeIdentifiers \
  >/dev/null 2>&1 || true
"$BUILD_PY" -m pip wheel "$ROOT" -w "$ROOT/vendor/wheels" >/dev/null

rsync -a \
  --exclude '.venv' \
  --exclude 'dist' \
  --exclude '.pytest_cache' \
  --exclude '**/__pycache__' \
  --exclude '*.egg-info' \
  --exclude '.git' \
  --exclude 'vendor/runtime-python' \
  --exclude 'vendor/cpython-*.tar.gz' \
  "$ROOT/" "$STAGE/usr/local/lib/brain-tools/"

# Bundle standalone CPython into the package
echo "==> Staging bundled runtime Python"
mkdir -p "$STAGE/usr/local/lib/brain-tools/runtime"
rm -rf "$STAGE/usr/local/lib/brain-tools/runtime/python"
cp -a "$RUNTIME_CACHE/python" "$STAGE/usr/local/lib/brain-tools/runtime/python"

# Also keep a copy of the app next to tools (repair / reference)
bash "$ROOT/packaging/macos/assemble-app.sh" "$VERSION" "$STAGE/usr/local/lib/brain-tools"

cp "$ROOT/scripts/macos/uninstall.sh" "$STAGE/usr/local/lib/brain-tools/uninstall.sh"
chmod 755 "$STAGE/usr/local/lib/brain-tools/uninstall.sh"
cp "$ROOT/scripts/macos/postinstall" "$SCRIPTS/postinstall"
chmod 755 "$SCRIPTS/postinstall"

# Inject exact version into postinstall wheel pin (already matches pyproject)
pkgbuild \
  --root "$STAGE" \
  --scripts "$SCRIPTS" \
  --identifier "$IDENT" \
  --version "$VERSION" \
  --install-location "/" \
  "$DIST/$PKG_NAME"

ls -lh "$DIST/$PKG_NAME"
echo "Package: $DIST/$PKG_NAME"
echo "Installs: /Applications/Brain.app + /usr/local/bin/brain + bundled CPython"
echo "Upgrade (recommended, vault untouched):"
echo "  brain upgrade --pkg \"$DIST/$PKG_NAME\""
echo "  # or: ./scripts/macos/upgrade.sh \"$DIST/$PKG_NAME\""
echo "Clean reinstall only if broken:"
echo "  sudo bash /usr/local/lib/brain-tools/uninstall.sh"
echo "  sudo installer -pkg \"$DIST/$PKG_NAME\" -target /"
