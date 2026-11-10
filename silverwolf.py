#!/usr/bin/env python3
"""
Silver Wolf floating desktop companion.

  Left-drag ........ move her
  Click ............ boop: hop, bubblegum, +EXP (every 10 = level up)
  Double-click ..... next image in images/
  Boop 10x fast .... insert the LV.999 cartridge: godmode for a short while
  Scroll ........... resize
  Right-click ...... menu

She also talks (speech bubbles), reacts to your system (CPU load and heat,
GPU, RAM, battery, Wi-Fi, USB drives, finished downloads) with chiptune sound
effects from ./sounds, and gets sleepy late at night.

Drop any transparent PNG / GIF / WebP into ./images to add more looks.
"""
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil
from PyQt6.QtCore import (QFileSystemWatcher, QPointF, QProcess, QRect, QRectF,
                          QSize, Qt, QTimer, QUrl)
from PyQt6.QtGui import (QAction, QColor, QCursor, QDesktopServices, QFont,
                         QFontMetrics, QGuiApplication, QIcon, QImage,
                         QLinearGradient, QMovie, QPainter, QPainterPath,
                         QPen, QPixmap, QPolygonF, QRadialGradient)
from PyQt6.QtWidgets import (QApplication, QFileDialog, QMenu,
                             QSystemTrayIcon, QWidget)

HERE = Path(__file__).resolve().parent
IMG_DIR = HERE / "images"
CFG_PATH = HERE / "config.json"
SOUND_DIR = HERE / "sounds"
PLAYER = shutil.which("pw-play") or shutil.which("paplay") or shutil.which("aplay")
DOWNLOADS = Path.home() / "Downloads"
STATIC_EXTS = {".png", ".jpg", ".jpeg"}
ANIM_EXTS = {".gif", ".webp", ".apng"}
PARTIAL_EXTS = {".part", ".crdownload", ".download", ".tmp", ".partial", ".opdownload"}

PAD = 60  # room around her for bobbing, hops and particles
VIOLET, CYAN, PINK, BLUE = QColor("#b48cff"), QColor("#5ef2ff"), QColor("#ff6bd6"), QColor("#8fa8ff")
PALETTE = [VIOLET, CYAN, PINK, BLUE]
GLYPHS = list("01") * 4 + list("ABCDEF<>/{}#$")
EXP_PER_LEVEL = 10
AFK_SECONDS = 300  # mouse untouched this long -> she comments on you being AFK

# Where the bubblegum sits, as a fraction of the image (x, y). Images not listed
# here just hop when clicked.
GUM_POS = {"silverwolfchibi.png": (0.255, 0.625)}

# SW999 / LV.999 transformation. Full-size art for her godmode form goes in
# forms/ (made by tools/make_sw999_form.py from a reference shot; git-ignored).
# Without it she stays chibi and just gets the godmode effects.
FORM_DIR = HERE / "forms"
GOLD = QColor("#ffd36b")
SW999_COLORS = [CYAN, PINK, QColor("#ffffff"), VIOLET]  # her cyan <-> pink gradient
CUBE_COLORS = [QColor("#ffe066"), PINK, CYAN, QColor("#c9b6ff")]  # the cubes in her cutscene
FORM_EXTRA = 0.7  # the full-size form is this many PADs taller than the chibi
# seconds per phase ("active" uses the sw999_seconds setting)
PHASE_T = {"cart": 0.9, "slot": 0.3, "digital": 1.4, "derez": 1.0, "insert": 0.9, "settle": 0.6,
           "visor": 1.1, "active": 7.0, "godoff": 1.0, "unsettle": 0.5, "eject": 0.7, "rerez": 0.9}
# LV.999 chibi look: her official chat stickers in forms/sw999_chibi/ (01-04, git-ignored).
#   01 gum + handheld (default)   02 pointing (booped)
#   03 star shades, arms crossed (godmode)   04 giant pixel-shades bubble (godmode trigger)
CHIBI_META = dict(back=(0.5, 0.62), gauntlet=(0.48, 0.80), hand=(0.48, 0.80))
STK_IDLE, STK_POINT, STK_GOD, STK_BUBBLE = 0, 1, 2, 3
INSERT_HIT = 0.45  # point in the insert phase where the cartridge locks into her gauntlet
BOOM_COLORS = [QColor("#ffb020"), QColor("#ff6a00"), QColor("#ffe066"), PINK, QColor("#ffffff")]
# Where things are on each chibi image, as fractions of the image (x, y):
#   slot = top of her handheld, screen = its screen, back = wing root.
FORM_ANCHORS = {"silverwolfchibi.png": dict(slot=(0.17, 0.685), screen=(0.165, 0.73), back=(0.42, 0.56))}

DEFAULTS = dict(height=300, opacity=1.0, wander=False, glitch=True,
                particles=True, click_through=False, mirror=False,
                speech=True, reactions=True, sounds=True, sleepy_hours=[0, 6],
                exp=0, level=1, sw999_seconds=30, sw999_auto=True, sw999_play=False, sw999_style="chibi",
                image_index=0, x=None, y=None)

# ------------------------------------------------------------------ lines
LINES = {
    "idle": [
        "Booting fun.exe... still loading.",
        "This desktop's security is cute. I'm already in.",
        "Want me to speedrun your to-do list?",
        "Reality is just a game with bad UI.",
        "I patched your boredom. You're welcome.",
        "AFK? I'll guard the loot.",
        "Your files are safe. Mostly. Probably.",
        "New high score: staring at your screen.",
        "If this were a game I'd have skipped the tutorial.",
        "Ping me if something needs hacking.",
        "Side quest idea: drink some water.",
        "Pretty sure this OS has an exploit. Let me check...",
        "Bored. Entertain me, player one.",
        "Don't mind me. Just watching your packets.",
        "Gum's running low. Send supplies.",
    ],
    "morning": ["Morning. Player one has joined.", "New day, new save file.",
                "Good morning. Coffee first, hacking second."],
    "afternoon": ["Afternoon grind? Let's go.", "Halfway through the day. Checkpoint reached."],
    "evening": ["Evening. Prime gaming hours.", "Sun's down. Monitors up."],
    "night": ["It's {time}. Even hackers sleep... sometimes.", "Zz... ten more minutes...",
              "Why are we still up? ...not complaining.", "Night mode: on. Brain: off."],
    "boop": ["Hey!", "Hands off the controller.", "I'm in a boss fight here.",
             "Poke me one more time...", "What? I'm busy.", "Combo x{combo}!",
             "Stop. ...okay, one more.", "That tickles the firewall."],
    "sleep_boop": ["Mm... five more minutes.", "Huh? I wasn't asleep.", "...zz... what?"],
    "drag": ["Moving servers?", "Whee—", "Careful, I bruise like a bad patch."],
    "levelup": ["LEVEL UP! Lv.{level} unlocked.", "Lv.{level}! Grinding pays off.",
                "Lv.{level}. Don't let it go to your head. Mine, I mean."],
    "cpu_high": ["Your CPU is lagging. Boring.", "Whoa, who's mining on my machine?",
                 "Fans going brrr. Close something?", "CPU at {cpu}%. Is that a boss fight?"],
    "cpu_calm": ["Back to 60 fps. Nice.", "Lag's gone. Much better."],
    "ram_high": ["RAM at {ram}%. Inventory management, please.", "Memory's almost full. Drop some loot?"],
    "battery_low": ["Battery {bat}%. Plug in before we lose progress.", "{bat}% battery. Don't make me rage quit."],
    "battery_critical": ["{bat}%!! Charger. Now.", "We're about to lose the save. {bat}% left!"],
    "charging": ["Charging. Respawn protection active.", "Plugged in. HP regenerating."],
    "download": ["Loot acquired: {name}", "Download complete: {name}. +50 EXP.",
                 "Got it. {name} is in your inventory."],
    "cpu_temp": ["CPU at {temp}°C. Who set the server room on fire?",
                 "{temp}°C... my gum is melting.", "Overheat warning: {temp}°C. Cooldown phase, please."],
    "gpu_busy": ["GPU at {gpu}%. Booting a game without me?", "Graphics card's awake. Boss fight?",
                 "RTX goes brrr. {gpu}% load."],
    "gpu_hot": ["GPU at {temp}°C. That's a lava level.", "{temp}°C on the GPU. Ease up, speedrunner."],
    "net_down": ["Connection lost. We're offline, player one.", "Disconnected. No server, no loot.",
                 "Network's gone. Did someone trip on the cable?"],
    "net_up": ["Back online. Reconnected to the server.", "Link restored. Ping me."],
    "drive": ["New drive detected: {name}. Let's see what's inside.", "USB loot: {name}. Plugged in.",
              "{name} mounted. Treasure chest opened."],
    "wake": ["Back online. Did you put me in sleep mode?", "Rebooted. Where were we?"],
    "quit": ["Logging off. Don't touch my save.", "Shutting down... for now."],
    "afk": ["AFK? I'll guard the loot.", "Hello? Player one? ...Fine, I'll idle too."],
    "levelup_big": ["Lv.{level}! Milestone unlocked."],
    "download_big": ["Big download: {name}. That's a lot of loot."],
    # LV.999 moments. tools/make_sw999_lines.py swaps in her real voice lines
    # (kept locally in forms/sw999_lines.json) and adds some to the moments above.
    "sw999_first": ["First time seeing my final form? Enjoy it."],
    "sw999_eject_early": ["Already? I was just getting started."],
    "sw999_hello": ["LV.999, loaded. Let's play.", "Final form, online. Try to keep up."],
    "sw999_idle": ["Max level and nothing to fight. Boring.", "This save file is mine now.",
                   "Want me to one-shot your inbox?", "Boop me a few times. I dare you."],
    "sw999_godoff": ["GG.", "Too easy."],
    "sw999_on": ["Godmode: on. Try to keep up.", "Cartridge loaded. This save file is mine now.",
                 "LV.999. Don't blink.", "Player two has entered the game. ...She's also me."],
    "sw999_boop": ["Godmode. Your clicks deal 0 damage.", "Access denied.", "Input ignored. I'm busy being OP."],
    "sw999_off": ["Ejecting. Elio can hold onto that.", "Godmode off. Back to Lv.{level}.",
                  "That's enough. She was getting too comfy in there."],
}

# which sound each line plays (default: a short "speak" blip)
SOUND_FOR = {
    "levelup": "levelup", "download": "loot", "drive": "loot",
    "battery_low": "warn", "battery_critical": "warn", "cpu_temp": "warn", "gpu_hot": "warn",
    "ram_high": "warn", "cpu_high": "glitch", "gpu_busy": "glitch",
    "charging": "online", "net_up": "online", "net_down": "offline",
    "wake": "online", "quit": "offline", "levelup_big": "levelup", "download_big": "loot",
    "sw999_on": "speak", "sw999_off": "speak",
}
# sounds still allowed during sleepy hours (idle chatter blips stay quiet)
NIGHT_SOUNDS = {"warn", "offline", "boop", "pop", "levelup", "loot",  # you clicked or it matters
                "cart", "transform", "godmode", "revert", "eject"}


def load_local_lines():
    """Her real LV.999 voice lines, if tools/make_sw999_lines.py has made them."""
    try:
        extra = json.loads((HERE / "forms" / "sw999_lines.json").read_text())
    except Exception:
        return
    def esc(lines):
        return [str(x).replace("{", "{{").replace("}", "}}") for x in lines if x]
    if "add" in extra or "replace" in extra:
        for key, lines in extra.get("replace", {}).items():
            if lines:
                LINES[key] = esc(lines)
        for key, lines in extra.get("add", {}).items():
            pool = LINES.setdefault(key, [])
            pool += [x for x in esc(lines) if x not in pool]
    else:  # older flat file: everything replaces
        for key, lines in extra.items():
            if isinstance(lines, list) and lines:
                LINES[key] = esc(lines)


def load_cfg():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CFG_PATH.read_text()))
    except Exception:
        pass
    return cfg


def tinted(pix: QPixmap, color: QColor) -> QPixmap:
    out = QPixmap(pix.size())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, pix)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), color)
    p.end()
    return out


# ------------------------------------------------------------------ speech bubble
class Bubble(QWidget):
    MAX_W = 260
    WIDE_W = 400  # long stories get a wider bubble instead of a very tall one

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool
                            | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.font = QFont("Source Code Pro")
        self.font.setPixelSize(13)
        self.font.setBold(True)
        self.tag_font = QFont("Source Code Pro")
        self.tag_font.setPixelSize(9)
        self.text = ""
        self.max_w = self.MAX_W
        self.start = 0.0
        self.until = 0.0
        self.alpha = 0.0
        self.text_rect = QRect()

    def say(self, text, now):
        self.text = text
        fm = QFontMetrics(self.font)
        self.max_w = self.WIDE_W if len(text) > 140 else self.MAX_W
        r = fm.boundingRect(QRect(0, 0, self.max_w, 1000),
                            Qt.TextFlag.TextWordWrap, text)
        self.text_rect = QRect(14, 22, r.width() + 2, r.height())
        self.setFixedSize(max(110, r.width() + 30), r.height() + 48)
        self.start = now
        self.until = now + 2.5 + len(text) * 0.06
        self.alpha = 1.0
        self.show()

    def busy(self, now):
        return self.isVisible() and now < self.until

    def tick(self, now):
        if not self.isVisible():
            return
        if now > self.until:
            self.alpha -= 0.06
            if self.alpha <= 0:
                self.hide()
                return
        self.update()

    def paintEvent(self, _):
        now = time.monotonic()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(max(0.0, min(1.0, self.alpha)))
        w, h = self.width(), self.height()
        body = QRectF(2, 2, w - 4, h - 16)
        path = QPainterPath()
        path.addRoundedRect(body, 10, 10)
        tail = QPainterPath()
        tx = w / 2
        tail.moveTo(tx - 9, body.bottom() - 1)
        tail.lineTo(tx + 4, h - 2)
        tail.lineTo(tx + 9, body.bottom() - 1)
        tail.closeSubpath()
        path = path.united(tail)
        p.fillPath(path, QColor(14, 10, 26, 230))
        p.setPen(QPen(VIOLET, 2))
        p.drawPath(path)
        # little scanline accent
        p.setPen(QPen(QColor(94, 242, 255, 60), 1))
        for y in range(int(body.top()) + 6, int(body.bottom()) - 4, 4):
            p.drawLine(int(body.left()) + 6, y, int(body.left()) + 10, y)
        # header tag
        p.setFont(self.tag_font)
        p.setPen(CYAN)
        p.drawText(QPointF(14, 15), "SW://")
        # typewriter text
        n = int((now - self.start) * 45)
        shown = self.text[:n]
        p.setFont(self.font)
        p.setPen(QColor("#e8e6ff"))
        p.drawText(self.text_rect, Qt.TextFlag.TextWordWrap, shown)
        if n < len(self.text) and int(now * 6) % 2 == 0:
            fm = QFontMetrics(self.font)
            p.fillRect(QRectF(self.text_rect.left() + fm.horizontalAdvance(shown.split("\n")[-1]) % self.max_w,
                              self.text_rect.top() + 2, 7, fm.height() - 4), PINK)
        p.end()


# ------------------------------------------------------------------ godmode effects layer
class FxLayer(QWidget):
    """Transparent, click-through window over the whole screen. In godmode her
    lasers, sword, light trail and YOU WIN don't fit in her own small window."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool
                            | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.owner.paint_fx(p, QPointF(self.pos()))
        p.end()


# ------------------------------------------------------------------ companion
class Companion(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.setWindowTitle("Silver Wolf")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(self.cfg["opacity"])

        self.movie = None
        self.static = None
        self.scaled = None
        self.cur_file = None
        self.img_w, self.img_h = 260, 300
        self.ground_x = 0.5  # where her feet are, as a fraction of image width
        self.tint_cache = {}

        self.t = 0.0
        self.last = time.monotonic()
        self.jump = 0.0
        self.jump_v = 0.0
        self.particles = []
        self.floaters = []  # floating texts (+1 EXP, POP!, LEVEL UP)
        self.spawn_acc = 0.0
        self.glitch_until = 0.0
        self.next_glitch = 2.0
        self.gum_t = None  # time the current gum bubble started

        # LV.999 transformation (see transform())
        self.form_phase = None
        self.form_t0 = 0.0
        self.form_static = self.form_movie = self.form_scaled = None
        self.form_bare = self.form_bare_scaled = self.form_visor = self.form_visor_scaled = None
        self.form_meta = {}
        self.form_flag = False
        self.form_src_size = QSize(1, 1)
        # godmode play
        self.fxl = None
        self.fx = []
        self.trail = []
        self.fly = None
        self.fly_tilt = 0.0
        self.home = None
        self.won = False
        self.next_act = 0.0
        self.last_act = None
        self.form_cache = {}
        self.block_cache = {}
        self.idle_src, self.idle_frames, self.idle_meta, self.idle_off = [], [], {}, (0, 0)
        self.idle_h = 1
        self.anim_t0 = 0.0
        self.lv_until = 0.0
        self.lv_pause = None
        self.auto_god = None
        self.next_lv_line = 0.0
        self.lv_boops = []
        self.stickers_src, self.stickers = [], []
        self.sticker_cur = self.sticker_prev = STK_IDLE
        self.sticker_t = -9.0
        self.sticker_until = 0.0
        self.next_point = 0.0

        self.drag_off = None
        self.drag_moved = False
        self.press_global = None
        self.combo = 0
        self.last_boop = 0.0

        self.wander_target = None
        self.wander_pause = 1.0
        self.fpos = None

        # speech + reactions
        self.bubble = Bubble()
        self.was_sleepy = self.is_sleepy()
        self.cursor_pos, self.cursor_t, self.afk_said = QCursor.pos(), time.monotonic(), False
        self.quitting = False
        self.ejected_early = False
        self.next_idle = time.monotonic() + random.uniform(60, 150)
        self.cooldown = {}
        self.sys_acc = 0.0
        self.cpu_hot = 0
        self.cpu_was_high = False
        self.cpu_cool = 0
        self.last_plugged = None
        self.sound_last = {}
        self.cpu_temp_hot = 0
        self.gpu_busy_n = 0
        self.gpu_proc = None
        self.gpu_acc = 0.0
        self.net_up = self.network_up()
        self.net_flip = 0
        self.drives = self.list_drives()
        psutil.cpu_percent(None)

        self.dl_known = self.list_downloads()
        self.dl_watch = None
        if DOWNLOADS.is_dir():
            self.dl_watch = QFileSystemWatcher([str(DOWNLOADS)], self)
            self.dl_watch.directoryChanged.connect(self.on_downloads_changed)

        self.load_images()
        self.restore_position()

        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self)
            self.tray.setToolTip("Silver Wolf")
            self.update_tray_icon()
            self.tray.activated.connect(self.on_tray)
            self.tray.show()

        if self.cfg["click_through"]:
            self.set_click_through(True, show=False)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

        QTimer.singleShot(2500, self.greet)

    # ---------- images ----------
    def image_files(self):
        IMG_DIR.mkdir(exist_ok=True)
        return sorted(f for f in IMG_DIR.iterdir()
                      if f.suffix.lower() in STATIC_EXTS | ANIM_EXTS)

    def load_images(self, forms=True):
        """Load her current look. forms=True also (re)loads the LV.999 art,
        which is slow (97 animation frames), so only at startup / Reload."""
        files = self.image_files()
        if self.movie:
            self.movie.stop()
        self.movie = self.static = self.scaled = self.cur_file = None
        self.tint_cache.clear()
        if not files:
            self.img_w, self.img_h = 260, 300
            self.apply_size()
            return
        idx = self.cfg["image_index"] % len(files)
        self.cfg["image_index"] = idx
        f = self.cur_file = files[idx]
        if f.suffix.lower() in ANIM_EXTS:
            m = QMovie(str(f))
            m.setCacheMode(QMovie.CacheMode.CacheAll)
            if m.isValid() and m.frameCount() != 1:
                m.jumpToFrame(0)
                self.movie = m
                self._src_size = m.currentImage().size()
            else:
                self.static = QPixmap(str(f))
        else:
            self.static = QPixmap(str(f))
        if self.static is not None:
            self._src_size = self.static.size()
        src = self.static.toImage() if self.static is not None else self.movie.currentImage()
        self.ground_x = self.find_ground_x(src)
        if forms:
            self.load_form_image()
        self.apply_size()

    @staticmethod
    def find_ground_x(img):
        """Horizontal centre of the opaque pixels in the bottom 15% of the image,
        so her shadow sits under her feet instead of under the image centre."""
        if img.isNull():
            return 0.5
        small = img.scaledToWidth(120).convertToFormat(img.Format.Format_ARGB32)
        w, h = small.width(), small.height()
        xs = [x for y in range(int(h * 0.85), h) for x in range(w)
              if small.pixelColor(x, y).alpha() > 20]
        return (sum(xs) / len(xs) + 0.5) / w if xs else 0.5

    def load_form_image(self):
        """Full-size LV.999 art (made by tools/make_sw999_form.py):
        forms/sw999.png, plus optional sw999_novisor.png, sw999_visor.png and
        sw999.json so her visor can slide down and become the godmode shades."""
        if self.form_movie:
            self.form_movie.stop()
        self.form_static = self.form_movie = self.form_scaled = None
        self.form_bare = self.form_bare_scaled = self.form_visor = self.form_visor_scaled = None
        self.form_meta = {}
        self.idle_src, self.idle_frames = [], []
        self.stickers_src, self.stickers = [], []
        self.form_cache.clear()
        self.block_cache.clear()
        if not FORM_DIR.is_dir():
            return
        chibi = FORM_DIR / "sw999_chibi"
        if chibi.is_dir():
            files = sorted(p for p in chibi.iterdir() if p.suffix.lower() in STATIC_EXTS | {".webp"})
            self.stickers_src = [px for px in (QPixmap(str(p)) for p in files) if not px.isNull()]
        for f in sorted(FORM_DIR.iterdir()):
            ext = f.suffix.lower()
            if f.stem.lower() != "sw999" or ext not in STATIC_EXTS | ANIM_EXTS:
                continue
            if ext in ANIM_EXTS:
                m = QMovie(str(f))
                m.setCacheMode(QMovie.CacheMode.CacheAll)
                if m.isValid() and m.frameCount() != 1:
                    m.jumpToFrame(0)
                    self.form_movie = m
                    self.form_src_size = m.currentImage().size()
                    break
            pix = QPixmap(str(f))
            if not pix.isNull():
                self.form_static = pix
                self.form_src_size = pix.size()
                break
        if not (self.form_movie or self.form_static):
            return
        bare, visor = QPixmap(str(FORM_DIR / "sw999_novisor.png")), QPixmap(str(FORM_DIR / "sw999_visor.png"))
        try:
            self.form_meta = json.loads((FORM_DIR / "sw999.json").read_text())
        except Exception:
            self.form_meta = {}
        if not bare.isNull() and not visor.isNull() and "visor" in self.form_meta and "eyes" in self.form_meta:
            self.form_bare, self.form_visor = bare, visor
        # her animated idle (tools/make_sw999_idle.py)
        try:
            self.idle_meta = json.loads((FORM_DIR / "sw999_idle.json").read_text())
            files = sorted((FORM_DIR / "sw999_idle").glob("*.png"))
            self.idle_src = [px for px in (QPixmap(str(p)) for p in files) if not px.isNull()]
        except Exception:
            self.idle_meta, self.idle_src = {}, []

    def scale_form_image(self):
        self.stickers = []
        if self.stickers_src:  # chibi stickers: a little bigger than the everyday chibi
            sz = round(self.img_h * 1.05)
            self.stickers = [px.scaled(sz, sz, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation) for px in self.stickers_src]
        if not (self.form_movie or self.form_static):
            return
        sw, sh = max(1, self.form_src_size.width()), max(1, self.form_src_size.height())
        fh = self.img_h + int(FORM_EXTRA * PAD)  # she's taller than the chibi
        fw = round(sw * fh / sh)
        max_w = self.img_w + 2 * PAD - 20  # must fit in the window
        if fw > max_w:
            fh, fw = round(fh * max_w / fw), max_w
        smooth = Qt.TransformationMode.SmoothTransformation
        ignore = Qt.AspectRatioMode.IgnoreAspectRatio
        if self.form_movie:
            self.form_movie.setScaledSize(QSize(fw, fh))
            if self.form_phase:
                self.form_movie.start()
        else:
            self.form_scaled = self.form_static.scaled(fw, fh, ignore, smooth)
        if self.form_bare is not None:
            self.form_bare_scaled = self.form_bare.scaled(fw, fh, ignore, smooth)
            vx, vy, vw, vh = self.form_meta["visor"]
            self.form_visor_scaled = self.form_visor.scaled(max(1, round(vw * fw)), max(1, round(vh * fh)),
                                                            ignore, smooth)
        self.idle_frames = []  # rescaled on first use (see idle_frame), it's 97 frames
        self.idle_h = fh

    def build_idle_frames(self):
        """Scale her idle animation so her body matches the still art, feet on the same spot."""
        if not self.idle_src or "body" not in self.idle_meta:
            return
        W, H = self.idle_src[0].width(), self.idle_src[0].height()
        bx, by, bw, bh = self.idle_meta["body"]
        s = self.idle_h / (bh * H)
        sw_, sh_ = max(1, round(W * s)), max(1, round(H * s))
        self.idle_frames = [px.scaled(sw_, sh_, Qt.AspectRatioMode.IgnoreAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation) for px in self.idle_src]
        self.idle_off = (self.img_w / 2 - (bx + bw / 2) * W * s, self.img_h - (by + bh) * H * s)

    def apply_size(self):
        h = max(80, min(1200, int(self.cfg["height"])))
        self.cfg["height"] = h
        if self.movie or self.static:
            sw, sh = self._src_size.width(), self._src_size.height()
            self.img_h = h
            self.img_w = max(1, round(sw * h / max(1, sh)))
            if self.movie:
                self.movie.setScaledSize(QSize(self.img_w, self.img_h))
                self.movie.start()
            else:
                self.scaled = self.static.scaled(
                    self.img_w, self.img_h, Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
        self.tint_cache.clear()
        self.form_cache.clear()
        self.block_cache.clear()
        self.scale_form_image()
        old_center = self.geometry().center() if self.isVisible() else None
        self.setFixedSize(self.img_w + 2 * PAD, self.img_h + 2 * PAD)
        if old_center is not None:
            self.move(old_center.x() - self.width() // 2,
                      old_center.y() - self.height() // 2)
            self.fpos = None
        self.update_tray_icon()

    def frame(self):
        if self.movie:
            return self.movie.currentPixmap()
        return self.scaled

    def update_tray_icon(self):
        if getattr(self, "tray", None) is None:
            return
        pix = self.frame()
        if pix is None or pix.isNull():
            pix = QPixmap(64, 64)
            pix.fill(VIOLET)
        self.tray.setIcon(QIcon(pix))

    def get_tint(self, pix, color):
        key = (pix.cacheKey(), color.rgb())
        if key not in self.tint_cache:
            if len(self.tint_cache) > 64:
                self.tint_cache.clear()
            self.tint_cache[key] = tinted(pix, color)
        return self.tint_cache[key]

    # ---------- position ----------
    def screen_rect(self):
        scr = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        return scr.availableGeometry()

    def restore_position(self):
        scr = QGuiApplication.primaryScreen().availableGeometry()
        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is None or y is None:
            x = scr.right() - self.width() - 40
            y = scr.bottom() - self.height() - 20
        on_screen = any(s.availableGeometry().intersects(
            self.frameGeometry().translated(x - self.x(), y - self.y()))
            for s in QGuiApplication.screens())
        if not on_screen:
            x, y = scr.right() - self.width() - 40, scr.bottom() - self.height() - 20
        self.move(int(x), int(y))

    def save(self):
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        try:
            CFG_PATH.write_text(json.dumps(self.cfg, indent=2))
        except Exception as e:
            print("could not save config:", e, file=sys.stderr)

    # ---------- speech ----------
    def is_sleepy(self):
        a, b = self.cfg.get("sleepy_hours", [0, 6])
        h = datetime.now().hour
        return a <= h < b if a <= b else (h >= a or h < b)

    def say(self, key, force=False, cooldown=0, **fmt):
        """Show a random line from LINES[key]. Returns True if shown."""
        if not self.cfg["speech"] or not self.isVisible():
            return False
        now = time.monotonic()
        if cooldown and now < self.cooldown.get(key, 0):
            return False
        if not force and self.bubble.busy(now):
            return False
        fmt.setdefault("time", datetime.now().strftime("%H:%M"))
        fmt.setdefault("level", self.cfg["level"])
        fmt.setdefault("combo", self.combo)
        try:
            text = random.choice(LINES[key]).format(**fmt)
        except (KeyError, IndexError):
            return False
        self.cooldown[key] = now + cooldown
        self.bubble.say(text, now)
        self.play(SOUND_FOR.get(key, "speak"))
        self.place_bubble()
        return True

    def place_bubble(self):
        if not self.bubble.isVisible():
            return
        r = self.screen_rect()
        bx = self.x() + self.width() // 2 - self.bubble.width() // 2
        by = self.y() + PAD - self.bubble.height() + 8 + int(self.jump)
        bx = max(r.left(), min(bx, r.right() - self.bubble.width()))
        by = max(r.top(), by)
        self.bubble.move(bx, by)

    def play(self, name):
        """Fire-and-forget a sound from ./sounds (non-blocking)."""
        if not self.cfg.get("sounds") or not PLAYER:
            return
        if self.is_sleepy() and name not in NIGHT_SOUNDS:
            return
        now = time.monotonic()
        if now - self.sound_last.get(name, 0) < 0.08:
            return
        self.sound_last[name] = now
        f = SOUND_DIR / f"{name}.wav"
        if f.exists():
            try:
                subprocess.Popen([PLAYER, str(f)], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError:
                pass

    def greet(self):
        if self.is_sleepy():
            self.say("night")
            return
        h = datetime.now().hour
        self.say("morning" if h < 12 else "afternoon" if h < 18 else "evening")

    # ---------- system reactions ----------
    def check_presence(self):
        """Morning after her sleepy hours -> wake line; mouse untouched 5 min -> AFK line."""
        sleepy = self.is_sleepy()
        if self.was_sleepy and not sleepy:
            self.say("wake", force=True)
        self.was_sleepy = sleepy
        pos = QCursor.pos()
        now = time.monotonic()
        if pos != self.cursor_pos:
            self.cursor_pos, self.cursor_t, self.afk_said = pos, now, False
        elif not self.afk_said and not sleepy and now - self.cursor_t > AFK_SECONDS:
            self.afk_said = self.say("afk")  # if she was mid-sentence, try again next check

    def check_system(self):
        self.check_presence()
        if not self.cfg["reactions"]:
            return
        cpu = psutil.cpu_percent(None)
        ram = psutil.virtual_memory().percent
        if cpu > 85:
            self.cpu_hot += 1
            self.cpu_cool = 0
        else:
            self.cpu_hot = 0
            self.cpu_cool = self.cpu_cool + 1 if cpu < 35 else 0
        if self.cpu_hot >= 4:  # ~12 s of heavy load
            if self.say("cpu_high", cooldown=300, cpu=round(cpu)):
                self.cpu_was_high = True
                self.start_glitch(0.3)
            self.cpu_hot = 0
        if self.cpu_was_high and self.cpu_cool >= 4:
            self.say("cpu_calm", cooldown=120)
            self.cpu_was_high = False
        if ram > 88:
            self.say("ram_high", cooldown=600, ram=round(ram))
        try:
            bat = psutil.sensors_battery()
        except Exception:
            bat = None
        if bat is not None:
            pct = round(bat.percent)
            if self.last_plugged is False and bat.power_plugged:
                self.say("charging", force=True, cooldown=60)
            elif not bat.power_plugged:
                if pct <= 10:
                    self.say("battery_critical", force=True, cooldown=180, bat=pct)
                elif pct <= 20:
                    self.say("battery_low", cooldown=900, bat=pct)
            self.last_plugged = bat.power_plugged
        self.check_cpu_temp()
        self.check_network()
        self.check_drives()

    def check_cpu_temp(self):
        try:
            temps = psutil.sensors_temperatures()
        except Exception:
            return
        cur = [t.current for t in temps.get("k10temp", []) + temps.get("coretemp", [])]
        if not cur:
            return
        t = max(cur)
        self.cpu_temp_hot = self.cpu_temp_hot + 1 if t >= 92 else 0
        if self.cpu_temp_hot >= 3:  # ~9 s above 92 °C
            if self.say("cpu_temp", cooldown=600, temp=round(t)):
                self.start_glitch(0.3)
            self.cpu_temp_hot = 0

    def check_gpu(self):
        """Ask nvidia-smi in the background; on_gpu() handles the answer."""
        if not self.cfg["reactions"] or not shutil.which("nvidia-smi"):
            return
        if self.gpu_proc and self.gpu_proc.state() != QProcess.ProcessState.NotRunning:
            return
        self.gpu_proc = QProcess(self)
        self.gpu_proc.finished.connect(self.on_gpu)
        self.gpu_proc.start("nvidia-smi", ["--query-gpu=utilization.gpu,temperature.gpu",
                                           "--format=csv,noheader,nounits"])

    def on_gpu(self, *_):
        try:
            out = bytes(self.gpu_proc.readAllStandardOutput()).decode().strip().splitlines()[0]
            util, temp = (int(float(x)) for x in out.split(","))
        except Exception:
            return
        if temp >= 85:
            self.say("gpu_hot", cooldown=600, temp=temp)
        self.gpu_busy_n = self.gpu_busy_n + 1 if util >= 70 else 0
        if self.gpu_busy_n >= 3:  # ~30 s of heavy GPU use
            if self.say("gpu_busy", cooldown=1800, gpu=util):
                self.start_glitch(0.35)
            self.gpu_busy_n = 0

    @staticmethod
    def network_up():
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
        except Exception:
            return True
        for name, st in stats.items():
            if name == "lo" or not st.isup or name.startswith(("docker", "veth", "br-", "virbr")):
                continue
            if any(a.family == 2 and not a.address.startswith("127.") for a in addrs.get(name, [])):
                return True
        return False

    def check_network(self):
        up = self.network_up()
        if up == self.net_up:
            self.net_flip = 0
            return
        self.net_flip += 1
        if self.net_flip >= 2:  # must hold for two checks (~6 s) to avoid flapping
            self.net_up = up
            self.net_flip = 0
            if self.say("net_up" if up else "net_down", force=not up, cooldown=30):
                self.start_glitch(0.25)

    @staticmethod
    def list_drives():
        try:
            return {p.mountpoint for p in psutil.disk_partitions()
                    if p.mountpoint.startswith(("/media/", "/run/media/", "/mnt/"))}
        except Exception:
            return set()

    def check_drives(self):
        now = self.list_drives()
        for mp in sorted(now - self.drives):
            if self.say("drive", force=True, cooldown=5, name=os.path.basename(mp) or mp):
                self.celebrate("+LOOT", PINK)
        self.drives = now

    def list_downloads(self):
        try:
            return {p.name for p in DOWNLOADS.iterdir()}
        except Exception:
            return set()

    def on_downloads_changed(self, _path):
        now_names = self.list_downloads()
        new = [n for n in now_names - self.dl_known
               if Path(n).suffix.lower() not in PARTIAL_EXTS and not n.startswith(".")]
        self.dl_known = now_names
        for n in new:
            QTimer.singleShot(1500, lambda n=n: self.download_done(n))

    def download_done(self, name):
        f = DOWNLOADS / name
        if not f.exists() or not self.cfg["reactions"]:
            return
        short = name if len(name) <= 28 else name[:25] + "..."
        try:
            big = f.stat().st_size >= 200 * 1024 * 1024
        except OSError:
            big = False
        if self.say("download_big" if big else "download", force=True, cooldown=5, name=short):
            self.celebrate("+50 EXP", CYAN)
            self.add_exp(5)

    # ---------- animation ----------
    def tick(self):
        now = time.monotonic()
        if now - self.last > 60:  # the machine was asleep (suspend), she wakes up with it
            QTimer.singleShot(1500, lambda: self.say("wake", force=True))
        dt = min(0.05, now - self.last)
        self.last = now
        self.t += dt
        sleepy = self.is_sleepy()

        if self.jump_v or self.jump:
            self.jump_v += 1600 * dt
            self.jump += self.jump_v * dt
            if self.jump >= 0:
                self.jump = self.jump_v = 0.0

        if self.cfg["glitch"] and self.t >= self.next_glitch:
            if not sleepy:
                self.start_glitch(random.uniform(0.12, 0.35))
            self.next_glitch = self.t + random.uniform(3.5, 9.0)

        # gum: grow for 0.7s, then pop
        if self.gum_t is not None and self.t - self.gum_t > 0.7:
            self.pop_gum()

        self.update_form(dt)
        self.update_fx_layer()
        self.update_particles(dt, sleepy)
        for f in self.floaters:
            f["life"] -= dt
            f["y"] += f["vy"] * dt
        self.floaters = [f for f in self.floaters if f["life"] > 0]

        if self.cfg["wander"] and self.drag_off is None and not sleepy and not self.form_phase:
            self.wander(dt)

        self.sys_acc += dt
        if self.sys_acc >= 3.0:
            self.sys_acc = 0.0
            self.check_system()
        self.gpu_acc += dt
        if self.gpu_acc >= 10.0:
            self.gpu_acc = 0.0
            self.check_gpu()

        if now >= self.next_idle and not self.form_phase:
            if (self.cfg.get("sw999_auto") and not sleepy and not self.form_phase
                    and random.random() < 0.08):
                self.transform()  # rare surprise overclock (~every 30-60 min)
            else:
                self.say("night" if sleepy else "idle")
            self.next_idle = now + random.uniform(120, 300)

        self.bubble.tick(now)
        self.place_bubble()
        self.update()

    def start_glitch(self, dur):
        self.glitch_until = max(self.glitch_until, self.t + dur)

    def spawn_particle(self, burst=False, at=None, colors=None):
        if at:
            x, y = at
        else:
            x = PAD + random.uniform(0.05, 0.95) * self.img_w
            y = PAD + random.uniform(0.3, 1.0) * self.img_h
        speed = random.uniform(40, 140) if burst else random.uniform(15, 45)
        ang = random.uniform(0, 2 * math.pi) if burst else -math.pi / 2 + random.uniform(-0.4, 0.4)
        life = random.uniform(0.8, 1.6) if at else random.uniform(1.2, 2.8)
        self.particles.append(dict(
            x=x, y=y, vx=math.cos(ang) * speed, vy=math.sin(ang) * speed,
            life=life, max=life, color=random.choice(colors or PALETTE),
            kind="pixel" if at else ("glyph" if random.random() < 0.45 else "pixel"),
            ch=random.choice(GLYPHS), size=random.choice((3, 4, 5, 6)),
            blink=random.uniform(4, 10)))

    def spawn_z(self):
        x = PAD + self.img_w * random.uniform(0.55, 0.75)
        y = PAD + self.img_h * 0.15
        self.particles.append(dict(x=x, y=y, vx=random.uniform(8, 20), vy=random.uniform(-28, -18),
                                   life=2.6, max=2.6, color=VIOLET, kind="z",
                                   ch=random.choice("zZ"), size=random.choice((12, 15, 18)), blink=2))

    def update_particles(self, dt, sleepy):
        powered = self.form_phase == "active"  # godmode: more, brighter particles
        if self.cfg["particles"]:
            self.spawn_acc += dt * (12.0 if powered else 1.5 if sleepy else 5.0)
            while self.spawn_acc >= 1 and len(self.particles) < (90 if powered else 50):
                self.spawn_acc -= 1
                if powered:
                    self.spawn_particle(colors=SW999_COLORS)
                elif sleepy and random.random() < 0.6:
                    self.spawn_z()
                else:
                    self.spawn_particle()
        alive = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vx"] *= 0.98
            if p["kind"] == "pixel" and p["max"] < 2:  # burst pixels fall a bit
                p["vy"] += 120 * dt
            alive.append(p)
        self.particles = alive

    def wander(self, dt):
        if self.fpos is None:
            self.fpos = QPointF(self.pos())
        if self.wander_pause > 0:
            self.wander_pause -= dt
            return
        r = self.screen_rect()
        if self.wander_target is None:
            self.wander_target = QPointF(
                random.uniform(r.left(), max(r.left(), r.right() - self.width())),
                random.uniform(r.top(), max(r.top(), r.bottom() - self.height())))
        d = self.wander_target - self.fpos
        dist = math.hypot(d.x(), d.y())
        if dist < 3:
            self.wander_target = None
            self.wander_pause = random.uniform(2.0, 7.0)
            return
        step = min(dist, 70 * dt)
        self.fpos += d * (step / dist)
        self.move(round(self.fpos.x()), round(self.fpos.y()))

    # ---------- gum / exp ----------
    def gum_point(self, lift):
        pos = GUM_POS.get(self.cur_file.name) if self.cur_file else None
        if not pos:
            return None
        gx, gy = pos
        if self.cfg["mirror"]:
            gx = 1 - gx
        return PAD + gx * self.img_w, PAD + gy * self.img_h + lift

    def lift(self):
        sleepy = self.is_sleepy()
        speed, amp = (0.8, 4) if sleepy else (1.7, 9)
        return math.sin(self.t * speed) * amp + self.jump

    def pop_gum(self):
        pt = self.gum_point(self.lift())
        self.gum_t = None
        if pt:
            self.play("pop")
            for _ in range(16):
                self.spawn_particle(burst=True, at=pt, colors=[PINK, QColor("#ffb3ec"), QColor("#ffffff")])
            self.floaters.append(dict(text="POP!", x=pt[0] - 18, y=pt[1] - 20, vy=-40,
                                      life=0.8, max=0.8, color=PINK, size=15))

    def celebrate(self, text, color):
        self.floaters.append(dict(text=text, x=PAD + self.img_w * 0.55, y=PAD + 10, vy=-30,
                                  life=1.4, max=1.4, color=color, size=13))
        for _ in range(10):
            self.spawn_particle(burst=True)

    def add_exp(self, n=1):
        self.cfg["exp"] += n
        leveled = False
        while self.cfg["exp"] >= EXP_PER_LEVEL:
            self.cfg["exp"] -= EXP_PER_LEVEL
            self.cfg["level"] += 1
            leveled = True
        if leveled:
            self.start_glitch(0.5)
            self.floaters.append(dict(text="LEVEL UP!", x=PAD + self.img_w / 2 - 60, y=PAD + 20,
                                      vy=-25, life=2.0, max=2.0, color=CYAN, size=20, big=True))
            for _ in range(30):
                self.spawn_particle(burst=True)
            self.say("levelup_big" if self.cfg["level"] % 10 == 0 else "levelup", force=True)
        self.save()
        return leveled

    # ---------- SW999 transformation ----------
    # LV.999 is her future self, sealed inside a game cartridge (Elio keeps it).
    #   cart     cartridge tossed in, hovers     digital  circuit-board world
    #   derez    the chibi breaks into pixels and re-forms full size
    #   insert   the cartridge slots into her gauntlet, gems light up, crystals burst
    #   settle   -> lv999: her animated idle as LV.999 (visor up on her head)
    #   godmode, her ultimate, from lv999 (auto once, or boop her 3x):
    #     visor (pulls it down into the shades) -> active (wings of light,
    #     shades) -> godoff (wings shatter) -> lv999
    #   unsettle -> eject (cartridge pops out) -> rerez (back to chibi)
    def transform(self):
        if self.form_phase or not self.isVisible():
            return
        self.form_phase, self.form_t0 = "cart", self.t
        self.form_flag = False
        self.gum_t = None
        self.jump = self.jump_v = 0.0
        self.bubble.hide()
        if self.form_movie:
            self.form_movie.start()
        self.play("cart")

    def revert(self):
        ph = self.form_phase
        if ph in ("settle", "lv999", "visor", "active"):
            self.ejected_early = self.say("sw999_eject_early", force=True)
        if ph in ("cart", "slot", "digital"):
            self.form_phase = None
            self.start_glitch(0.2)
        elif ph == "derez":
            self.set_phase("rerez")
        elif ph in ("insert", "settle", "lv999"):
            self.set_phase("unsettle")
        elif ph in ("visor", "active"):
            self.lv_until = self.t  # finish godmode, then leave
            self.lv_pause = None
            self.set_phase("godoff")
        elif ph == "godoff":
            self.lv_until = self.t
            self.lv_pause = None

    def godmode(self):
        """Her ultimate: only from her LV.999 idle."""
        if self.form_phase == "lv999" and self.can_godmode():
            self.lv_pause = self.t
            self.set_phase("visor")

    def lv999_seconds(self):
        return max(15.0, float(self.cfg.get("sw999_seconds", 30)))

    def set_phase(self, ph):
        self.form_phase, self.form_t0 = ph, self.t
        self.form_flag = False
        if ph == "digital":
            self.play("transform")  # insert click + boot jingle (cutscene version)
        elif ph == "derez":
            self.play("glitch")
            self.start_glitch(0.15)
        elif ph == "insert":
            self.play("cart")
        elif ph == "settle":
            self.next_point = self.t + 6.0
            self.lv_until = self.t + PHASE_T["settle"] + self.lv999_seconds()
            self.auto_god = self.t + PHASE_T["settle"] + 4.0  # one ultimate early on
            self.anim_t0 = self.t
            self.next_lv_line = self.t + 9.0
            if not self.cfg.get("lv999_seen"):
                self.cfg["lv999_seen"] = True
                self.save()
                self.say("sw999_first", force=True)
            else:
                self.say("sw999_hello", force=True)
        elif ph == "visor":
            self.say("sw999_on", force=True)
        elif ph == "active":
            self.floaters.append(dict(text="GODMODE", x=self.width() / 2 - 62, y=PAD - 20, vy=-14,
                                      life=2.0, max=2.0, color=PINK, size=20, big=True))
            if self.cfg.get("sw999_play"):
                self.start_godmode()
        elif ph == "godoff":
            self.play("revert")
            self.shatter_wings()
            if self.fly is not None or (self.fxl is not None and self.fxl.isVisible()):
                self.end_godmode()
        elif ph == "lv999":
            if self.lv_pause is not None:  # back from godmode, which doesn't eat LV.999 time
                self.lv_until += self.t - self.lv_pause
                self.lv_pause = None
                self.say("sw999_godoff", force=True)
        elif ph == "eject":
            self.play("eject")
        elif ph == "rerez":
            self.play("revert")
            self.start_glitch(0.2)

    def form_progress(self):
        """(phase, 0..1 progress through it)."""
        if not self.form_phase:
            return None, 0.0
        if self.form_phase == "lv999":
            span = max(0.001, self.lv_until - self.form_t0)
            return "lv999", max(0.0, min(1.0, (self.t - self.form_t0) / span))
        dur = PHASE_T[self.form_phase]
        return self.form_phase, max(0.0, min(1.0, (self.t - self.form_t0) / dur))

    def form_amount(self):
        """How far her wings of light are spread: 0..1."""
        ph, k = self.form_progress()
        if ph == "active":
            u = min(1.0, (self.t - self.form_t0) / 0.7)
            return 1 - (1 - u) ** 3
        if ph == "godoff":
            return max(0.0, 1 - k * 3)
        return 0.0

    def body_is_form(self):
        """Is the full-size LV.999 body what's on screen right now?"""
        ph, k = self.form_progress()
        return ph in ("insert", "settle", "lv999", "visor", "active", "godoff", "unsettle", "eject") \
            or (ph == "derez" and k >= 0.5) or (ph == "rerez" and k < 0.5)

    def update_sticker(self, ph, k):
        """Pick the chibi sticker for the moment, and remember when it changed."""
        if ph == "visor":
            want = STK_BUBBLE if k < 0.45 else STK_GOD
        elif ph == "active":
            want = STK_GOD
        elif ph == "godoff":
            want = STK_GOD if k < 0.3 else STK_IDLE
        elif ph == "lv999":
            if self.t >= self.next_point:  # now and then she points at you
                self.sticker_until = self.t + 2.5
                self.next_point = self.t + random.uniform(8, 14)
            want = STK_POINT if self.t < self.sticker_until else STK_IDLE
        else:
            want = STK_IDLE
        if want != self.sticker_cur:
            self.sticker_prev, self.sticker_cur, self.sticker_t = self.sticker_cur, want, self.t

    def update_form(self, dt):
        ph, k = self.form_progress()
        if not ph:
            return
        if self.chibi_mode():
            self.update_sticker(ph, k)
        if ph == "digital" or (ph == "active" and random.random() < dt * 3):
            for _ in range(int(dt * 30) + (random.random() < (dt * 30) % 1)):
                self.spawn_cube()
        if ph == "insert" and k >= INSERT_HIT and not self.form_flag:  # cartridge locks into the gauntlet
            self.form_flag = True
            self.play("transform")
            self.start_glitch(0.12)
            for _ in range(20):
                self.spawn_cube(burst=True)
        if ph == "visor" and k >= 0.45 and not self.form_flag:  # shades lock on
            self.form_flag = True
            self.play("godmode")
            if self.chibi_mode():  # the pixel-shades bubble pops
                self.play("pop")
                cx, cy = self.width() / 2, PAD + self.img_h * 0.3
                for _ in range(22):
                    self.spawn_particle(burst=True, at=(cx, cy), colors=[PINK, QColor("#ffb3ec"), CYAN, QColor("#ffffff")])
                self.floaters.append(dict(text="POP!", x=cx - 18, y=cy - 20, vy=-40, life=0.8, max=0.8, color=PINK, size=15))
            for _ in range(24):
                self.spawn_cube(burst=True)
        if ph == "lv999":
            if self.auto_god and self.t >= self.auto_god:
                self.auto_god = None
                self.godmode()
                return
            if self.t >= self.next_lv_line:
                if self.say("sw999_idle"):
                    self.next_lv_line = self.t + random.uniform(10, 18)
                else:
                    self.next_lv_line = self.t + 2
        if ph == "active" and self.fxl is not None and self.fxl.isVisible():
            self.update_godmode(dt, k)
        if k < 1:
            return
        nxt = {"cart": "slot", "slot": "digital", "digital": "derez", "derez": "settle", "insert": "settle",
               "settle": "lv999", "visor": "active", "active": "godoff", "lv999": "unsettle",
               "unsettle": "eject", "eject": "rerez"}.get(ph)
        if ph == "godoff":
            nxt = "lv999" if self.t < self.lv_until else "unsettle"
        if nxt:
            self.set_phase(nxt)
            return
        self.form_phase = None  # rerez finished
        if self.form_movie:
            self.form_movie.stop()
        if not self.ejected_early:  # don't talk over her "already?" line
            self.say("sw999_off", force=True)
        self.ejected_early = False

    def spawn_cube(self, burst=False, at=None, colors=None, speed=(60, 160)):
        """The floating yellow / pink / cyan / lavender cubes from her transformation."""
        if burst or at:
            x, y = at if at else (self.width() / 2 + random.uniform(-20, 20), PAD + self.img_h * 0.25)
            ang, sp = random.uniform(0, 2 * math.pi), random.uniform(*speed)
            vx, vy = math.cos(ang) * sp, math.sin(ang) * sp
        else:
            x, y = random.uniform(8, self.width() - 8), random.uniform(PAD * 0.5, self.height() - 10)
            vx, vy = random.uniform(-8, 8), random.uniform(-45, -15)
        life = random.uniform(0.9, 2.0)
        self.particles.append(dict(x=x, y=y, vx=vx, vy=vy, life=life, max=life, kind="cube",
                                   color=random.choice(colors or CUBE_COLORS), ch="",
                                   size=random.choice((4, 5, 6, 8)), blink=random.uniform(3, 7)))

    def local_to_window(self, lx, ly):
        m = -1 if self.cfg["mirror"] else 1
        return self.width() / 2 + m * (lx - self.img_w / 2), PAD + self.img_h / 2 + self.lift() + (ly - self.img_h / 2)

    def shatter_wings(self):
        """God Mode OFF: her wings of light break apart into pixels."""
        rx, ry = self.local_to_window(*self.wing_root())
        for _ in range(70):
            side = random.choice((-1, 1))
            a = math.radians(random.uniform(-40, 30))
            d = random.uniform(10, 150)
            x, y = rx + side * math.cos(a) * d, ry + math.sin(a) * d
            sp = random.uniform(20, 90)
            life = random.uniform(0.6, 1.4)
            self.particles.append(dict(x=x, y=y, vx=side * math.cos(a) * sp, vy=math.sin(a) * sp - 20,
                                       life=life, max=life, kind="cube", ch="", blink=random.uniform(3, 8),
                                       color=random.choice((PINK, CYAN, QColor("#ffffff"), QColor("#e6dcff"))),
                                       size=random.choice((3, 4, 5, 6))))

    # ---------- godmode: she plays around the whole screen ----------
    def start_godmode(self):
        self.home = QPointF(self.pos())
        self.fly = None
        self.trail = []
        self.fx = []
        self.won = False
        self.last_act = None
        self.next_act = self.t + 0.9
        self.fly_tilt = 0.0
        if self.fxl is None:
            self.fxl = FxLayer(self)
        scr = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        self.fxl.setGeometry(scr.geometry())
        self.fxl.show()
        self.raise_()

    def end_godmode(self):
        self.fly = None
        self.fly_tilt = 0.0
        self.save()

    def screen_box(self):
        """Where her window may go: the screen minus her own size."""
        r = self.screen_rect()
        return r.left(), r.top(), max(r.left(), r.right() - self.width()), max(r.top(), r.bottom() - self.height())

    def fly_to(self, target, dur=None):
        a = QPointF(self.pos())
        d = math.hypot(target.x() - a.x(), target.y() - a.y())
        self.fly = dict(t0=self.t, dur=dur or max(0.6, min(1.3, d / 700)), a=a, b=target)
        self.play("cart")

    def local_to_global(self, lx, ly):
        """Her local (img box) coordinates -> global screen position (ignores the small tilt)."""
        m = -1 if self.cfg["mirror"] else 1
        wx = self.width() / 2 + m * (lx - self.img_w / 2)
        wy = PAD + self.img_h / 2 + self.lift() + (ly - self.img_h / 2)
        return QPointF(self.x() + wx, self.y() + wy)

    def hand_global(self):
        if self.has_form_art() and "hand" in self.fmeta:
            return self.local_to_global(*self.form_point(*self.fmeta["hand"]))
        return self.local_to_global(*self.anchor_pt("screen", (0.5, 0.7)))

    def pick_target(self):
        """Aim at the mouse pointer if it's not right on top of her, else somewhere on screen."""
        c = QPointF(QCursor.pos())
        me = QPointF(self.geometry().center())
        if math.hypot(c.x() - me.x(), c.y() - me.y()) > 160:
            return c
        r = self.screen_rect()
        return QPointF(random.uniform(r.left() + 80, r.right() - 80), random.uniform(r.top() + 80, r.bottom() - 80))

    def update_godmode(self, dt, k):
        now = self.t
        # flying
        if self.fly:
            f = self.fly
            u = min(1.0, (now - f["t0"]) / f["dur"])
            e = u * u * (3 - 2 * u)
            pos = f["a"] + (f["b"] - f["a"]) * e
            vx = (f["b"].x() - f["a"].x()) / f["dur"]
            self.fly_tilt = max(-14.0, min(14.0, vx / 60)) * math.sin(u * math.pi)
            self.move(round(pos.x()), round(pos.y()))
            if u >= 1:
                self.fly = None
                self.fly_tilt = 0.0
                self.next_act = now + 0.35
        if self.fly:  # light trail behind her
            c = self.local_to_global(*self.wing_root())
            self.trail.append((c.x(), c.y(), now))
        # next move
        if self.fly or now < self.next_act or self.drag_off is not None:
            return
        left = (1 - k) * PHASE_T["active"]
        if not self.won and left < 3.4:
            if math.hypot(self.x() - self.home.x(), self.y() - self.home.y()) > 30:
                self.fly_to(self.home)  # head home for the finale
                self.last_act = "fly"
            else:
                self.won = True
                self.fx.append(dict(kind="win", t0=now, dur=2.4))
                self.play("win")
                self.next_act = now + 99
            return
        if self.won:
            return
        if self.last_act != "fly":
            x0, y0, x1, y1 = self.screen_box()
            for _ in range(8):  # a spot a decent distance away
                t = QPointF(random.uniform(x0, x1), random.uniform(y0, y1))
                if math.hypot(t.x() - self.x(), t.y() - self.y()) > 220:
                    break
            self.fly_to(t)
            self.last_act = "fly"
            return
        act = random.choice([a for a in ("rain", "beam", "slash") if a != getattr(self, "prev_attack", None)])
        self.prev_attack = self.last_act = act
        if act == "rain":
            target = self.pick_target()
            rng = random.Random()
            n = 16
            starts = []
            for i in range(n):
                ang = math.radians(-170 + 160 * i / (n - 1) + rng.uniform(-4, 4))  # from above, all around
                r = rng.uniform(380, 620)
                starts.append((target.x() + math.cos(ang) * r, target.y() + math.sin(ang) * r, rng.uniform(0, 0.3)))
            self.fx.append(dict(kind="rain", t0=now, dur=1.7, target=target, starts=starts))
            self.play("laser")
            self.next_act = now + 1.8
        elif act == "beam":
            self.fx.append(dict(kind="beam", t0=now, dur=1.1, target=self.pick_target()))
            self.next_act = now + 1.2
        else:
            self.fx.append(dict(kind="slash", t0=now, dur=0.9, side=random.choice((-1, 1))))
            self.next_act = now + 1.0

    def add_burst(self, at, n, colors):
        """Pixel explosion on the effects layer (positions are computed from time)."""
        rng = random.Random()
        bits = [(rng.uniform(0, 2 * math.pi), rng.uniform(80, 340), rng.choice(colors), rng.choice((5, 7, 9, 12)))
                for _ in range(n)]
        self.fx.append(dict(kind="burst", t0=self.t, dur=0.9, at=QPointF(at), bits=bits))

    def anchors(self):
        return FORM_ANCHORS.get(self.cur_file.name) if self.cur_file else None

    def chibi_mode(self):
        return self.cfg.get("sw999_style", "chibi") == "chibi" and len(self.stickers) >= 4

    def has_form_art(self):
        return self.chibi_mode() or self.form_movie is not None or self.form_scaled is not None

    @property
    def fmeta(self):
        """Anchor points for the current LV.999 look."""
        return CHIBI_META if self.chibi_mode() else self.form_meta

    def can_godmode(self):
        return self.chibi_mode() or (self.has_form_art() and self.form_bare_scaled is not None)

    def form_sprite(self, pix, bare=False):
        """The LV.999 pixmap and its top-left offset inside the img_w x img_h box.
        bare=True gives the version without the visor on her head."""
        if self.chibi_mode():
            art = self.stickers[self.sticker_cur]
            return art, (self.img_w - art.width()) / 2, self.img_h - art.height()
        if self.has_form_art():
            art = self.form_movie.currentPixmap() if self.form_movie else self.form_scaled
            if bare and self.form_bare_scaled is not None:
                art = self.form_bare_scaled
            return art, (self.img_w - art.width()) / 2, self.img_h - art.height()
        key = pix.cacheKey()
        if key not in self.form_cache:
            if len(self.form_cache) > 64:
                self.form_cache.clear()
            self.form_cache[key] = self.build_godmode_tint(pix)
        return self.form_cache[key], 0, 0

    def form_point(self, fx, fy):
        """A point given as fractions of the LV.999 art -> local coordinates."""
        art, ox, oy = self.form_sprite(self.frame())
        return ox + fx * art.width(), oy + fy * art.height()

    @staticmethod
    def build_godmode_tint(pix):
        """Without LV.999 art: her own art with a light cyan->pink wash."""
        w, h = pix.width(), pix.height()
        out = QPixmap(pix.size())
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.drawPixmap(0, 0, pix)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(94, 242, 255, 55))
        g.setColorAt(0.5, QColor(160, 120, 255, 25))
        g.setColorAt(1.0, QColor(255, 107, 214, 60))
        p.fillRect(out.rect(), g)
        for y in range(0, h, 3):
            p.fillRect(0, y, w, 1, QColor(255, 255, 255, 14))
        p.end()
        return out

    def pixel_blocks(self, pix):
        """Cut a sprite into coloured blocks for the de-rez / re-rez effect."""
        key = pix.cacheKey()
        if key in self.block_cache:
            return self.block_cache[key]
        if len(self.block_cache) > 16:
            self.block_cache.clear()
        img = pix.toImage()
        w, h = img.width(), img.height()
        b = max(3, round(self.img_h / 55))
        rng = random.Random(999)
        blocks = []
        for y in range(0, h, b):
            for x in range(0, w, b):
                c = img.pixelColor(min(w - 1, x + b // 2), min(h - 1, y + b // 2))
                if c.alpha() < 60:
                    continue
                ang = rng.uniform(0, 2 * math.pi)
                blocks.append((x, y, QColor(c), math.cos(ang), math.sin(ang),
                               rng.uniform(0.15, 0.55) * self.img_h,
                               0.25 * (1 - y / h) + rng.uniform(0, 0.15),  # top goes last
                               rng.choice(CUBE_COLORS) if rng.random() < 0.25 else None))
        self.block_cache[key] = (b, blocks)
        return b, blocks

    # ---------- painting ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        sleepy = self.is_sleepy()
        lift = self.lift()
        tilt = math.sin(self.t * (0.5 if sleepy else 0.9)) * (4 if sleepy else 2.2)
        phase, fk = self.form_progress()
        art = self.has_form_art()
        big = art and self.body_is_form()  # full-size LV.999 on screen
        if big:
            tilt *= 0.4  # she's tall; a big sway looks seasick
        if phase == "active":
            tilt += self.fly_tilt  # leans into the direction she's flying

        cx = self.width() / 2
        sy = PAD + self.img_h + 26
        # ground point under her feet (follows mirror)
        gx = 0.5 if big else (1 - self.ground_x if self.cfg["mirror"] else self.ground_x)
        fx = cx + (gx - 0.5) * self.img_w
        k = max(0.4, min(1.2, 1.0 + (lift / 80.0)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(120, 90, 200, int(70 * k)))
        sw = self.img_w * (0.3 if big else 0.45) * k
        p.drawEllipse(QPointF(fx, sy), sw / 2, 7 * k)

        if phase == "digital":
            self.paint_circuits(p, fk)

        pix = self.frame()
        if pix is None or pix.isNull():
            self.paint_placeholder(p)
        else:
            p.save()
            if sleepy and not phase:
                p.setOpacity(0.85)
            p.translate(cx, PAD + self.img_h / 2 + lift)
            p.rotate(tilt)
            if self.cfg["mirror"]:
                p.scale(-1, 1)
            p.translate(-self.img_w / 2, -self.img_h / 2)
            glitching = self.t < self.glitch_until or (
                phase == "digital" and random.random() < 0.05 + 0.3 * fk)

            amount = self.form_amount()
            if amount > 0:
                self.paint_light_wings(p, amount, lift)
            if phase == "derez" and fk >= 0.5:  # crystals burst as she re-forms (cutscene version)
                self.paint_crystal_burst(p, fk * 2 - 1)
            if phase == "insert" and fk >= INSERT_HIT:  # crystals burst as the cartridge locks in
                self.paint_crystal_burst(p, (fk - INSERT_HIT) / (1 - INSERT_HIT))

            bare = art and not self.chibi_mode() and self.form_bare_scaled is not None \
                and phase in ("visor", "active", "godoff")
            if phase == "derez":
                if fk < 0.5:
                    self.paint_blocks(p, pix, 0, 0, fk * 2, gathering=False)
                else:
                    self.paint_blocks(p, *self.form_sprite(pix), fk * 2 - 1, gathering=True)
            elif phase == "rerez":
                if fk < 0.5:
                    self.paint_blocks(p, *self.form_sprite(pix, bare), fk * 2, gathering=False)
                else:
                    self.paint_blocks(p, pix, 0, 0, fk * 2 - 1, gathering=True)
            elif self.chibi_mode() and phase in ("insert", "settle", "lv999", "visor", "active", "godoff",
                                                 "unsettle", "eject"):
                self.paint_sticker_body(p, phase, glitching)
            elif phase in ("insert", "eject"):
                self.draw_pix(p, *self.form_sprite(pix), glitching)
            elif phase in ("settle", "unsettle", "lv999", "visor", "godoff"):
                self.paint_lv999_body(p, phase, fk, pix, self.idle_frame() if art else None, glitching)
            elif phase == "active":
                form, ox, oy = self.form_sprite(pix, bare)
                self.paint_aura(p, form, ox, oy)
                self.draw_pix(p, form, ox, oy, glitching)
            else:
                self.draw_pix(p, pix, 0, 0, glitching)

            # in front of her
            if phase in ("slot", "digital") or (phase == "derez" and fk < 0.5):
                self.paint_screen_glow(p, phase, fk)
            if art and not self.chibi_mode() and (phase in ("visor", "active")
                                                  or (phase == "insert" and fk >= INSERT_HIT)):
                self.paint_gauntlet_glow(p, phase, fk)
            self.paint_cartridge(p, phase, fk)
            if bare:
                self.paint_visor_and_shades(p, phase, fk)
            p.restore()

        if phase == "digital":
            self.paint_pixel_scan(p, fk)
        elif phase == "active":
            self.paint_godmode_bar(p, fx, sy, 1 - fk)

        self.paint_gum(p, lift)
        self.paint_particles(p)
        self.paint_floaters(p)
        p.end()

    def paint_gum(self, p, lift):
        if self.gum_t is None:
            return
        pt = self.gum_point(lift)
        if not pt:
            return
        k = min(1.0, (self.t - self.gum_t) / 0.7)
        r = self.img_h * 0.035 + self.img_h * 0.07 * (k ** 1.5)
        c = QPointF(pt[0] - r * 0.15, pt[1])
        g = QRadialGradient(c.x() - r * 0.35, c.y() - r * 0.35, r * 1.3)
        g.setColorAt(0, QColor(255, 230, 248, 235))
        g.setColorAt(0.45, QColor(255, 150, 215, 215))
        g.setColorAt(1, QColor(240, 90, 180, 200))
        p.setBrush(g)
        p.setPen(QPen(QColor(200, 60, 150, 180), 1.5))
        p.drawEllipse(c, r, r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawEllipse(QPointF(c.x() - r * 0.4, c.y() - r * 0.4), r * 0.18, r * 0.12)

    def draw_pix(self, p, pix, x, y, glitch):
        p.save()
        p.translate(x, y)
        if glitch:
            self.paint_glitch(p, pix)
        else:
            p.drawPixmap(0, 0, pix)
        p.restore()

    # --- LV.999 effects (drawn in her local img_w x img_h coordinates) ---
    def anchor_pt(self, key, default):
        a = (self.anchors() or {}).get(key, default)
        return a[0] * self.img_w, a[1] * self.img_h

    def paint_aura(self, p, form, fx, fy):
        """Pulsing cyan/pink outline glow."""
        pulse = 0.12 + 0.06 * math.sin(self.t * 5)
        p.save()
        p.setOpacity(pulse)
        for i in range(8):
            a = i * math.pi / 4 + self.t * 0.8
            glow = self.get_tint(form, CYAN if i % 2 else PINK)
            p.drawPixmap(QPointF(fx + math.cos(a) * 3, fy + math.sin(a) * 3), glow)
        p.restore()

    def paint_blocks(self, p, pix, ox, oy, u, gathering):
        """De-rez: blocks fly apart (u 0->1). Gathering: they fly back together."""
        b, blocks = self.pixel_blocks(pix)
        h = self.img_h
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, c, dx, dy, dist, delay, alt in blocks:
            v = max(0.0, min(1.0, (u - delay) / 0.6))
            if gathering:
                v = 1 - v  # 1 = scattered, 0 = home
                v = v * v
            else:
                v = v ** 1.4
            off = dist * v
            col = QColor(alt) if alt is not None and 0.08 < v < 0.9 else QColor(c)
            col.setAlphaF(max(0.0, min(1.0, (1 - v) * c.alphaF() * 1.2)))
            p.fillRect(QRectF(ox + x + dx * off, oy + y + dy * off - v * 0.12 * h, b, b), col)
        p.restore()

    def wing_root(self):
        if self.has_form_art() and "back" in self.fmeta:
            return self.form_point(*self.fmeta["back"])
        return self.anchor_pt("back", (0.45, 0.55))

    def paint_light_wings(self, p, amount, lift):
        """Godmode wings: three fans of light rays per side, pink up top, white
        in the middle, cyan below, spreading out as amount goes 0 -> 1."""
        rx, ry = self.wing_root()
        # visible window area in local coordinates
        x_lo, x_hi = -PAD + 4, self.img_w + PAD - 4
        y_lo, y_hi = -PAD - lift + 4, self.img_h + PAD - lift - 4
        e = amount
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        # soft glow where the wings join her back
        g = QRadialGradient(rx, ry, 0.35 * self.img_h * e + 1)
        g.setColorAt(0, QColor(255, 255, 255, int(150 * e)))
        g.setColorAt(0.4, QColor(200, 170, 255, int(70 * e)))
        g.setColorAt(1, QColor(200, 170, 255, 0))
        p.setBrush(g)
        p.drawEllipse(QPointF(rx, ry), 0.35 * self.img_h * e + 1, 0.35 * self.img_h * e + 1)
        groups = ((-32, PINK), (-8, QColor("#e6dcff")), (16, CYAN))
        for side in (-1, 1):
            for gi, (deg, col) in enumerate(groups):
                for ri, spread in enumerate((-10, -5, 0, 5, 10)):
                    shimmer = math.sin(self.t * 3.1 + gi * 1.7 + ri * 0.9)
                    a = math.radians((70 + (deg + spread - 70) * e) + shimmer * 1.5)  # folded = down
                    dx, dy = side * math.cos(a), math.sin(a)
                    # longest ray that still fits inside the window
                    lim = []
                    if dx:
                        lim.append(((x_hi if dx > 0 else x_lo) - rx) / dx)
                    if dy:
                        lim.append(((y_hi if dy > 0 else y_lo) - ry) / dy)
                    L = max(0.0, min(lim)) * (0.78 + 0.18 * (1 - abs(spread) / 10) + 0.04 * shimmer) * e
                    if L < 4:
                        continue
                    px, py = -dy, dx
                    wd = L * (0.045 if spread == 0 else 0.03)
                    poly = QPolygonF([QPointF(rx, ry),
                                      QPointF(rx + dx * L * 0.3 + px * wd, ry + dy * L * 0.3 + py * wd),
                                      QPointF(rx + dx * L, ry + dy * L),
                                      QPointF(rx + dx * L * 0.3 - px * wd, ry + dy * L * 0.3 - py * wd)])
                    gr = QLinearGradient(QPointF(rx, ry), QPointF(rx + dx * L, ry + dy * L))
                    c0, c1, c2 = QColor(255, 255, 255, int(230 * e)), QColor(col), QColor(col)
                    c1.setAlpha(int(200 * e))
                    c2.setAlpha(0)
                    gr.setColorAt(0, c0)
                    gr.setColorAt(0.45, c1)
                    gr.setColorAt(1, c2)
                    p.setBrush(gr)
                    p.drawPolygon(poly)
        p.restore()

    def paint_crystal_burst(self, p, u):
        """Cyan crystal shards bursting out of her back as she re-forms."""
        rx, ry = self.wing_root()
        rng = random.Random(7)
        p.save()
        p.setOpacity(max(0.0, 1 - u) ** 0.7)
        for i in range(16):
            side = -1 if i % 2 else 1
            a = math.radians(rng.uniform(-50, 40))
            dx, dy = side * math.cos(a), math.sin(a)
            L = (0.25 + 0.5 * rng.random()) * self.img_h * (0.3 + 0.9 * u)
            w = L * 0.08
            px, py = -dy, dx
            base = 0.15 * L
            poly = QPolygonF([QPointF(rx + dx * base, ry + dy * base),
                              QPointF(rx + dx * L * 0.6 + px * w, ry + dy * L * 0.6 + py * w),
                              QPointF(rx + dx * L, ry + dy * L),
                              QPointF(rx + dx * L * 0.6 - px * w * 0.4, ry + dy * L * 0.6 - py * w * 0.4)])
            p.setPen(QPen(QColor(230, 255, 255, 220), 1))
            p.setBrush(QColor(94, 200, 255, 150) if i % 3 else QColor(140, 120, 255, 150))
            p.drawPolygon(poly)
        p.restore()

    def paint_sticker_body(self, p, phase, glitching):
        """LV.999 chibi: the current sticker, with a quick pop when it changes."""
        u = min(1.0, (self.t - self.sticker_t) / 0.22)
        cur, prev = self.stickers[self.sticker_cur], self.stickers[self.sticker_prev]

        def place(px):
            return (self.img_w - px.width()) / 2, self.img_h - px.height()
        if phase == "active":
            self.paint_aura(p, cur, *place(cur))
        base = p.opacity()
        p.save()
        if u < 1:  # bounce about her base and crossfade while the sticker swaps
            sc = 1 + 0.1 * math.sin(u * math.pi)
            p.translate(self.img_w / 2, self.img_h)
            p.scale(sc, sc)
            p.translate(-self.img_w / 2, -self.img_h)
            p.setOpacity(base * (1 - u))
            self.draw_pix(p, prev, *place(prev), glitching)
            p.setOpacity(base * u)
        self.draw_pix(p, cur, *place(cur), glitching)
        p.restore()

    def idle_frame(self):
        """Current frame of her LV.999 idle animation, with its local offset."""
        if not self.idle_frames:
            self.build_idle_frames()
        if not self.idle_frames:
            return None
        i = int((self.t - self.anim_t0) * 1000 / max(20, self.idle_meta.get("frame_ms", 100))) % len(self.idle_frames)
        return self.idle_frames[i], self.idle_off[0], self.idle_off[1]

    def paint_lv999_body(self, p, phase, k, pix, idle, glitching):
        """Her full-size body, crossfading between the still art (needed for the
        visor / shades / gauntlet moments) and the idle animation."""
        still = self.form_sprite(pix)
        bare = self.form_sprite(pix, True)
        anim = idle or still

        def draw(sprite, a, aura=False):
            if a <= 0:
                return
            p.save()
            p.setOpacity(p.opacity() * a)
            if aura:
                self.paint_aura(p, *sprite)
            self.draw_pix(p, *sprite, glitching)
            p.restore()
        if phase == "settle":
            draw(still, 1 - k)
            draw(anim, k)
        elif phase == "unsettle":
            draw(anim, 1 - k)
            draw(still, k)
        elif phase == "lv999":
            draw(anim, 1)
        elif phase == "visor":
            draw(bare, 1, aura=k > 0.45)
            draw(anim, max(0.0, 1 - k / 0.15))
        elif phase == "godoff":
            u = max(0.0, (k - 0.65) / 0.35)
            draw(bare, 1 - u, aura=k < 0.15)
            draw(anim, u)

    def paint_visor_and_shades(self, p, phase, k):
        """Her visor slides down from her head and turns into the godmode
        shades; when godmode ends the shades turn back and it goes back up."""
        vx, vy, vw, vh = self.form_meta["visor"]
        ex, ey, ew = self.form_meta["eyes"]
        hx, hy = self.form_point(vx + vw / 2, vy + vh / 2)
        tx, ty = self.form_point(ex, ey)
        art, _, _ = self.form_sprite(self.frame(), True)
        width = ew * art.width()
        visor = self.form_visor_scaled

        def visor_at(u, alpha):  # u: 0 = on her head, 1 = over her eyes
            if alpha <= 0:
                return
            e = u * u * (3 - 2 * u)
            p.save()
            p.setOpacity(p.opacity() * alpha)
            p.translate(hx + (tx - hx) * e, hy + (ty - hy) * e)
            p.rotate(math.sin(e * math.pi) * -8)
            p.drawPixmap(QPointF(-visor.width() / 2, -visor.height() / 2), visor)
            p.restore()
        if phase == "visor":
            if k < 0.45:
                visor_at(k / 0.45, 1)
                return
            u = min(1.0, (k - 0.45) / 0.25)
            visor_at(1, 1 - u)
            self.paint_flash(p, tx, ty, width * 1.6, 1 - abs(u * 2 - 1))
            self.draw_shades(p, tx, ty, width, 0.55 + 0.45 * u, u, sparkle=1.0 - 0.6 * min(1.0, (k - 0.45) / 0.55))
        elif phase == "active":
            sp = max(0.0, math.sin(self.t * 1.3)) ** 12  # an occasional glint
            self.draw_shades(p, tx, ty, width, 1.0, 1.0, sparkle=0.4 * sp)
        elif phase == "godoff":
            if k < 0.15:
                u = k / 0.15
                self.paint_flash(p, tx, ty, width * 1.4, 1 - u)
                self.draw_shades(p, tx, ty, width, 1.0, 1 - u)
                visor_at(1, u)
            elif k < 0.65:
                visor_at(1 - (k - 0.15) / 0.5, 1)
            else:
                visor_at(0, 1 - (k - 0.65) / 0.35)

    @staticmethod
    def paint_flash(p, x, y, r, a):
        if a <= 0:
            return
        g = QRadialGradient(x, y, r)
        g.setColorAt(0, QColor(255, 255, 255, int(240 * a)))
        g.setColorAt(0.3, QColor(255, 180, 240, int(140 * a)))
        g.setColorAt(1, QColor(94, 242, 255, 0))
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(x, y), r, r)
        p.restore()

    @staticmethod
    def draw_shades(p, x, y, width, scale, alpha, sparkle=0.0):
        """The godmode shades: one wide angular piece, outer tips swept up,
        cyan on her right fading to pink on her left, with a star glint."""
        if alpha <= 0:
            return
        s = width / 2 * scale
        h = s * 0.55

        def q(u, v):
            return QPointF(x + u * s, y + v * h)
        shape = QPolygonF([q(-1.35, -0.85), q(-0.2, -0.12), q(0, 0.02), q(0.2, -0.12), q(1.35, -0.85),
                           q(0.85, 0.35), q(0.3, 0.55), q(0, 0.3), q(-0.3, 0.55), q(-0.85, 0.35)])
        p.save()
        p.setOpacity(alpha)
        g = QLinearGradient(q(-1.2, 0), q(1.2, 0))
        g.setColorAt(0, QColor(94, 242, 255, 240))
        g.setColorAt(0.5, QColor(190, 170, 255, 235))
        g.setColorAt(1, QColor(255, 107, 214, 240))
        p.setPen(QPen(QColor(20, 16, 40, 230), max(1.0, s * 0.06),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.MiterJoin))
        p.setBrush(g)
        p.drawPolygon(shape)
        # light streak across the lenses
        p.setPen(QPen(QColor(255, 255, 255, 170), max(1.0, s * 0.07)))
        p.drawLine(q(-1.0, -0.42), q(-0.35, -0.05))
        p.drawLine(q(0.35, -0.05), q(1.0, -0.42))
        if sparkle > 0:  # four-point star on her left lens, as in the cutscene
            cx_, cy_ = x + 0.6 * s, y - 0.1 * h
            r = s * 0.9 * sparkle
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, int(255 * min(1.0, sparkle * 1.5))))
            p.drawPolygon(QPolygonF([QPointF(cx_, cy_ - r), QPointF(cx_ + r * 0.16, cy_ - r * 0.16),
                                     QPointF(cx_ + r, cy_), QPointF(cx_ + r * 0.16, cy_ + r * 0.16),
                                     QPointF(cx_, cy_ + r), QPointF(cx_ - r * 0.16, cy_ + r * 0.16),
                                     QPointF(cx_ - r, cy_), QPointF(cx_ - r * 0.16, cy_ - r * 0.16)]))
        p.restore()

    def paint_screen_glow(self, p, phase, k):
        """Her handheld lights up once the cartridge is in, and shows 999."""
        sx, sy = self.anchor_pt("screen", (0.5, 0.75))
        r = 0.05 * self.img_h
        flick = 0.6 + 0.4 * math.sin(self.t * 23) if phase == "digital" else 0.8
        g = QRadialGradient(sx, sy, r * 2.2)
        c0, c1 = QColor(CYAN), QColor(CYAN)
        c0.setAlpha(int(170 * flick))
        c1.setAlpha(0)
        g.setColorAt(0, c0)
        g.setColorAt(1, c1)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(sx, sy), r * 2.2, r * 2.2)
        if phase == "digital":
            f = QFont("Source Code Pro")
            f.setPixelSize(max(6, int(r * 0.9)))
            f.setBold(True)
            p.setFont(f)
            p.setPen(PINK)
            p.drawText(QRectF(sx - r * 1.5, sy - r, r * 3, r * 2), Qt.AlignmentFlag.AlignCenter, "999")
        p.restore()

    def cart_size(self, small=False):
        ch = (0.06 if small else 0.12) * self.img_h
        return ch * 0.82, ch

    def gauntlet_pt(self):
        """Where the cartridge goes: her gauntlet (full-size art) or, without
        the art, the chibi's handheld."""
        if self.has_form_art() and "gauntlet" in self.fmeta:
            return self.form_point(*self.fmeta["gauntlet"])
        return self.anchor_pt("slot", (0.5, 0.7))

    def cart_hover_pt(self):
        return self.img_w * 0.7, -PAD * 0.3 + math.sin(self.t * 2.2) * 4

    def paint_cartridge(self, p, phase, k):
        if phase in ("cart", "slot", "digital", "derez"):
            return self.paint_cartridge_handheld(p, phase, k)
        if phase not in ("insert", "eject"):
            return
        hx, hy = self.cart_hover_pt()
        gx, gy = self.gauntlet_pt()
        big_w, big_h = self.cart_size()
        sm_w, sm_h = self.cart_size(small=True)
        x, y, ang, cw, ch, glow = hx, hy, math.sin(self.t * 1.7) * 14, big_w, big_h, 1.0
        alpha = 1.0
        if phase == "cart":  # tossed in from above, spinning, then hovers
            e = 1 - (1 - k) ** 3
            x = hx + (1 - e) * 0.3 * self.img_w
            y = (-PAD - big_h) + (hy - (-PAD - big_h)) * e
            ang = (1 - e) * 540 + e * ang
            glow = e
        elif phase == "insert":
            u = min(1.0, k / INSERT_HIT)
            e = u * u  # accelerates into the slot
            x, y = hx + (gx - hx) * e, hy + (gy - hy) * e
            ang *= 1 - u
            cw, ch = big_w + (sm_w - big_w) * e, big_h + (sm_h - big_h) * e
            glow = 1.0 - 0.5 * u
        elif phase in ("visor", "active"):
            x, y, ang, cw, ch, glow = gx, gy, 0.0, sm_w, sm_h, 0.5 + 0.2 * math.sin(self.t * 4)
        elif phase == "eject":  # pops out of the gauntlet and flies off-screen
            if k < 0.2:
                x, y, ang, cw, ch = gx, gy - (k / 0.2) * big_h * 0.8, 0.0, sm_w, sm_h
            else:
                v = (k - 0.2) / 0.8
                x = gx + v * 0.6 * self.img_w
                y = gy - big_h * 0.8 - v * (gy + PAD + big_h * 2)
                ang = -v * 720
                cw, ch = sm_w + (big_w - sm_w) * v, sm_h + (big_h - sm_h) * v
            glow = 0.6
        p.save()
        p.setOpacity(alpha)
        if glow > 0:  # the sealed LV.999 humming inside it
            r = ch * 1.1
            g = QRadialGradient(x, y - ch / 2, r)
            c0 = QColor(PINK if int(self.t * 3) % 2 else CYAN)
            c0.setAlpha(int(140 * glow))
            c1 = QColor(c0)
            c1.setAlpha(0)
            g.setColorAt(0, c0)
            g.setColorAt(1, c1)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(x, y - ch / 2), r, r)
        p.translate(x, y)
        p.rotate(ang)
        self.draw_cart_shape(p, cw, ch)
        p.restore()

    def paint_cartridge_handheld(self, p, phase, k):
        """Cutscene version: tossed in, lands on her handheld, clicks into it,
        then breaks up with her when she de-rezzes."""
        if phase == "derez" and k >= 0.5:
            return
        slot_x, slot_y = self.anchor_pt("slot", (0.5, 0.7))
        cw, ch = self.cart_size()
        seated = slot_y + ch * 0.35  # how deep it sits once inserted
        x, y, ang, clip, alpha = slot_x, seated, 0.0, True, 1.0
        if phase == "cart":  # tossed in from above, spinning, lands on the slot
            e = 1 - (1 - k) ** 3
            x = slot_x + (1 - e) * 0.35 * self.img_w
            y = (-PAD - ch) + (slot_y - (-PAD - ch)) * e
            ang = (1 - e) * 540
            clip = False
        elif phase == "slot":  # chk
            y = slot_y + (seated - slot_y) * (k * k)
        elif phase == "derez":
            alpha = max(0.0, 1 - k * 2.5)
        p.save()
        p.setOpacity(alpha)
        if clip:  # the part below the slot is inside the handheld
            p.setClipRect(QRectF(-4 * self.img_w, -4 * self.img_h, 8 * self.img_w, 4 * self.img_h + slot_y))
        p.translate(x, y)
        p.rotate(ang)
        self.draw_cart_shape(p, cw, ch)
        p.restore()

    def paint_gauntlet_glow(self, p, phase, k):
        """Once the cartridge is in, her gauntlet's gems light up and a 999
        readout flashes over it, as in the cutscene."""
        if "gems" not in self.fmeta:
            return
        gx, gy = self.gauntlet_pt()
        if phase == "insert":
            u = (k - INSERT_HIT) / (1 - INSERT_HIT)
        else:
            u = 1.0
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        cols = (PINK, CYAN, QColor("#ffe066"), QColor("#7dff9a"))
        for i, (fx, fy) in enumerate(self.form_meta["gems"]):
            on = max(0.0, min(1.0, u * 3 - i * 0.6))  # light up one after another
            if on <= 0:
                continue
            x, y = self.form_point(fx, fy)
            pulse = 0.7 + 0.3 * math.sin(self.t * 6 + i)
            r = 0.035 * self.img_h * (1 + (1 - on) * 1.5)
            g = QRadialGradient(x, y, r)
            c0, c1 = QColor(cols[i % len(cols)]), QColor(cols[i % len(cols)])
            c0.setAlpha(int(230 * on * pulse))
            c1.setAlpha(0)
            g.setColorAt(0, QColor(255, 255, 255, int(230 * on * pulse)))
            g.setColorAt(0.35, c0)
            g.setColorAt(1, c1)
            p.setBrush(g)
            p.drawEllipse(QPointF(x, y), r, r)
        if phase == "insert" and u > 0:  # "999" readout
            f = QFont("Source Code Pro")
            f.setPixelSize(max(8, int(0.05 * self.img_h)))
            f.setBold(True)
            p.setFont(f)
            a = min(1.0, u * 3) * (1 - max(0.0, u - 0.7) / 0.3)
            c = QColor(PINK)
            c.setAlphaF(max(0.0, a))
            p.setPen(c)
            p.drawText(QPointF(gx - 0.05 * self.img_h, gy - 0.05 * self.img_h - u * 8), "999")
        p.restore()

    @staticmethod
    def draw_cart_shape(p, cw, ch):
        """Retro game cartridge, anchored at the middle of its bottom edge."""
        body = QPainterPath()
        body.moveTo(-cw / 2, -ch)
        body.lineTo(cw / 2 - cw * 0.18, -ch)
        body.lineTo(cw / 2, -ch + cw * 0.18)  # clipped corner
        body.lineTo(cw / 2, 0)
        body.lineTo(-cw / 2, 0)
        body.closeSubpath()
        p.setPen(QPen(QColor(10, 8, 18), 1.4))
        p.setBrush(QColor(52, 48, 66))
        p.drawPath(body)
        p.setPen(QPen(QColor(30, 26, 42), 1))
        for i in range(3):
            yy = -ch + ch * (0.07 + 0.05 * i)
            p.drawLine(QPointF(-cw * 0.35, yy), QPointF(cw * 0.2, yy))
        lab = QRectF(-cw * 0.38, -ch * 0.72, cw * 0.76, ch * 0.5)
        g = QLinearGradient(lab.topLeft(), lab.bottomRight())
        g.setColorAt(0, CYAN)
        g.setColorAt(1, PINK)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawRect(lab)
        f = QFont("Source Code Pro")
        f.setPixelSize(max(5, int(ch * 0.2)))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(14, 10, 26))
        p.drawText(lab, Qt.AlignmentFlag.AlignCenter, "999")
        p.setPen(QPen(GOLD, 1))
        for i in range(5):
            xx = -cw * 0.3 + i * cw * 0.15
            p.drawLine(QPointF(xx, -ch * 0.12), QPointF(xx, -2))

    # --- LV.999 effects in window coordinates ---
    def circuit_paths(self):
        """Circuit traces branching out from her handheld (fixed per size)."""
        key = (self.width(), self.height())
        if getattr(self, "_circuits_key", None) == key:
            return self._circuits
        rng = random.Random(31)
        w, h = self.width(), self.height()
        sx, sy = self.anchor_pt("screen", (0.5, 0.75))
        ox, oy = w / 2 - self.img_w / 2 + sx, PAD + sy
        paths = []
        for i in range(14):
            pts = [(ox, oy)]
            x, y = ox, oy
            horiz = i % 2 == 0
            for _ in range(rng.randint(3, 5)):
                if horiz:
                    x = max(4.0, min(w - 4.0, x + rng.choice((-1, 1)) * rng.uniform(25, 90)))
                else:
                    y = max(4.0, min(h - 4.0, y + rng.choice((-1, 1)) * rng.uniform(20, 70)))
                pts.append((x, y))
                horiz = not horiz
            paths.append((pts, rng.uniform(0, 0.35)))
        self._circuits_key, self._circuits = key, paths
        return paths

    def paint_circuits(self, p, k):
        """Her transformation opens in a circuit-board world: traces light up
        and race outward from the handheld."""
        p.save()
        for pts, delay in self.circuit_paths():
            u = max(0.0, min(1.0, (k - delay) / 0.5))
            if u <= 0:
                continue
            fade = 1.0 if k < 0.8 else max(0.0, (1 - k) / 0.2)
            total = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
            left = total * u
            path = QPainterPath(QPointF(*pts[0]))
            end = pts[0]
            for a, b in zip(pts, pts[1:]):
                seg = math.hypot(b[0] - a[0], b[1] - a[1])
                if left >= seg:
                    path.lineTo(*b)
                    end = b
                    left -= seg
                else:
                    t = left / seg if seg else 0
                    end = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                    path.lineTo(*end)
                    break
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(94, 160, 255, int(70 * fade)), 5))
            p.drawPath(path)
            p.setPen(QPen(QColor(150, 220, 255, int(220 * fade)), 1.6))
            p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(220, 250, 255, int(255 * fade)))
            p.drawEllipse(QPointF(*end), 2.5, 2.5)
        p.restore()

    def paint_pixel_scan(self, p, k):
        """A bright column of pixels sweeping across her."""
        w, h = self.width(), self.height()
        cell = max(4, round(self.img_h / 45))
        bw = w * 0.14
        x0 = -bw + (w + bw) * k
        rng = random.Random(int(self.t * 20))
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        y = 0
        while y < h:
            x = x0
            while x < x0 + bw:
                d = 1 - abs((x - x0) / bw * 2 - 1)  # brightest in the middle
                if rng.random() < 0.75 * d:
                    c = QColor(94, 170 + rng.randint(0, 80), 255, int(40 + 150 * d * rng.random()))
                    p.fillRect(QRectF(x, y, cell - 1, cell - 1), c)
                x += cell
            y += cell
        p.restore()

    # --- godmode effects layer (full screen, global coordinates) ---
    def update_fx_layer(self):
        now = self.t
        for fx in self.fx:
            u = (now - fx["t0"]) / fx["dur"]
            if fx["kind"] == "rain" and u >= 0.58 and not fx.get("boomed"):
                fx["boomed"] = True
                self.play("boom")
                self.add_burst(fx["target"], 46, BOOM_COLORS)
            elif fx["kind"] == "beam" and u >= 0.25 and not fx.get("fired"):
                fx["fired"] = True
                self.play("laser")
                self.add_burst(fx["target"], 22, SW999_COLORS)
            elif fx["kind"] == "slash" and u >= 0.25 and not fx.get("swung"):
                fx["swung"] = True
                self.play("slash")
            elif fx["kind"] == "win" and not fx.get("popped"):
                fx["popped"] = True
                r = self.fxl.geometry() if self.fxl else self.screen_rect()
                for sx in (0.3, 0.7):
                    self.add_burst(QPointF(r.left() + r.width() * sx, r.top() + r.height() * 0.42), 30, CUBE_COLORS)
        self.fx = [fx for fx in self.fx if now - fx["t0"] < fx["dur"]]
        self.trail = [q for q in self.trail if now - q[2] < 0.6]
        if self.fxl is None or not self.fxl.isVisible():
            return
        if self.form_phase != "active" and not self.fx and not self.trail:
            self.fxl.hide()
        else:
            self.fxl.update()

    def paint_fx(self, p, org):
        now = self.t

        def L(pt):
            return QPointF(pt.x() - org.x(), pt.y() - org.y())
        # light trail while she flies
        for (x0, y0, t0), (x1, y1, t1) in zip(self.trail, self.trail[1:]):
            a = max(0.0, 1 - (now - t1) / 0.6)
            for col, wd, al in ((PINK, 18, 70), (CYAN, 9, 130), (QColor("#ffffff"), 3, 220)):
                c = QColor(col)
                c.setAlpha(int(al * a))
                p.setPen(QPen(c, wd * a + 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(L(QPointF(x0, y0)), L(QPointF(x1, y1)))
        for fx in self.fx:
            u = max(0.0, (now - fx["t0"]) / fx["dur"])
            getattr(self, "fx_" + fx["kind"])(p, fx, u, L)

    def fx_rain(self, p, fx, u, L):
        """Lasers raining in from all around onto one spot (her ultimate)."""
        t = L(fx["target"])
        fade = 1.0 if u < 0.58 else max(0.0, 1 - (u - 0.58) / 0.15)
        for i, (sx, sy, delay) in enumerate(fx["starts"]):
            v = max(0.0, min(1.0, (u - delay) / 0.28))
            if v <= 0 or fade <= 0:
                continue
            s = L(QPointF(sx, sy))
            head = QPointF(s.x() + (t.x() - s.x()) * v, s.y() + (t.y() - s.y()) * v)
            col = (CYAN, QColor("#ffffff"), PINK, QColor("#b7a8ff"))[i % 4]
            c = QColor(col)
            c.setAlpha(int(110 * fade))
            p.setPen(QPen(c, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(s, head)
            p.setPen(QPen(QColor(255, 255, 255, int(230 * fade)), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(s, head)
        if 0.45 < u < 0.75:  # converge flash
            a = 1 - abs((u - 0.6) / 0.15)
            self.paint_flash(p, t.x(), t.y(), 70, a)

    def fx_burst(self, p, fx, u, L):
        """Pixel explosion: chunky squares flying out, a little gravity."""
        at = L(fx["at"])
        tau = u * fx["dur"]
        if u < 0.3:
            r = 20 + 260 * tau
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, int(200 * (1 - u / 0.3))), 4))
            p.drawEllipse(at, r, r)
        p.setPen(Qt.PenStyle.NoPen)
        for ang, sp, col, sz in fx["bits"]:
            x = at.x() + math.cos(ang) * sp * tau
            y = at.y() + math.sin(ang) * sp * tau + 220 * tau * tau
            c = QColor(col)
            c.setAlphaF(max(0.0, 1 - u))
            p.fillRect(QRectF(x - sz / 2, y - sz / 2, sz, sz), c)
            p.fillRect(QRectF(x - sz / 2, y - sz / 2, sz, max(1.0, sz * 0.3)),
                       QColor(255, 255, 255, int(150 * (1 - u))))

    def fx_beam(self, p, fx, u, L):
        """She charges a shot in her gauntlet and fires a beam at the target."""
        o = L(self.hand_global())
        t = L(fx["target"])
        if u < 0.25:  # charging orb with pixels being pulled in
            v = u / 0.25
            self.paint_flash(p, o.x(), o.y(), 8 + 26 * v, 0.6 + 0.4 * v)
            rng = random.Random(int(self.t * 30))
            p.setPen(Qt.PenStyle.NoPen)
            for _ in range(10):
                a, r = rng.uniform(0, 2 * math.pi), (1 - v) * 60 + rng.uniform(0, 20)
                p.fillRect(QRectF(o.x() + math.cos(a) * r, o.y() + math.sin(a) * r, 4, 4), rng.choice(CUBE_COLORS))
            return
        fade = 1.0 if u < 0.8 else max(0.0, 1 - (u - 0.8) / 0.2)
        th = 9 * (1 + 0.25 * math.sin(self.t * 40))
        for col, wd, al in ((PINK, 2.6, 90), (CYAN, 1.4, 180), (QColor("#ffffff"), 0.5, 255)):
            c = QColor(col)
            c.setAlpha(int(al * fade))
            p.setPen(QPen(c, th * wd, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(o, t)
        rng = random.Random(int(self.t * 25))
        p.setPen(Qt.PenStyle.NoPen)
        for _ in range(14):  # pixels shed along the beam
            s = rng.random()
            x, y = o.x() + (t.x() - o.x()) * s, o.y() + (t.y() - o.y()) * s
            c = QColor(rng.choice(CUBE_COLORS))
            c.setAlphaF(fade * 0.9)
            p.fillRect(QRectF(x + rng.uniform(-14, 14), y + rng.uniform(-14, 14), 5, 5), c)
        self.paint_flash(p, o.x(), o.y(), 22, fade)
        self.paint_flash(p, t.x(), t.y(), 40, fade)

    def fx_slash(self, p, fx, u, L):
        """A big pixel-art sword swung in an arc (from her battle moves)."""
        pivot = L(self.hand_global())
        side = fx["side"]
        a0, a1 = -125.0, 55.0
        if u < 0.25:
            e, grow = 0.0, u / 0.25
        elif u < 0.55:
            v = (u - 0.25) / 0.3
            e, grow = 1 - (1 - v) ** 3, 1.0
        else:
            e, grow = 1.0, 1.0
        fade = 1.0 if u < 0.7 else max(0.0, 1 - (u - 0.7) / 0.3)

        def world_ang(a):
            return a if side > 0 else 180 - a
        cur = a0 + (a1 - a0) * e
        length = 1.1 * self.img_h * (0.4 + 0.6 * grow)
        cell = max(5.0, self.img_h / 34)
        # pixel arc left behind by the swing
        if 0.25 <= u:
            p.setPen(Qt.PenStyle.NoPen)
            steps = int(abs(cur - a0) / 4)
            for i in range(steps):
                a = math.radians(world_ang(a0 + (cur - a0) * i / max(1, steps)))
                for rr in (0.62, 0.78, 0.92):
                    c = QColor(PINK if rr > 0.9 else CYAN)
                    c.setAlphaF(fade * 0.55 * (i / max(1, steps)))
                    x = pivot.x() + math.cos(a) * length * rr
                    y = pivot.y() + math.sin(a) * length * rr
                    p.fillRect(QRectF(x - cell / 2, y - cell / 2, cell, cell), c)
        # afterimages, then the sword
        if 0.25 <= u < 0.6:
            for i in (3, 2, 1):
                self.draw_pixel_sword(p, pivot, world_ang(cur - (a1 - a0) * 0.06 * i), length, cell, fade * 0.18 * (4 - i))
        self.draw_pixel_sword(p, pivot, world_ang(cur), length, cell, fade)

    @staticmethod
    def draw_pixel_sword(p, pivot, ang, length, cell, alpha):
        if alpha <= 0:
            return
        n = max(8, int(length / cell))
        p.save()
        p.translate(pivot)
        p.rotate(ang)
        p.setOpacity(alpha)
        p.setPen(Qt.PenStyle.NoPen)
        handle, guard = QColor(58, 29, 92), CYAN
        for i in range(n):
            x = i * cell
            if i < 2:  # handle
                p.fillRect(QRectF(x, -cell / 2, cell, cell), handle)
            elif i == 2:  # cross-guard
                p.fillRect(QRectF(x, -cell * 2.5, cell, cell * 5), guard)
            else:
                taper = 1 if i >= n - 2 else 3
                for row in range(-(taper // 2), taper // 2 + 1):
                    if i == n - 1:
                        col = PINK
                    elif row == 0:
                        col = QColor("#ffffff")
                    else:
                        col = QColor(94, 242, 255)
                    p.fillRect(QRectF(x, row * cell - cell / 2, cell + 0.5, cell + 0.5), col)
        p.restore()

    def fx_win(self, p, fx, u, L):
        """YOU WIN, big and pixelated, from her Elation skill."""
        if self.fxl is None:
            return
        img = self.win_text_image()
        W, H = self.fxl.width(), self.fxl.height()
        s = min(W * 0.6 / img.width(), 12.0)
        if u < 0.12:
            s *= 0.3 + 0.9 * (u / 0.12)
        elif u < 0.2:
            s *= 1.2 - 0.2 * ((u - 0.12) / 0.08)
        a = 1.0 if u < 0.8 else max(0.0, 1 - (u - 0.8) / 0.2)
        w, h = img.width() * s, img.height() * s
        x, y = W / 2 - w / 2, H * 0.42 - h / 2
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.setOpacity(a)
        rng = random.Random(int(self.t * 12))
        glitch = rng.random() < 0.25
        # glitch copies
        p.setOpacity(a * 0.5)
        p.drawImage(QRectF(x - 6, y, w, h), self.win_text_image(CYAN))
        p.drawImage(QRectF(x + 6, y, w, h), self.win_text_image(PINK))
        p.setOpacity(a)
        if glitch:  # a few sliced rows shifted sideways
            rows = img.height()
            for r in range(rows):
                dx = rng.choice((0, 0, 0, rng.uniform(-18, 18)))
                p.drawImage(QRectF(x + dx, y + r * s, w, s), img, QRectF(0, r, img.width(), 1))
        else:
            p.drawImage(QRectF(x, y, w, h), img)
        f = QFont("Source Code Pro")
        f.setPixelSize(max(14, int(s * 2.2)))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#e8e6ff"))
        p.drawText(QRectF(0, y + h + 6, W, s * 4), Qt.AlignmentFlag.AlignHCenter, "LV.999  ·  SCORE 999,999,999")
        p.restore()

    def win_text_image(self, solid=None):
        """'YOU WIN' rendered tiny without antialiasing, so scaling it up keeps it pixelated."""
        key = "win" if solid is None else solid.name()
        cache = self.__dict__.setdefault("_win_imgs", {})
        if key in cache:
            return cache[key]
        f = QFont("Source Code Pro")
        f.setPixelSize(13)
        f.setBold(True)
        f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        fm = QFontMetrics(f)
        img = QImage(fm.horizontalAdvance("YOU WIN") + 4, fm.height() + 2, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        q = QPainter(img)
        q.setFont(f)
        q.setPen(QColor("#ffffff"))
        q.drawText(QPointF(2, fm.ascent() + 1), "YOU WIN")
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        if solid is None:
            g = QLinearGradient(0, 0, img.width(), img.height())
            g.setColorAt(0, CYAN)
            g.setColorAt(0.5, QColor("#ffffff"))
            g.setColorAt(1, PINK)
            q.fillRect(img.rect(), g)
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
            for yy in range(0, img.height(), 2):  # scanlines
                q.fillRect(0, yy, img.width(), 1, QColor(0, 0, 0, 40))
        else:
            q.fillRect(img.rect(), solid)
        q.end()
        cache[key] = img
        return img

    def paint_godmode_bar(self, p, cx, sy, left):
        """Segmented retro bar under her feet showing how much godmode is left."""
        segs = 10
        sw_, gap, hh = 7, 2, 5
        total = segs * sw_ + (segs - 1) * gap
        x, y = cx - total / 2, sy + 14
        lit = math.ceil(left * segs - 1e-6)
        p.save()
        for i in range(segs):
            u = i / (segs - 1)
            c = QColor(int(94 + (255 - 94) * u), int(242 + (107 - 242) * u), int(255 + (214 - 255) * u))
            if i >= lit:
                c = QColor(40, 34, 60)
            p.fillRect(QRectF(x + i * (sw_ + gap), y, sw_, hh), c)
        f = QFont("Source Code Pro")
        f.setPixelSize(9)
        f.setBold(True)
        p.setFont(f)
        p.setPen(PINK)
        p.drawText(QPointF(x, y - 3), "GODMODE")
        p.restore()

    def paint_glitch(self, p, pix):
        w, h = pix.width(), pix.height()
        off = random.randint(3, 9)
        p.setOpacity(0.55)
        p.drawPixmap(-off, 0, self.get_tint(pix, QColor("#00f0ff")))
        p.drawPixmap(off, 0, self.get_tint(pix, QColor("#ff2bd6")))
        p.setOpacity(1.0)
        p.drawPixmap(0, 0, pix)
        for _ in range(random.randint(3, 7)):
            sy = random.randint(0, max(1, h - 4))
            sh = random.randint(3, max(4, h // 12))
            dx = random.randint(-22, 22)
            p.drawPixmap(QRectF(dx, sy, w, sh), pix, QRectF(0, sy, w, sh))
        for _ in range(random.randint(1, 3)):
            c = QColor(random.choice(PALETTE))
            c.setAlpha(90)
            p.fillRect(QRectF(random.uniform(-10, w * 0.3), random.uniform(0, h),
                              random.uniform(w * 0.3, w), random.uniform(1, 3)), c)

    def paint_particles(self, p):
        font = QFont("monospace")
        font.setPixelSize(11)
        font.setBold(True)
        zfont = QFont("Source Code Pro")
        zfont.setBold(True)
        p.setPen(Qt.PenStyle.NoPen)
        for q in self.particles:
            a = q["life"] / q["max"]
            a = min(1.0, a * 2.0) * (0.75 + 0.25 * math.sin(self.t * q["blink"]))
            c = QColor(q["color"])
            c.setAlphaF(max(0.0, min(1.0, a)))
            if q["kind"] in ("glyph", "z"):
                if q["kind"] == "z":
                    zfont.setPixelSize(q["size"])
                    p.setFont(zfont)
                else:
                    p.setFont(font)
                p.setPen(c)
                p.drawText(QPointF(q["x"], q["y"]), q["ch"])
                p.setPen(Qt.PenStyle.NoPen)
            elif q["kind"] == "cube":  # little lit cube: light top and left faces
                s = q["size"]
                r = QRectF(q["x"] - s / 2, q["y"] - s / 2, s, s)
                p.fillRect(r, c)
                hi = QColor(255, 255, 255, int(150 * c.alphaF()))
                p.fillRect(QRectF(r.left(), r.top(), s, max(1.0, s * 0.3)), hi)
                p.fillRect(QRectF(r.left(), r.top(), max(1.0, s * 0.3), s), hi)
            else:
                s = q["size"]
                p.fillRect(QRectF(q["x"] - s / 2, q["y"] - s / 2, s, s), c)

    def paint_floaters(self, p):
        for f in self.floaters:
            font = QFont("Good Times" if f.get("big") else "Source Code Pro")
            font.setPixelSize(f["size"])
            font.setBold(True)
            p.setFont(font)
            a = min(1.0, f["life"] / f["max"] * 2)
            # pixel-style hard shadow, then glitch offset copy, then text
            for dx, dy, col in ((2, 2, QColor(14, 10, 26)), (-1, 0, PINK if f["color"] != PINK else CYAN),
                                (0, 0, f["color"])):
                c = QColor(col)
                c.setAlphaF(a * (0.6 if (dx, dy) == (-1, 0) else 1))
                p.setPen(c)
                p.drawText(QPointF(f["x"] + dx, f["y"] + dy), f["text"])

    def paint_placeholder(self, p):
        r = QRectF(PAD, PAD, self.img_w, self.img_h)
        p.setBrush(QColor(40, 20, 70, 200))
        p.setPen(VIOLET)
        p.drawRoundedRect(r, 18, 18)
        p.setPen(QColor("white"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter,
                   "No images yet.\n\nDrop a transparent\nPNG / GIF into\nimages/\n\nthen right-click →\nReload images")

    # ---------- input ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.press_global = e.globalPosition().toPoint()
            self.drag_off = self.press_global - self.pos()
            self.drag_moved = False
        elif e.button() == Qt.MouseButton.RightButton:
            self.build_menu().exec(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self.drag_off is not None:
            g = e.globalPosition().toPoint()
            if (g - self.press_global).manhattanLength() > 4:
                if not self.drag_moved and random.random() < 0.25:
                    self.say("drag", cooldown=30)
                self.drag_moved = True
            if self.drag_moved:
                self.fly = None  # grabbing her mid-flight stops the flight
                self.move(g - self.drag_off)
                self.fpos = None
                self.wander_target = None

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.drag_off is not None:
            if not self.drag_moved:
                self.boop()
            else:
                self.wander_pause = 3.0
                self.save()
            self.drag_off = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.next_image()

    def wheelEvent(self, e):
        step = 1 if e.angleDelta().y() > 0 else -1
        self.cfg["height"] = int(self.cfg["height"] * (1.08 if step > 0 else 1 / 1.08))
        self.apply_size()
        self.save()

    def boop(self):
        now = time.monotonic()
        self.combo = self.combo + 1 if now - self.last_boop < 2.0 else 1
        self.last_boop = now
        self.jump_v = -200 if self.body_is_form() else -380  # full-size her only hops a little
        self.play("boop")
        if self.gum_t is None and not self.form_phase and self.cur_file and self.cur_file.name in GUM_POS:
            self.gum_t = self.t
        if self.form_phase == "active":  # godmode: boops just bounce her
            pass
        elif self.form_phase == "lv999":  # three quick boops: godmode
            self.lv_boops = [b for b in self.lv_boops if now - b < 2.0] + [now]
            if len(self.lv_boops) >= 3:
                self.lv_boops = []
                self.godmode()
            else:
                self.sticker_until = self.t + 1.5  # points at you
                self.say("sw999_boop", cooldown=5)
        else:
            self.floaters.append(dict(text="+1 EXP", x=PAD + self.img_w * 0.62 + random.uniform(-10, 10),
                                      y=PAD + self.img_h * 0.3, vy=-45, life=1.0, max=1.0,
                                      color=VIOLET, size=12))
        leveled = self.add_exp(1)
        if self.combo == 10 and not self.form_phase:
            self.transform()  # rapid booping overclocks her
        elif self.form_phase and not leveled:
            pass
        elif not leveled:
            if self.is_sleepy():
                self.say("sleep_boop", cooldown=8)
            elif self.combo >= 5 and self.combo % 5 == 0:
                self.say("boop", force=True)
            elif random.random() < 0.3:
                self.say("boop", cooldown=6)

    # ---------- menu / actions ----------
    def build_menu(self):
        m = QMenu()
        lv = m.addAction(f"Lv.{self.cfg['level']}  ·  EXP {self.cfg['exp']}/{EXP_PER_LEVEL}")
        lv.setEnabled(False)
        m.addSeparator()

        def toggle(label, key, fn=None, menu=m):
            a = QAction(label, menu, checkable=True)
            a.setChecked(bool(self.cfg[key]))

            def on(v, key=key):
                self.cfg[key] = v
                if fn:
                    fn(v)
                self.save()
            a.toggled.connect(on)
            menu.addAction(a)

        toggle("Speech bubbles", "speech", lambda v: v or self.bubble.hide())
        toggle("React to system (CPU, GPU, battery, Wi-Fi, USB, downloads)", "reactions")
        toggle("Sound effects", "sounds", lambda v: v and self.play("boop"))
        m.addAction("Say something", lambda: self.say("night" if self.is_sleepy() else "idle", force=True))
        m.addSeparator()
        if self.form_phase:
            if self.form_phase == "lv999" and self.can_godmode():
                m.addAction("Godmode!  (or boop her 3x)", self.godmode)
            m.addAction("Eject cartridge (back to Lv.{})".format(self.cfg["level"]), self.revert)
        else:
            m.addAction("Insert cartridge: LV.999  (or boop 10x fast)", self.transform)
        toggle("Surprise LV.999 transformations", "sw999_auto")
        toggle("Godmode: fly around and attack (experimental)", "sw999_play")
        look = m.addMenu("LV.999 look")
        for label, val in (("Chibi (stickers)", "chibi"), ("Full size", "full")):
            a = QAction(label, look, checkable=True)
            a.setChecked(self.cfg.get("sw999_style", "chibi") == val)
            a.triggered.connect(lambda _=False, val=val: (self.cfg.__setitem__("sw999_style", val), self.save()))
            look.addAction(a)
        dur = m.addMenu("LV.999 duration")
        for secs in (20, 30, 60, 120, 300):
            a = QAction(f"{secs} s", dur, checkable=True)
            a.setChecked(int(self.cfg.get("sw999_seconds", 30)) == secs)
            a.triggered.connect(lambda _=False, secs=secs: (self.cfg.__setitem__("sw999_seconds", secs), self.save()))
            dur.addAction(a)
        m.addSeparator()
        toggle("Wander around", "wander", lambda v: setattr(self, "fpos", None))
        toggle("Glitch effects", "glitch")
        toggle("Data particles", "particles")
        toggle("Mirror", "mirror")
        m.addSeparator()

        size = m.addMenu("Size")
        for name, h in (("Tiny", 150), ("Small", 220), ("Medium", 300), ("Large", 420), ("Huge", 600)):
            a = size.addAction(name)
            a.triggered.connect(lambda _=False, h=h: self.set_height(h))
        op = m.addMenu("Opacity")
        for pct in (100, 85, 70, 50, 30):
            a = op.addAction(f"{pct}%")
            a.triggered.connect(lambda _=False, pct=pct: self.set_opacity(pct / 100))

        m.addSeparator()
        m.addAction("Next image", self.next_image)
        m.addAction("Add image…", self.add_image)
        m.addAction("Open images folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(IMG_DIR))))
        m.addAction("Reload images", lambda: self.load_images())
        m.addSeparator()
        if self.tray:
            ct = QAction("Click-through (toggle from tray)", m, checkable=True)
            ct.setChecked(self.cfg["click_through"])
            ct.toggled.connect(lambda v: self.set_click_through(v))
            m.addAction(ct)
        m.addAction("Hide / show", self.toggle_visible)
        m.addAction("Quit", self.quit)
        return m

    def set_height(self, h):
        self.cfg["height"] = h
        self.apply_size()
        self.save()

    def set_opacity(self, o):
        self.cfg["opacity"] = o
        self.setWindowOpacity(o)
        self.save()

    def next_image(self):
        self.start_glitch(0.4)
        if self.form_phase or len(self.image_files()) < 2:
            return  # nothing to switch to (or she's LV.999 right now)
        self.cfg["image_index"] += 1
        self.gum_t = None
        self.load_images(forms=False)
        self.save()

    def add_image(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Add image", str(Path.home()),
                                            "Images (*.png *.gif *.webp *.apng *.jpg *.jpeg)")
        if fn:
            dest = IMG_DIR / Path(fn).name
            shutil.copy(fn, dest)
            files = self.image_files()
            self.cfg["image_index"] = files.index(dest)
            self.load_images(forms=False)
            self.save()

    def set_click_through(self, on, show=True):
        self.cfg["click_through"] = on
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, on)
        if show:
            self.show()
        self.save()

    def toggle_visible(self):
        self.setVisible(not self.isVisible())
        if not self.isVisible():
            self.bubble.hide()

    def on_tray(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.set_click_through(not self.cfg["click_through"])
            if self.tray:
                self.tray.showMessage("Silver Wolf",
                                      "Click-through ON" if self.cfg["click_through"] else "Click-through OFF",
                                      QSystemTrayIcon.MessageIcon.Information, 1500)
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self.build_menu().exec(QCursor.pos())

    def quit(self):
        if self.quitting:
            return
        self.quitting = True
        self.save()
        if self.isVisible() and self.say("quit", force=True):
            QTimer.singleShot(2600, QApplication.quit)  # let her finish the goodbye
        else:
            QApplication.quit()


def main():
    load_local_lines()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = Companion()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
