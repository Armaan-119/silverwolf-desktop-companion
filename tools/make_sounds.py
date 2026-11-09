#!/usr/bin/env python3
"""Generate Silver Wolf's chiptune sound effects into ../sounds/*.wav.

Pure numpy square/triangle/noise synthesis, so nothing is downloaded.
Re-run after tweaking to regenerate:  python3 tools/make_sounds.py
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "sounds"
VOLUME = 0.32  # keep them quiet; they play over whatever you're doing


def note(n):
    """MIDI note number -> Hz."""
    return 440.0 * 2 ** ((n - 69) / 12)


def tone(freq, dur, wave_="square", duty=0.5, slide=0.0, vib=0.0):
    t = np.arange(int(SR * dur)) / SR
    f = freq * (1 + slide * t / max(dur, 1e-6))
    if vib:
        f = f * (1 + 0.012 * np.sin(2 * np.pi * vib * t))
    ph = np.cumsum(f) / SR % 1.0
    if wave_ == "square":
        s = np.where(ph < duty, 1.0, -1.0)
    elif wave_ == "tri":
        s = 4 * np.abs(ph - 0.5) - 1
    elif wave_ == "noise":
        rng = np.random.default_rng(7)
        steps = rng.uniform(-1, 1, int(dur * freq) + 2)
        s = steps[(t * freq).astype(int)]
    else:
        s = np.sin(2 * np.pi * ph)
    return s


def env(n, a=0.004, r=0.05, dur=None):
    e = np.ones(n)
    na, nr = int(SR * a), int(SR * r)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def seq(notes, step, wave_="square", duty=0.5, gap=0.0, rel=0.03):
    parts = []
    for n in notes:
        if n is None:
            parts.append(np.zeros(int(SR * step)))
            continue
        s = tone(note(n), step - gap, wave_, duty)
        parts.append(s * env(len(s), r=rel))
        if gap:
            parts.append(np.zeros(int(SR * gap)))
    return np.concatenate(parts)


def mix(*tracks):
    n = max(len(t) for t in tracks)
    out = np.zeros(n)
    for t in tracks:
        out[:len(t)] += t
    return out


def save(name, s):
    s = s / max(1e-9, np.max(np.abs(s))) * VOLUME
    data = (s * 32767).astype(np.int16)
    OUT.mkdir(exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote", OUT / f"{name}.wav", f"{len(s) / SR:.2f}s")


def main():
    # boop: tiny upward chirp
    s = tone(note(76), 0.08, "square", 0.25, slide=0.9)
    save("boop", s * env(len(s), r=0.04))

    # pop: noise burst + falling blip
    a = tone(3000, 0.05, "noise")
    b = tone(note(84), 0.07, "square", 0.125, slide=-0.6)
    save("pop", mix(a * env(len(a), r=0.04) * 0.6, b * env(len(b), r=0.05)))

    # speak: soft two-step "terminal" blip
    save("speak", seq([81, 88], 0.045, "square", 0.25, rel=0.02) * 0.7)

    # levelup: classic arpeggio + held chord
    lead = seq([72, 76, 79, 84, 79, 84, 88], 0.07, "square", 0.25, gap=0.008)
    hold = tone(note(91), 0.35, "square", 0.25, vib=6)
    lead = np.concatenate([lead, hold * env(len(hold), r=0.25)])
    bass = seq([48, None, 55, None, 60, None, 60], 0.07, "tri") * 0.8
    save("levelup", mix(lead, bass))

    # loot: coin-ish double ping (download finished, drive plugged)
    save("loot", seq([83, 88], 0.09, "square", 0.5, rel=0.06))

    # warn: low glitchy two-tone alarm (battery low, overheating)
    w = seq([64, 58, 64, 58], 0.11, "square", 0.5, gap=0.02)
    n = tone(1800, len(w) / SR, "noise") * 0.15
    save("warn", mix(w, n * env(len(n), r=0.1)))

    # glitch: short bitcrushed sweep (GPU stress, reconnect)
    g = tone(note(96), 0.18, "square", 0.5, slide=-0.85)
    g = np.round(g * 3) / 3
    save("glitch", g * env(len(g), r=0.08))

    # connect / disconnect
    save("online", seq([67, 74, 79], 0.06, "square", 0.25))
    save("offline", seq([79, 74, 67], 0.07, "square", 0.25))

    # transform: rising charge (sweep + quickening arpeggio) into a big held chord (SW999)
    sweep = tone(note(48), 1.3, "square", 0.25, slide=3.0)
    sweep = np.round(sweep * 4) / 4 * np.linspace(0.2, 1.0, len(sweep))
    arp = np.concatenate([seq([60, 67, 72, 79], st, "square", 0.125, rel=0.01)
                          for st in (0.09, 0.07, 0.05, 0.035)])
    charge = mix(sweep * 0.5, arp * 0.6)
    burst = tone(4000, 0.12, "noise")
    chord = mix(*(tone(note(n), 0.6, "square", 0.25, vib=7) for n in (72, 79, 84, 91)))
    chord = chord * env(len(chord), r=0.45) * 0.7
    bass = tone(note(36), 0.6, "tri")
    hit = mix(burst * env(len(burst), r=0.1) * 0.8, chord, bass * env(len(bass), r=0.4))
    save("transform", np.concatenate([charge, hit]))

    # revert: power-down slide + falling arpeggio
    down = tone(note(84), 0.5, "square", 0.25, slide=-0.75)
    down = np.round(down * 3) / 3
    fall = seq([79, 72, 67, 60], 0.07, "square", 0.25)
    save("revert", np.concatenate([down * env(len(down), r=0.1) * 0.6, fall]))


if __name__ == "__main__":
    main()
