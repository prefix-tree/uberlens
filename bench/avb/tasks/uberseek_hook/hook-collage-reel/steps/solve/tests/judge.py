#!/usr/bin/env python3
"""Score an answer about how a collage hook is built: each strip's time and column, the flash, the title.

A strip counts when its time is within 0.1 s of a true strip's and its column is the same; each true strip
matches at most one answered. The flash and the title count when within 0.1 s. Weights: strips 0.6, flash
0.2, title 0.2; when the title is not graded, strips 0.8 and flash 0.2.
"""

import argparse
import json
from pathlib import Path

TOLERANCE = 0.1

parser = argparse.ArgumentParser()
parser.add_argument("--answer")
parser.add_argument("--truth")
parser.add_argument("--reward-json")
args = parser.parse_args()
truth = json.loads(Path(args.truth).read_text())
out = Path(args.reward_json)
out.parent.mkdir(parents=True, exist_ok=True)
try:
    answer = json.loads(Path(args.answer).read_text())
    strips = [(float(s["t"]), int(s["column"])) for s in answer.get("strips", [])]
except (OSError, ValueError, KeyError, TypeError) as error:
    out.write_text(json.dumps({"reward": 0.0, "details": {"reason": f"no usable answer: {error}"}}))
    raise SystemExit(0) from None

left, matched = list(strips), []
for true in truth["strips"]:
    near = [s for s in left if s[1] == true["column"] and abs(s[0] - true["t"]) <= TOLERANCE]
    if near:
        best = min(near, key=lambda s: abs(s[0] - true["t"]))
        left.remove(best)
        matched.append({"truth": true, "answered": best})
share = len(matched) / max(len(truth["strips"]), len(strips))


def close(key):
    value = answer.get(key)
    return value is not None and abs(float(value) - truth[key]) <= TOLERANCE


flash = close("flash")
graded = truth.get("title") is not None
title = close("title") if graded else None
reward = (0.6 * share + 0.2 * flash + 0.2 * bool(title)) if graded else (0.8 * share + 0.2 * flash)
details = {
    "strips_matched": len(matched),
    "strips_true": len(truth["strips"]),
    "strips_answered": len(strips),
    "flash": flash,
    "title": title,
    "answer": answer,
}
out.write_text(json.dumps({"reward": round(reward, 4), "details": details}))
