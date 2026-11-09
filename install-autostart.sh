#!/usr/bin/env bash
# Start Silver Wolf automatically when you log in. Run with --remove to undo.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
F="$HOME/.config/autostart/silverwolf.desktop"
if [ "$1" = "--remove" ]; then rm -f "$F"; echo "Autostart removed."; exit; fi
mkdir -p "$HOME/.config/autostart"
cat > "$F" <<DESK
[Desktop Entry]
Type=Application
Name=Silver Wolf
Exec="$DIR/run.sh"
Icon=$DIR/images/silverwolfchibi.png
X-GNOME-Autostart-enabled=true
DESK
echo "Autostart installed: $F"
