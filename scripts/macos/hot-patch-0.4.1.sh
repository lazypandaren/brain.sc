#!/bin/bash
# Back-compat wrapper — prefer scripts/macos/hot-patch.sh
exec "$(cd "$(dirname "$0")" && pwd)/hot-patch.sh" "$@"
