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
MAX_LEN = 400  # her longest (the cartridge story) is ~300; the bubble widens for long ones

# companion situation -> wiki section titles (exact). Everyday situations ADD her
# lines to the ones already there; the LV.999 moments REPLACE the placeholders.
ADD = {
    "morning": ["Greeting"], "afternoon": ["Greeting"], "evening": ["Greeting"],
    "wake": ["Greeting", "Added to Team With ( Trailblazer )"],       # back from suspend / sleepy hours
    "quit": ["Parting"],
    "afk": ["Turn Idling", "Added to Team With Herta", "Added to Team With Firefly"],
    "levelup": ["Eidolon Activation", "Character Ascension", "Trace Activation", "Battle Won"],
    "levelup_big": ["Max Level Reached"],                               # every 10th level
    "drag": ["Added to Team With Evanescia"],
    "cpu_high": ["Added to Team With Blade"],
    "gpu_busy": ["Battle Begins: Weakness Break", "Added to Team With Himeko • Nova"],
    "net_down": ["Hit by Heavy Attack"],
    "charging": ["Return to Battle"],
    "battery_low": ["Battle Begins: Danger Alert"],
    "battery_critical": ["Downed"],
    "drive": ["Health Recovery"],
    "download": ["Treasure Opening"],
    "download_big": ["Precious Treasure Opening"],
}
# the fun ones: her takes on everyone else, and the long stories. She tells
# these in her idle chatter, both as LV.999 and as everyday Silver Wolf.
STORIES = ["About Self: \"LV.999\" Cartridge", "About Self: Combat", "Something to Share", "Knowledge",
           "About ( Trailblazer )", "About Blade", "About Firefly", "About Kafka", "About The Herta",
           "About Sparxie", "About Yao Guang", "About Ashveil", "About Pearl", "About Evanescia",
           "About Himeko • Nova", "Added to Team With Ashveil", "Added to Team With Yao Guang",
           "Added to Team With Sparxie", "Added to Team With Mortenax Blade", "Added to Team With Pearl"]
ADD["idle"] = STORIES

REPLACE = {
    "sw999_first": ["First Meeting"],                                   # her very first transformation
    "sw999_hello": ["Technique", "Added to Team With Silver Wolf", "Added to Team With The Herta"],
    "sw999_idle": ["Hobbies", "Annoyances", "Chat: Hacking", "Chat: Phantasmoon Games", "About Elio",
                   "Character Idles", "About Mortenax Blade Non-Existent State", "Chat: Current Situation"]
                  + STORIES,
    "sw999_on": ["Ultimate: Activate", "Enhanced Elation Skill", "Enhanced Basic ATK", "Skill"],
    "sw999_boop": ["Basic ATK", "Hit by Light Attack", "Enemy Target Found", "Turn Begins"],
    "sw999_godoff": ["Elation Skill", "Successful Puzzle-Solving"],
    "sw999_eject_early": ["Added to Team With Kafka"],                  # you ejected the cartridge yourself
    "sw999_off": ["Returning to Town"],
}


def clean(text):
    m = re.search(r"Actual Voice-Over:\s*(.*?)\s*\)\s*$", text)
    if m:
        text = m.group(1)
    text = text.split("(2×)")[0]                    # drop the 2x-speed repeat
    text = re.sub(r"▶\s*\S+", "", text)            # audio links
    text = re.sub(r"\((?:System Sound \d+|2×|Not recorded in Profile)\)", "", text)
    text = re.sub(r"\(\s*Trailblazer\s*\)", "Trailblazer", text)
    text = re.sub(r"\s+([,.!?…:;])", r"\1", text)
    text = re.sub(r'"\s+([^"\s][^"]*?)\s*"', r'"\1"', text)  # wiki links leave '" Zero "' padding
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
    def pick(table):
        out = {}
        for moment, titles in table.items():
            got = [lines[t] for t in titles if lines.get(t) and len(lines[t]) <= MAX_LEN]
            missing = [t for t in titles if t not in lines]
            if missing:
                print("not found on the page:", missing)
            out[moment] = got
        return out
    out = {"add": pick(ADD), "replace": pick(REPLACE)}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print("wrote", OUT, sum(len(v) for t in out.values() for v in t.values()), "lines")


if __name__ == "__main__":
    main()
