"""Eval tasks for taking an edit apart: when each picture of a collage appears, where, and the flash.

Two tasks, both in the AgenticVBench layout so `bench/avb/run.py` runs them like any benchmark task:

- `hook-collage-synthetic`: a generated vertical hook whose answer is known from how it was made. Its video
  is committed with the task.
- `hook-collage-reel`: a real reel whose hook builds the same way. Its video is not committed; fetch it with
  `python -m bench.avb.hook fetch` (needs yt-dlp and network access to the post). Its answer was measured
  with `events` and confirmed by eye on a sheet of the first 1.6 seconds at 15 frames a second.

`python -m bench.avb.hook make` writes the synthetic video, the answers and the reference solutions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
TASKS = HERE / "tasks" / "uberseek_hook"
REPO = HERE.parent.parent
REEL = "https://www.instagram.com/reel/Dc5LK82saLG/"
REEL_FILE = REPO / "data" / "reference" / "collage-reel.mp4"

RATE, WIDTH, HEIGHT, COLUMNS = 30, 540, 960, 6
# (first frame it shows, its column counted from the left at 0): not left to right, so order must be read.
STRIPS = [(12, 0), (18, 2), (24, 1), (30, 3), (36, 5), (42, 4)]
FLASH = (54, 2)  # first frame and how many frames: a white shape over the middle
TITLE = 90  # the frame where the picture cuts to a title card
LENGTH = 4  # seconds

ANSWERS = {
    "hook-collage-synthetic": {
        "strips": [{"t": round(frame / RATE, 3), "column": column} for frame, column in STRIPS],
        "flash": round(FLASH[0] / RATE, 3),
        "title": round(TITLE / RATE, 3),
    },
    # Measured with `events` (each strip's first frame at 60 frames a second) and seen on a 15 fps sheet.
    "hook-collage-reel": {
        "strips": [{"t": t, "column": c} for c, t in enumerate([0.183, 0.35, 0.517, 0.683, 0.883, 1.05])],
        "flash": 1.433,
        "title": None,  # not graded: it comes after closing bars, and its first frame was not pinned down
    },
}


def synthetic(out: Path) -> Path:
    """The generated hook: a moving picture, six strips that pop in one by one, a two-frame flash, a title card."""
    sources = ["smptebars", "rgbtestsrc", "smptehdbars", "yuvtestsrc", "testsrc", "color=c=0xe08020"]  # each unlike the background
    width = WIDTH // COLUMNS
    inputs = ["-f", "lavfi", "-i", f"testsrc2=size={WIDTH}x{HEIGHT}:rate={RATE}:duration={LENGTH}"]
    for source in sources:
        inputs += ["-f", "lavfi", "-i", f"{source}{':' if '=' in source else '='}size={width}x{HEIGHT}:rate={RATE}:duration={LENGTH}"]
    inputs += ["-f", "lavfi", "-i", f"color=c=white:size=200x420:rate={RATE}:duration={LENGTH}"]
    inputs += ["-f", "lavfi", "-i", f"color=c=0x101418:size={WIDTH}x{HEIGHT}:rate={RATE}:duration={LENGTH}"]
    graph, last = [], "0:v"
    for i, (frame, column) in enumerate(STRIPS):
        graph.append(f"[{last}][{i + 1}:v]overlay=x={column * width}:y=0:enable='gte(n,{frame})'[s{i}]")
        last = f"s{i}"
    flash_in, card = len(sources) + 1, len(sources) + 2
    end = FLASH[0] + FLASH[1] - 1
    graph.append(f"[{last}][{flash_in}:v]overlay=x=170:y=270:enable='between(n,{FLASH[0]},{end})'[f]")
    graph.append(f"[{card}:v]drawbox=x=60:y=400:w=420:h=120:color=0xd02020:t=fill[c]")
    graph.append(f"[f][c]overlay=enable='gte(n,{TITLE})',format=yuv420p[v]")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", "[v]",
         "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-g", str(RATE), "-threads", "1", str(out)],
        check=True,
    )  # fmt: skip
    return out


def make() -> None:
    for name, answer in ANSWERS.items():
        tests, solution = TASKS / name / "steps" / "solve" / "tests", TASKS / name / "steps" / "solve" / "solution"
        tests.mkdir(parents=True, exist_ok=True)
        solution.mkdir(parents=True, exist_ok=True)
        (tests / "answer.json").write_text(json.dumps(answer, indent=1) + "\n")
        (solution / "solve.sh").write_text(
            "#!/bin/bash\n# Reference solution: the answer, written where the task asks.\nset -euo pipefail\nmkdir -p /workspace/output\n"
            f"cat > /workspace/output/answer.json <<'EOF'\n{json.dumps(answer)}\nEOF\n"
        )
    materials = TASKS / "hook-collage-synthetic" / "materials"
    materials.mkdir(exist_ok=True)
    synthetic(materials / "hook.mp4")


def fetch() -> None:
    REEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["yt-dlp", "-o", str(REEL_FILE.with_suffix(".%(ext)s")), "--merge-output-format", "mp4", REEL], check=True)


if __name__ == "__main__":
    {"make": make, "fetch": fetch}[sys.argv[1] if len(sys.argv) > 1 else "make"]()
