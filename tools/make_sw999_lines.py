#!/usr/bin/env python3
"""Pull Silver Wolf LV.999's voice lines from a saved copy of her wiki
Voice-Overs page into forms/sw999_lines.json, for her speech bubbles.

    python3 tools/make_sw999_lines.py ["References/Silver Wolf LV.999's English Voice-Overs _ ... .html"]

The lines are HoYoverse's text, so the output stays local (git-ignored);
this script only knows which wiki section goes with which moment.
"(Trailblazer)" becomes "Trailblazer": that's you.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "References"
OUT = ROOT / "forms" / "sw999_lines.json"
MAX_LEN = 170  # longer lines make huge bubbles

# wiki section title (prefix match) -> companion moment
MOMENTS = {
    "sw999_hello": ["First Meeting", "Technique", "Max Level Reached", "Added to Team With ( Trailblazer )",
                    "Greeting"],
    "sw999_idle": ["Hobbies", "Annoyances", "About Self: Combat", "Chat: Hacking", "Chat: Phantasmoon",
                   "About Elio", "Turn Idling", "Character Idles", "Character Ascension", "Trace Activation",
                   "Added to Team With Silver Wolf", "About Mortenax", "Eidolon Activation",
                   "About ( Trailblazer )", "Chat: Current Situation", "Added to Team With Kafka"],
    "sw999_on": ["Ultimate: Activate", "Enhanced Elation Skill", "Enhanced Basic ATK", "Skill"],
    "sw999_boop": ["Basic ATK", "Hit by Light Attack", "Enemy Target Found", "Battle Begins: Danger Alert",
                   "Battle Begins: Weakness Break", "Turn Begins", "Hit by Heavy Attack"],
    "sw999_godoff": ["Battle Won", "Elation Skill", "Successful Puzzle-Solving", "Return to Battle"],
    "sw999_off": ["Returning to Town", "Parting"],
}


def clean(text):
    m = re.search(r"Actual Voice-Over:\s*(.*?)\s*\)\s*$", text)
    if m:
        text = m.group(1)
    text = text.split("(2×)")[0]                    # drop the 2x-speed repeat
    text = re.sub(r"▶\s*\S+", "", text)            # audio links
    text = re.sub(r"\((?:System Sound \d+|2×|Not recorded in Profile)\)", "", text)
    text = re.sub(r"\(\s*Trailblazer\s*\)", "Trailblazer", text)
    text = re.sub(r"\s+([,.!?…])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else next(REF.glob("*English Voice-Overs*.html"))
    page = src.read_text(encoding="utf-8", errors="ignore")
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S)
    lines = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            lines.setdefault(cells[0], clean(cells[-1]))
    out = {}
    for moment, titles in MOMENTS.items():
        picked = []
        for t in titles:
            for title, text in lines.items():
                if title.startswith(t) and text and len(text) <= MAX_LEN and text not in picked:
                    picked.append(text)
        out[moment] = picked
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print("wrote", OUT, {k: len(v) for k, v in out.items()})


if __name__ == "__main__":
    main()
