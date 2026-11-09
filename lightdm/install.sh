#!/usr/bin/env bash
# Silver Wolf theme for the LightDM GTK login screen.
#   sudo ./lightdm/install.sh           install (takes effect at next login screen)
#   sudo ./lightdm/install.sh --revert  restore your previous greeter config
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJ="$(dirname "$HERE")"
USER_NAME="${SUDO_USER:-$(logname 2>/dev/null || id -un)}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
CONF=/etc/lightdm/lightdm-gtk-greeter.conf
BACKUP=/etc/lightdm/lightdm-gtk-greeter.conf.before-silverwolf
ASSETS=/usr/share/backgrounds/silverwolf
WALL="$USER_HOME/Downloads/wp12692474-silver-wolf-honkai-wallpapers.jpg"
CHIBI="$PROJ/images/silverwolfchibi.png"

if [ "${1:-}" = "--revert" ]; then
  [ -f "$BACKUP" ] && cp "$BACKUP" "$CONF" && echo "restored $CONF"
  if [ -f "/var/lib/AccountsService/users/$USER_NAME.before-silverwolf" ]; then
    mv "/var/lib/AccountsService/users/$USER_NAME.before-silverwolf" "/var/lib/AccountsService/users/$USER_NAME"
  fi
  exit 0
fi

# theme
rm -rf /usr/share/themes/SilverWolf-Greeter
cp -r "$HERE/SilverWolf-Greeter" /usr/share/themes/
chmod -R a+rX /usr/share/themes/SilverWolf-Greeter

# images (the greeter runs as the lightdm user and can't read your home folder)
mkdir -p "$ASSETS"
cp "$WALL" "$ASSETS/login.jpg"
cp "$CHIBI" "$ASSETS/avatar.png"
chmod -R a+rX "$ASSETS"

# fonts used by the theme
mkdir -p /usr/local/share/fonts/silverwolf
cp "$USER_HOME/.local/share/fonts/pixel/VT323-Regular.ttf" \
   "$USER_HOME/.local/share/fonts/SourceCodePro/SourceCodePro-Regular.ttf" \
   "$USER_HOME/.local/share/fonts/SourceCodePro/SourceCodePro-Bold.ttf" \
   /usr/local/share/fonts/silverwolf/ 2>/dev/null || true
chmod -R a+rX /usr/local/share/fonts/silverwolf
fc-cache -f /usr/local/share/fonts/silverwolf >/dev/null

# avatar via AccountsService (what the greeter shows for your user)
mkdir -p /var/lib/AccountsService/icons
cp "$CHIBI" "/var/lib/AccountsService/icons/$USER_NAME"
U="/var/lib/AccountsService/users/$USER_NAME"
if [ -f "$U" ]; then
  [ -f "$U.before-silverwolf" ] || cp "$U" "$U.before-silverwolf"
  if grep -q '^Icon=' "$U"; then
    sed -i "s|^Icon=.*|Icon=/var/lib/AccountsService/icons/$USER_NAME|" "$U"
  else
    sed -i "/^\[User\]/a Icon=/var/lib/AccountsService/icons/$USER_NAME" "$U"
  fi
else
  printf '[User]\nIcon=/var/lib/AccountsService/icons/%s\n' "$USER_NAME" > "$U"
fi

# greeter config
[ -f "$BACKUP" ] || cp "$CONF" "$BACKUP"
cat > "$CONF" <<EOF
# Silver Wolf login screen (installed by SW desktop effects/lightdm/install.sh)
# previous config: $BACKUP
[greeter]
background = $ASSETS/login.jpg
user-background = false
theme-name = SilverWolf-Greeter
icon-theme-name = Flat-Remix-Purple-Dark
font-name = Source Code Pro 11
xft-antialias = true
xft-dpi = 168
xft-hintstyle = slight
xft-rgba = rgb
position = 27%,center 70%,center
indicators = ~host;~spacer;~session;~layout;~a11y;~clock;~power;
clock-format = %d %b, %H:%M
screensaver-timeout = 60
default-user-image = $ASSETS/avatar.png
keyboard = onboard
EOF
echo "Silver Wolf login screen installed. You'll see it next time you log out."
echo "Undo with: sudo $0 --revert"
