#!/usr/bin/env bash
# Install / remove the Silver Wolf Plymouth boot splash.
#   sudo ./plymouth/install.sh            install + make default (rebuilds initramfs, ~1 min)
#   sudo ./plymouth/install.sh --revert   go back to the Kali splash
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
SRC="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)/silverwolf"
DEST=/usr/share/plymouth/themes/silverwolf
PREV_FILE=/usr/share/plymouth/themes/.silverwolf-previous

case "${1:-}" in
  --revert)
    prev=$(cat "$PREV_FILE" 2>/dev/null || echo kali)
    plymouth-set-default-theme -R "$prev"
    echo "restored splash: $prev" ;;
  *)
    [ -d "$SRC" ] || { echo "missing $SRC - run: python3 tools/make_plymouth.py"; exit 1; }
    [ -f "$PREV_FILE" ] || plymouth-set-default-theme > "$PREV_FILE"
    rm -rf "$DEST"
    cp -r "$SRC" "$DEST"
    chmod -R a+rX "$DEST"
    plymouth-set-default-theme -R silverwolf
    echo "Silver Wolf splash installed. It shows on next boot/shutdown."
    echo "Undo with: sudo $0 --revert" ;;
esac
