#!/usr/bin/env python3
"""Generate the "silverwolf" Plymouth boot splash into ../plymouth/silverwolf/.

All text is pre-rendered to PNG (VT323 / Good Times) because the initramfs
won't have your fonts. Install with:  sudo ./plymouth/install.sh
"""
import getpass
import shutil
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage,
                         QLinearGradient, QPainter)

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "plymouth" / "silverwolf"
CHIBI = HERE / "images" / "silverwolfchibi.png"
REF_H = 1600  # images are drawn for a 1600 px tall screen; the script rescales

VIOLET, PINK, CYAN, TEXT, DIM, DARK = ("#b48cff", "#ff6bd6", "#5ef2ff",
                                       "#e8e6ff", "#8b86a8", "#0e0a1a")
USER = getpass.getuser()

LOG = [
    ("OK", "mounting /dev/realm"),
    ("OK", "bypassing firewall (it was cute)"),
    ("OK", "loading bubblegum.so"),
    ("**", "spoofing MAC 5W:0L:F0:00:13:37"),
    ("OK", "patching reality v2.7"),
    ("OK", "syncing save file SilverWolf.sav"),
    ("OK", "spawning daemon: glitchd"),
    ("OK", "decrypting hunters.db"),
    ("!!", "sleep.exe not responding, ignoring"),
    ("OK", "calibrating pixel shaders"),
    ("OK", "overclocking fun to 165Hz"),
    ("OK", f"granting root to player: {USER}"),
    ("OK", "warming up GPU (RTX goes brrr)"),
    ("OK", "restoring desktop companion"),
    ("**", "hiding from the sysadmin"),
    ("OK", "LEVEL data loaded"),
]
SHUT_LOG = [
    ("OK", "saving progress"),
    ("OK", "stashing loot in /home"),
    ("OK", "wiping footprints from logs"),
    ("OK", "unmounting /dev/realm"),
    ("OK", "glitchd: going to sleep"),
    ("**", "see you next session, player one"),
]


def font(family, px, bold=False):
    f = QFont(family)
    f.setPixelSize(px)
    f.setBold(bold)
    f.setStyleStrategy(QFont.StyleStrategy.NoAntialias if family == "VT323"
                       else QFont.StyleStrategy.PreferAntialias)
    return f


def text_img(runs, fnt, path, shadow=True, pad=6):
    """runs: [(text, color), ...] drawn left to right."""
    fm = QFontMetrics(fnt)
    w = sum(fm.horizontalAdvance(t) for t, _ in runs) + pad * 2 + 4
    h = fm.height() + pad * 2
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setFont(fnt)
    x = pad
    for t, c in runs:
        if shadow:  # glitchy chromatic offset + hard shadow
            p.setPen(QColor(14, 10, 26, 220))
            p.drawText(x + 3, pad + fm.ascent() + 3, t)
            cc = QColor(PINK if c != PINK else CYAN)
            cc.setAlpha(110)
            p.setPen(cc)
            p.drawText(x - 2, pad + fm.ascent(), t)
        p.setPen(QColor(c))
        p.drawText(x, pad + fm.ascent(), t)
        x += fm.horizontalAdvance(t)
    p.end()
    img.save(str(OUT / path))


def solid(path, w, h, color, border=None):
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(color))
    if border:
        p = QPainter(img)
        p.setPen(QColor(border))
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()
    img.save(str(OUT / path))


def tinted(src, color, path):
    img = QImage(str(src)).convertToFormat(QImage.Format.Format_ARGB32)
    p = QPainter(img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(img.rect(), QColor(color))
    p.end()
    img.save(str(OUT / path))


def scanlines(path):
    img = QImage(256, 256, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    for y in range(0, 256, 4):
        p.fillRect(0, y, 256, 1, QColor(0, 0, 0, 70))
    p.end()
    img.save(str(OUT / path))


def vignette(path):
    img = QImage(64, 400, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, 400)
    g.setColorAt(0, QColor(180, 140, 255, 0))
    g.setColorAt(1, QColor(180, 80, 220, 70))
    p.fillRect(QRectF(0, 0, 64, 400), g)
    p.end()
    img.save(str(OUT / path))


def main():
    app = QGuiApplication([])  # noqa: F841 (must stay alive)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    shutil.copy(CHIBI, OUT / "chibi.png")
    tinted(CHIBI, "#00f0ff", "chibi_cyan.png")
    tinted(CHIBI, "#ff2bd6", "chibi_pink.png")

    title = font("Good Times", 64)
    sub = font("VT323", 40)
    log = font("VT323", 30)
    text_img([("SW://", CYAN), ("BOOT", VIOLET)], title, "title_boot.png")
    text_img([("SW://", CYAN), ("LOGOUT", VIOLET)], title, "title_shutdown.png")
    text_img([("> ", PINK), ("initializing ", TEXT), ("SilverWolf.exe", VIOLET)], sub, "sub_boot.png")
    text_img([("> ", PINK), ("saving progress... ", TEXT), ("bye, player one", VIOLET)], sub, "sub_shutdown.png")
    text_img([("_", PINK)], sub, "cursor.png", shadow=False)
    text_img([("> ", PINK), ("ACCESS KEY REQUIRED", CYAN)], sub, "prompt.png")
    text_img([("*", PINK)], sub, "bullet.png", shadow=False)

    tag = {"OK": CYAN, "**": PINK, "!!": "#ff6b8a"}
    for name, lines in (("log", LOG), ("slog", SHUT_LOG)):
        for i, (t, msg) in enumerate(lines):
            text_img([("[ ", DIM), (t, tag[t]), (" ] ", DIM), (msg, TEXT)], log, f"{name}{i}.png",
                     shadow=False, pad=2)

    solid("bar_bg.png", 560, 14, "#1a1230", border=VIOLET)  # drawn at final size so the border stays crisp
    solid("bar_fg.png", 8, 8, VIOLET)
    solid("bar_hi.png", 8, 8, PINK)
    solid("glitch_cyan.png", 8, 8, "#5ef2ff")
    solid("glitch_pink.png", 8, 8, "#ff2bd6")
    scanlines("scanlines.png")
    vignette("glow.png")

    script = (HERE / "tools" / "silverwolf.script.in").read_text()
    script = script.replace("@LOG_COUNT@", str(len(LOG))).replace("@SLOG_COUNT@", str(len(SHUT_LOG)))
    (OUT / "silverwolf.script").write_text(script)
    (OUT / "silverwolf.plymouth").write_text(
        "[Plymouth Theme]\nName=Silver Wolf\nDescription=SW://BOOT glitch splash\n"
        "ModuleName=script\n\n[script]\nImageDir=/usr/share/plymouth/themes/silverwolf\n"
        "ScriptFile=/usr/share/plymouth/themes/silverwolf/silverwolf.script\n")
    print("built", OUT, len(list(OUT.iterdir())), "files")


if __name__ == "__main__":
    main()
