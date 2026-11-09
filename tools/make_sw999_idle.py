#!/usr/bin/env python3
"""Cut her LV.999 idle animation out of the character-preview GIF.

    python3 tools/make_sw999_idle.py [References/Silver_Wolf_LV.999_Transformation_Start_Character_Preview_Details_05.gif]

Needs:  pip install "rembg[cpu]" opencv-python-headless pillow

Writes (git-ignored, the art is HoYoverse's):
  forms/sw999_idle/000.png ...  every frame, cut out, all on one shared canvas
  forms/sw999_idle.json         frame time, and where her body is in frame 0
"""
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageSequence
from rembg import new_session, remove

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    ROOT / "References" / "Silver_Wolf_LV.999_Transformation_Start_Character_Preview_Details_05.gif"
OUT = ROOT / "forms" / "sw999_idle"
STAGE = (90, 150, 640, 812)  # the starfield stage inside the preview card (720x960)


def keep_her(alpha):
    """Drop stray bits (card icons, stars): keep blobs touching the main body."""
    a = alpha.copy()
    solid = (a > 40).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
    if n <= 1:
        return a
    main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    near = cv2.dilate((lab == main).astype(np.uint8), np.ones((15, 15), np.uint8))
    for i in range(1, n):
        if i != main and not (near & (lab == i)).any():
            a[lab == i] = 0
    return a


def drop_dark_haze(f):
    """The cut-out keeps a dark smudge of starfield around her glowing pixel
    gesture. Real glow is bright, so fade out dark half-transparent pixels."""
    rgb, a = f[:, :, :3].astype(np.float32) / 255, f[:, :, 3].astype(np.float32)
    k = np.clip((rgb.max(axis=2) - 0.22) / 0.25, 0, 1)
    f[:, :, 3] = np.where(a < 235, a * k, a).astype(np.uint8)
    return f


def main():
    sess = new_session("isnet-anime")
    src = Image.open(SRC)
    dur = src.info.get("duration", 100)
    frames = []
    for i, fr in enumerate(ImageSequence.Iterator(src)):
        rgb = fr.convert("RGB").crop(STAGE)
        cut = np.array(remove(rgb, session=sess).convert("RGBA"))
        cut[:, :, 3] = keep_her(cut[:, :, 3])
        frames.append(cut)
        print(f"\rframe {i + 1}/{src.n_frames}", end="", flush=True)
    print()
    # light temporal smoothing of the edges so the cut-out doesn't shimmer
    alphas = np.stack([f[:, :, 3].astype(np.float32) for f in frames])
    sm = alphas.copy()
    sm[1:-1] = 0.25 * alphas[:-2] + 0.5 * alphas[1:-1] + 0.25 * alphas[2:]
    for f, a in zip(frames, sm):
        f[:, :, 3] = np.where(a > 250, 255, a).astype(np.uint8)
        drop_dark_haze(f)
    # one shared canvas for all frames
    union = np.zeros(frames[0].shape[:2], bool)
    for f in frames:
        union |= f[:, :, 3] > 8
    ys, xs = np.nonzero(union)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for i, f in enumerate(frames):
        Image.fromarray(f[y0:y1, x0:x1]).save(OUT / f"{i:03d}.png", optimize=True)
    a0 = frames[0][y0:y1, x0:x1, 3] > 40
    by, bx = np.nonzero(a0)
    W, H = x1 - x0, y1 - y0
    meta = dict(frame_ms=dur, frames=len(frames), size=[int(W), int(H)],
                # her body in frame 0: matches the still form art, used to line the two up
                body=[bx.min() / W, by.min() / H, (bx.max() + 1 - bx.min()) / W, (by.max() + 1 - by.min()) / H])
    (OUT.parent / "sw999_idle.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("wrote", len(frames), "frames", f"{W}x{H}", "->", OUT)


if __name__ == "__main__":
    main()
