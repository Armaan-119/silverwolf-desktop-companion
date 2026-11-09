#!/usr/bin/env python3
"""Build the "SilverWolf" pixel-art X cursor theme into ~/.icons/SilverWolf.

  python3 tools/make_cursors.py            build + install
Then pick it with:  plasma-apply-cursortheme SilverWolf
Anything not drawn here (rare cursors) falls back to breeze_cursors.
"""
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtGui import QColor, QGuiApplication, QImage

THEME = "SilverWolf"
DEST = Path.home() / ".icons" / THEME
BASE = 24             # nominal cursor size
SCALES = (1, 2, 3)    # -> 24, 48, 72 px
COL = {"O": "#0e0a1a", "V": "#b48cff", "P": "#ff6bd6", "C": "#5ef2ff",
       "D": "#3b2d5c", "W": "#f4f0ff"}

ARROW = """
O............
OO...........
OPO..........
OPVO.........
OPVVO........
OPVVVO.......
OPVVVVO......
OPVVVVVO.....
OPVVVVVVO....
OPVVVVVVVO...
OPVVVVVVVVO..
OPVVVVVOOOOO.
OPVVOVVO.....
OPVOOVVO.....
OPO..OVVO....
OO...OVVO....
O.....OVVO...
......OVCO...
.......OO....
"""

HAND = """
....OO..........
...OPVO.........
...OPVO.........
...OPVO.........
...OPVOOO.......
...OPVOVVOOO....
...OPVOVVOVVOO..
OO.OPVOVVOVVOVO.
OVVOPVVVVVVVVVO.
OVVVVVVVVVVVVVO.
.OVVVVVVVVVVVVO.
.OVVVVVVVVVVVVO.
..OVVVVVVVVVVO..
..OVVVVVVVVVCO..
...OVVVVVVVCO...
...OVVVVVVVVO...
...OOOOOOOOOO...
"""

IBEAM = """
OOO.OOO
OPPOPPO
.OOVOO.
..OVO..
..OVO..
..OVO..
..OVO..
..OVO..
..OVO..
..OVO..
..OVO..
..OVO..
..OVO..
..OVO..
.OOVOO.
OCCOCCO
OOO.OOO
"""

H_RESIZE = """
...O.......O...
..OPO.....OPO..
.OPVOOOOOOOVPO.
OPVVVVVVVVVVVPO
.OPVOOOOOOOVPO.
..OPO.....OPO..
...O.......O...
"""

FD_RESIZE = """
OOOOOO.......
OPPPPO.......
OPVVO........
OPVVVO.......
OPOVVVO......
OO.OVVVO.....
....OVVVO....
.....OVVVO.OO
......OVVVOCO
.......OVVVCO
........OVVCO
.......OCCCCO
.......OOOOOO
"""


def parse(art):
    rows = [r for r in art.strip("\n").splitlines()]
    w = max(len(r) for r in rows)
    return [r.ljust(w, ".") for r in rows]


def transpose(g):
    return ["".join(g[y][x] for y in range(len(g))) for x in range(len(g[0]))]


def mirror(g):
    return [r[::-1] for r in g]


def merge(a, b):
    """Overlay two equally sized grids: fill beats outline beats empty."""
    rank = {".": 0, "O": 1}
    out = []
    for ra, rb in zip(a, b):
        out.append("".join(x if rank.get(x, 2) >= rank.get(y, 2) else y for x, y in zip(ra, rb)))
    return out


def blank(w, h):
    return [["."] * w for _ in range(h)]


def crosshair():
    n, c = 17, 8
    g = blank(n, n)
    for i in range(n):
        if abs(i - c) >= 3:
            for (x, y) in ((i, c), (c, i)):
                g[y][x] = "V" if i not in (0, n - 1) else "O"
            for d in (-1, 1):
                if g[c + d][i] == ".":
                    g[c + d][i] = "O"
                if g[i][c + d] == ".":
                    g[i][c + d] = "O"
    g[c][c] = "P"
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        g[c + dy][c + dx] = "O"
    return ["".join(r) for r in g]


def not_allowed():
    n = 16
    g = blank(n, n)
    c = (n - 1) / 2
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - c, y - c)
            on_slash = abs((x - c) - (y - c)) <= 1.0 and d < 5.2
            if 5 <= d <= 6.6 or on_slash:
                g[y][x] = "P"
            elif 4.0 <= d <= 7.6 or (abs((x - c) - (y - c)) <= 2.0 and d < 5.5):
                g[y][x] = "O"
    return ["".join(r) for r in g]


def spinner(frame, n=15, radius=5, block=3, count=8):
    g = blank(n, n)
    c = n // 2
    for i in range(count):
        a = 2 * math.pi * i / count - math.pi / 2
        bx = round(c + radius * math.cos(a)) - block // 2
        by = round(c + radius * math.sin(a)) - block // 2
        age = (frame - i) % count
        fill = "P" if age == 0 else "V" if age == 1 else "C" if age == 2 else "D"
        for y in range(by - 1, by + block + 1):
            for x in range(bx - 1, bx + block + 1):
                if 0 <= x < n and 0 <= y < n:
                    inside = by <= y < by + block and bx <= x < bx + block
                    if inside:
                        g[y][x] = fill
                    elif g[y][x] == ".":
                        g[y][x] = "O"
    return ["".join(r) for r in g]


def place(canvas, grid, ox, oy):
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch != "." and 0 <= oy + y < len(canvas) and 0 <= ox + x < len(canvas[0]):
                canvas[oy + y][ox + x] = ch


def centered(grid):
    """Put a grid in the middle of a BASE canvas; returns (canvas, hotspot)."""
    h, w = len(grid), len(grid[0])
    ox, oy = (BASE - w) // 2, (BASE - h) // 2
    cv = blank(BASE, BASE)
    place(cv, grid, ox, oy)
    return cv, (ox + w // 2, oy + h // 2)


def corner(grid, ox=2, oy=1, hot=(0, 0)):
    cv = blank(BASE, BASE)
    place(cv, grid, ox, oy)
    return cv, (ox + hot[0], oy + hot[1])


def save_png(canvas, scale, path):
    img = QImage(BASE * scale, BASE * scale, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    for y, row in enumerate(canvas):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            col = QColor(COL[ch])
            for dy in range(scale):
                for dx in range(scale):
                    img.setPixelColor(x * scale + dx, y * scale + dy, col)
    img.save(str(path))


def build(name, frames, hot, tmp, out_dir, delay=0):
    """frames: list of canvases. Writes one xcursor file via xcursorgen."""
    cfg = []
    for fi, cv in enumerate(frames):
        for s in SCALES:
            png = tmp / f"{name}_{fi}_{s}.png"
            save_png(cv, s, png)
            line = f"{BASE * s} {hot[0] * s + s // 2} {hot[1] * s + s // 2} {png}"
            cfg.append(line + (f" {delay}" if delay else ""))
    (tmp / f"{name}.cfg").write_text("\n".join(cfg) + "\n")
    subprocess.run(["xcursorgen", str(tmp / f"{name}.cfg"), str(out_dir / name)], check=True)


ALIASES = {
    "left_ptr": ["default", "arrow", "top_left_arrow", "left_arrow", "right_ptr", "draft_large",
                 "draft_small", "x-cursor", "context-menu", "help", "question_arrow",
                 "whats_this", "dnd-none", "dnd-move", "dnd-copy", "dnd-link", "copy", "alias",
                 "link"],
    "hand2": ["hand1", "pointer", "pointing_hand", "hand", "openhand", "grab",
              "9d800788f1b08800ae810202380a0822", "e29285e634086352946a0e7090d73106"],
    "xterm": ["text", "ibeam", "vertical-text"],
    "watch": ["wait"],
    "left_ptr_watch": ["progress", "half-busy", "3ecb610c1bf2410f44200f48c40d3599",
                       "08e8e1c95fe2fc01f976f1e063a24ccd", "00000000000000020006000e7e9ffc3f"],
    "crosshair": ["cross", "tcross", "cross_reverse", "diamond_cross", "cell", "plus", "color-picker"],
    "not-allowed": ["forbidden", "circle", "crossed_circle", "no-drop", "pirate",
                    "03b6e0fcb3499374a867c041f52298f0"],
    "sb_h_double_arrow": ["h_double_arrow", "ew-resize", "col-resize", "size_hor", "left_side",
                          "right_side", "e-resize", "w-resize", "split_h",
                          "028006030e0e7ebffc7f7070c0600140", "14fef782d02440884392942c11205230"],
    "sb_v_double_arrow": ["v_double_arrow", "ns-resize", "row-resize", "size_ver", "top_side",
                          "bottom_side", "n-resize", "s-resize", "split_v",
                          "00008160000006810000408080010102", "2870a09082c103050810ffdffffe0204"],
    "fd_double_arrow": ["nwse-resize", "size_fdiag", "top_left_corner", "bottom_right_corner",
                        "nw-resize", "se-resize", "c7088f0f3e6c8088236ef8e1e3e70000"],
    "bd_double_arrow": ["nesw-resize", "size_bdiag", "top_right_corner", "bottom_left_corner",
                        "ne-resize", "sw-resize", "fcf1c3c7cd4491d801f1e1c78f100000"],
    "fleur": ["move", "size_all", "all-scroll", "grabbing", "closedhand", "dnd-none",
              "4498f0e0c1937ffe01fd06f973665830", "9081237383d90e509aa00f00170e968f"],
}


def main():
    QGuiApplication([])  # QImage colour handling needs an app instance
    arrow = parse(ARROW)
    hres = parse(H_RESIZE)
    vres = transpose(hres)
    fd = parse(FD_RESIZE)
    move_h = [r.center(15, ".") for r in hres]
    move_h = [["."] * 15 for _ in range(4)] + [list(r) for r in move_h] + [["."] * 15 for _ in range(4)]
    move = merge(["".join(r) for r in move_h], transpose(["".join(r) for r in move_h]))

    jobs = {
        "left_ptr": ([corner(arrow)[0]], corner(arrow)[1], 0),
        "hand2": ([corner(parse(HAND), 3, 1)[0]], (3 + 4, 1 + 1), 0),
        "xterm": ([centered(parse(IBEAM))[0]], centered(parse(IBEAM))[1], 0),
        "crosshair": ([centered(crosshair())[0]], centered(crosshair())[1], 0),
        "not-allowed": ([centered(not_allowed())[0]], centered(not_allowed())[1], 0),
        "sb_h_double_arrow": ([centered(hres)[0]], centered(hres)[1], 0),
        "sb_v_double_arrow": ([centered(vres)[0]], centered(vres)[1], 0),
        "fd_double_arrow": ([centered(fd)[0]], centered(fd)[1], 0),
        "bd_double_arrow": ([centered(mirror(fd))[0]], centered(mirror(fd))[1], 0),
        "fleur": ([centered(move)[0]], centered(move)[1], 0),
    }
    spin = [centered(spinner(i))[0] for i in range(8)]
    jobs["watch"] = (spin, centered(spinner(0))[1], 90)
    prog = []
    for i in range(8):
        cv = blank(BASE, BASE)
        place(cv, arrow, 2, 1)
        place(cv, spinner(i, n=11, radius=3, block=2), 12, 12)
        prog.append(cv)
    jobs["left_ptr_watch"] = (prog, (2, 1), 90)

    if DEST.exists():
        shutil.rmtree(DEST)
    cur = DEST / "cursors"
    cur.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for name, (frames, hot, delay) in jobs.items():
            build(name, frames, hot, tmp, cur, delay)
        save_png(jobs["left_ptr"][0][0], 2, DEST / "preview.png")
    made = set(jobs)
    for target, names in ALIASES.items():
        for n in names:
            if n not in made and not (cur / n).exists():
                (cur / n).symlink_to(target)
    (DEST / "index.theme").write_text(
        "[Icon Theme]\nName=Silver Wolf\nComment=Pixel cursors in Silver Wolf violet\n"
        "Inherits=breeze_cursors\n")
    (DEST / "cursor.theme").write_text("[Icon Theme]\nInherits=SilverWolf\n")
    print("installed", DEST, "-", len(list(cur.iterdir())), "cursor names")


if __name__ == "__main__":
    main()
