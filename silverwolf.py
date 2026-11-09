#!/usr/bin/env python3
"""
Silver Wolf floating desktop companion.

  Left-drag ........ move her
  Click ............ boop: hop, bubblegum, +EXP (every 10 = level up)
  Double-click ..... next image in images/
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
                         QFontMetrics, QGuiApplication, QIcon, QMovie,
                         QPainter, QPainterPath, QPen, QPixmap,
                         QRadialGradient)
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

# Where the bubblegum sits, as a fraction of the image (x, y). Images not listed
# here just hop when clicked.
GUM_POS = {"silverwolfchibi.png": (0.255, 0.625)}

DEFAULTS = dict(height=300, opacity=1.0, wander=False, glitch=True,
                particles=True, click_through=False, mirror=False,
                speech=True, reactions=True, sounds=True, sleepy_hours=[0, 6],
                exp=0, level=1,
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
}

# which sound each line plays (default: a short "speak" blip)
SOUND_FOR = {
    "levelup": "levelup", "download": "loot", "drive": "loot",
    "battery_low": "warn", "battery_critical": "warn", "cpu_temp": "warn", "gpu_hot": "warn",
    "ram_high": "warn", "cpu_high": "glitch", "gpu_busy": "glitch",
    "charging": "online", "net_up": "online", "net_down": "offline",
}
# sounds still allowed during sleepy hours (idle chatter blips stay quiet)
NIGHT_SOUNDS = {"warn", "offline", "boop", "pop", "levelup", "loot"}  # you clicked or it matters


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
        self.start = 0.0
        self.until = 0.0
        self.alpha = 0.0
        self.text_rect = QRect()

    def say(self, text, now):
        self.text = text
        fm = QFontMetrics(self.font)
        r = fm.boundingRect(QRect(0, 0, self.MAX_W, 1000),
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
            p.fillRect(QRectF(self.text_rect.left() + fm.horizontalAdvance(shown.split("\n")[-1]) % self.MAX_W,
                              self.text_rect.top() + 2, 7, fm.height() - 4), PINK)
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

    def load_images(self):
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
        self.apply_size()

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
    def check_system(self):
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
        if self.say("download", force=True, cooldown=5, name=short):
            self.celebrate("+50 EXP", CYAN)
            self.add_exp(5)

    # ---------- animation ----------
    def tick(self):
        now = time.monotonic()
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

        self.update_particles(dt, sleepy)
        for f in self.floaters:
            f["life"] -= dt
            f["y"] += f["vy"] * dt
        self.floaters = [f for f in self.floaters if f["life"] > 0]

        if self.cfg["wander"] and self.drag_off is None and not sleepy:
            self.wander(dt)

        self.sys_acc += dt
        if self.sys_acc >= 3.0:
            self.sys_acc = 0.0
            self.check_system()
        self.gpu_acc += dt
        if self.gpu_acc >= 10.0:
            self.gpu_acc = 0.0
            self.check_gpu()

        if now >= self.next_idle:
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
        if self.cfg["particles"]:
            self.spawn_acc += dt * (1.5 if sleepy else 5.0)
            while self.spawn_acc >= 1 and len(self.particles) < 50:
                self.spawn_acc -= 1
                if sleepy and random.random() < 0.6:
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
            self.say("levelup", force=True)
        self.save()
        return leveled

    # ---------- painting ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        sleepy = self.is_sleepy()
        lift = self.lift()
        tilt = math.sin(self.t * (0.5 if sleepy else 0.9)) * (4 if sleepy else 2.2)

        cx = self.width() / 2
        sy = PAD + self.img_h + 26
        k = max(0.4, min(1.2, 1.0 + (lift / 80.0)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(120, 90, 200, int(70 * k)))
        sw = self.img_w * 0.45 * k
        p.drawEllipse(QPointF(cx, sy), sw / 2, 7 * k)

        pix = self.frame()
        if pix is None or pix.isNull():
            self.paint_placeholder(p)
        else:
            p.save()
            if sleepy:
                p.setOpacity(0.85)
            p.translate(cx, PAD + self.img_h / 2 + lift)
            p.rotate(tilt)
            if self.cfg["mirror"]:
                p.scale(-1, 1)
            p.translate(-self.img_w / 2, -self.img_h / 2)
            if self.t < self.glitch_until:
                self.paint_glitch(p, pix)
            else:
                p.drawPixmap(0, 0, pix)
            p.restore()

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
        self.jump_v = -380
        self.play("boop")
        if self.gum_t is None and self.cur_file and self.cur_file.name in GUM_POS:
            self.gum_t = self.t
        self.floaters.append(dict(text="+1 EXP", x=PAD + self.img_w * 0.62 + random.uniform(-10, 10),
                                  y=PAD + self.img_h * 0.3, vy=-45, life=1.0, max=1.0,
                                  color=VIOLET, size=12))
        leveled = self.add_exp(1)
        if not leveled:
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
        m.addAction("Reload images", self.load_images)
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
        self.cfg["image_index"] += 1
        self.gum_t = None
        self.load_images()
        self.start_glitch(0.4)
        self.save()

    def add_image(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Add image", str(Path.home()),
                                            "Images (*.png *.gif *.webp *.apng *.jpg *.jpeg)")
        if fn:
            dest = IMG_DIR / Path(fn).name
            shutil.copy(fn, dest)
            files = self.image_files()
            self.cfg["image_index"] = files.index(dest)
            self.load_images()
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
        self.save()
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = Companion()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
