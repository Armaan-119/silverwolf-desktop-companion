#!/usr/bin/env python3
"""Build the full-size LV.999 form images in ../forms/ from a reference shot.

    python3 tools/make_sw999_form.py [References/Character_Silver_Wolf_LV.999_Game.webp]

Needs:  pip install "rembg[cpu]" opencv-python-headless pillow
(rembg downloads its isnet-anime model, ~176 MB, on first run.)

Writes (all git-ignored: the art is HoYoverse's, keep it local):
  forms/sw999.png          her, cut out of the background
  forms/sw999_novisor.png  same, with the visor on her head painted out
  forms/sw999_visor.png    just the visor, so it can slide down onto her eyes
  forms/sw999.json         where the visor, eyes and wing root are (fractions)

The visor outline and eye position below are measured on the in-game model
screenshot (850x1511). For a different picture, re-measure them.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "References" / "Character_Silver_Wolf_LV.999_Game.webp"
OUT = ROOT / "forms"

# measured on the 850x1511 in-game screenshot (source pixels)
VISOR_POLY = [(333, 140), (350, 127), (395, 124), (420, 128), (445, 124), (500, 126), (517, 132),
              (526, 150), (523, 182), (510, 182), (500, 172), (470, 176), (440, 170), (430, 158),
              (418, 160), (410, 173), (380, 177), (355, 172), (342, 180), (330, 176)]
VISOR_BOX = (322, 116, 532, 188)
EYES = (427, 245, 150)      # centre x, centre y, width across both eyes
WING_ROOT = (425, 520)      # between the shoulder blades


def main():
    OUT.mkdir(exist_ok=True)
    print("cutting out", SRC.name, "...")
    cut = remove(Image.open(SRC).convert("RGB"), session=new_session("isnet-anime"))
    im = np.array(cut.convert("RGBA"))
    rgb, a = im[:, :, :3].copy(), im[:, :, 3]

    # paint the visor out of her hair
    poly = np.array(VISOR_POLY, np.int32)
    shape = np.zeros(a.shape, np.uint8)
    cv2.fillPoly(shape, [poly], 255)
    mask = shape.copy()
    mask[:126, 340:385] = 0  # keep the cyan hair spikes above it
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=2) & np.where(a > 0, 255, 0).astype(np.uint8)
    fixed = cv2.inpaint(rgb, mask, 9, cv2.INPAINT_TELEA)
    below = np.roll(fixed, -48, axis=0)  # faint strand texture from the hair just below
    mf = cv2.GaussianBlur(mask, (9, 9), 0).astype(np.float32)[:, :, None] / 255.0
    fixed = (fixed * (1 - 0.35 * mf) + below * (0.35 * mf)).astype(np.uint8)
    a2 = a.copy()
    cols = np.arange(a.shape[1])
    a2[(shape > 0) & ((cols < 338) | (cols > 515))[None, :]] = 0  # hinges stuck out past her hair

    visor = np.dstack([rgb, np.where(cv2.dilate(mask, np.ones((3, 3), np.uint8)) > 0, a, 0)]).astype(np.uint8)

    # crop everything to her silhouette
    x0, y0, x1, y1 = Image.fromarray(a).getbbox()
    w, h = x1 - x0, y1 - y0
    Image.fromarray(im).crop((x0, y0, x1, y1)).save(OUT / "sw999.png")
    Image.fromarray(np.dstack([fixed, a2])).crop((x0, y0, x1, y1)).save(OUT / "sw999_novisor.png")
    Image.fromarray(visor).crop(VISOR_BOX).save(OUT / "sw999_visor.png")

    vx0, vy0, vx1, vy1 = VISOR_BOX
    meta = dict(
        visor=[(vx0 - x0) / w, (vy0 - y0) / h, (vx1 - vx0) / w, (vy1 - vy0) / h],  # x, y, w, h
        eyes=[(EYES[0] - x0) / w, (EYES[1] - y0) / h, EYES[2] / w],               # x, y, width
        back=[(WING_ROOT[0] - x0) / w, (WING_ROOT[1] - y0) / h],
    )
    (OUT / "sw999.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("wrote", ", ".join(p.name for p in sorted(OUT.glob("sw999*"))), f"({w}x{h})")


if __name__ == "__main__":
    main()
