# Silver Wolf Desktop Companion

A fan-made Silver Wolf (Honkai: Star Rail) companion that floats on your Linux
desktop. She hops when you boop her, blows bubblegum, levels up, talks in speech
bubbles, reacts to your system with chiptune sounds, and can transform into
**LV.999** with a magical girl transformation.

> This is the `sw999` branch with the LV.999 transformation.
> The original companion without it is on `main`.

## Features

- **Floating chibi** that you can drag anywhere. Scroll to resize, double-click for the next look.
- **Boop her** to make her hop and pop bubblegum. Every boop gives +EXP, and every 10 EXP is a level up.
- **Speech bubbles** for greetings, idle chatter, late-night lines and reactions.
- **System reactions** with chiptune sound effects for:
  - CPU load and temperature, GPU, RAM and battery
  - Wi-Fi going up or down
  - USB drives being plugged in
  - finished downloads
- **Sleepy mode** at night. She floats slower, shows Zzz, and fades a little between 0:00 and 6:00.
- **Glitch effects and data particles**, both of which can be turned off.
- **Click-through, mirror, opacity, size and wander** options in the right-click menu.

### LV.999 transformation

Boop her 10 times fast, or right-click → **Insert cartridge: LV.999**. Now and
then she also does it by surprise.

1. The LV.999 cartridge drops in and slots into her handheld, and the screen shows `999`.
2. A spinning pink and cyan **magic circle** opens under her. A pillar of light and sparkles rise while she floats up.
3. A **white scanner line** sweeps up from her feet and rewrites her into LV.999 as it goes.
4. A flash, and **LV.999** pops up.

As LV.999 she has her own idle and occasionally points at you. Her ultimate,
**Godmode**, pulls her visor down into the pixel shades. Use it from the menu or
boop her 3 times. When her time runs out, the cartridge ejects and she goes back
to normal.

## Controls

| Action | What it does |
| --- | --- |
| Left-drag | Move her |
| Click | Boop: hop, bubblegum, +EXP |
| Boop 10x fast | Insert the LV.999 cartridge |
| Boop 3x (as LV.999) | Godmode |
| Double-click | Next image in `images/` |
| Scroll | Resize |
| Right-click | Menu (also in the tray icon) |

## Install

Needs Python 3, PyQt6 and psutil:

```bash
pip install PyQt6 psutil
./run.sh
```

To start her automatically at login:

```bash
./install-autostart.sh            # install
./install-autostart.sh --remove   # undo
```

To use your own looks, drop any transparent PNG, GIF or WebP into `images/`.

## LV.999 art (not included)

The LV.999 art, references and voice lines belong to HoYoverse, so they are
**not** in this repo. `forms/` and `References/` are git-ignored. Without the
art she still transforms, but stays in her normal look with a cyan and pink
glow.

To get the full LV.999 look locally:

- **Chibi look (default):** put her four official LV.999 chat stickers in
  `forms/sw999_chibi/` as `01` to `04` (PNG or WebP):
  - `01`: gum and handheld
  - `02`: pointing
  - `03`: star shades
  - `04`: pixel-shades bubble
- **Full-size look:** run `tools/make_sw999_form.py` and `tools/make_sw999_idle.py`
  on reference images in `References/` to cut her out. The script headers list
  the extra Python packages they need.
- **Voice lines:** run `tools/make_sw999_lines.py` on a saved copy of her wiki
  voice-over page.

## Extras

These are optional, and both installers need sudo:

- `plymouth/install.sh`: Silver Wolf boot and shutdown splash. Undo it with `--revert`.
- `lightdm/install.sh`: Silver Wolf login screen theme. It expects a wallpaper
  path set inside the script. Undo it with `--revert`.
- `tools/make_cursors.py`: pixel-art cursor theme.
- `tools/make_sounds.py`: regenerates the chiptune sound effects. They're pure
  synthesis, so nothing is downloaded.

## Disclaimer

Fan project, not affiliated with HoYoverse. Silver Wolf and Honkai: Star Rail
belong to HoYoverse.
