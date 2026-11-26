"""Eval tasks for taking an edit apart: when each picture of a collage appears, where, and the flash.

Three tasks, all in the AgenticVBench layout so `bench/avb/run.py` runs them like any benchmark task:

- `hook-collage-synthetic`: a generated vertical hook whose answer is known from how it was made.
- `hook-collage-hard`: the same, made hard enough to tell an agent with UberSeek from one without: 60 frames a
  second, nine strips at uneven gaps, two that fade in, a one-frame flash, a moving distractor, and times
  judged to just over one frame. The generated videos are made when missing, not committed.
- `hook-collage-reel`: a real reel whose hook builds the same way. Its video is not committed; fetch it with
  `python -m bench.avb.hook fetch` (needs yt-dlp and network access to the post). Its answer was measured
  with `events` and confirmed by eye on a sheet of the first 1.6 seconds at 15 frames a second.

`python -m bench.avb.hook make` writes the synthetic video, the answers and the reference solutions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
TASKS = HERE / "tasks" / "uberseek_hook"
REPO = HERE.parent.parent
REEL = "https://www.instagram.com/reel/Dc5LK82saLG/"
REEL_FILE = REPO / "data" / "reference" / "collage-reel.mp4"

WIDTH, HEIGHT, LENGTH = 540, 960, 4


@dataclass(frozen=True)
class Hook:
    """A generated hook: strips that appear one at a time in columns, a flash, a title card."""

    rate: int
    columns: int
    strips: list[tuple[int, int, int]]  # (first frame it shows, column from the left at 0, frames it takes to fade in; 0 pops)
    flash: tuple[int, int]  # first frame and how many frames: a white shape over the middle
    title: int  # the frame where the picture cuts to a title card
    tolerance: float  # how close a reported time must be, in seconds
    ball: bool = False  # a small ball crossing the frame the whole time: motion that is not an event

    def answer(self) -> dict:
        return {
            "strips": [{"t": round(frame / self.rate, 3), "column": column} for frame, column, _ in self.strips],
            "flash": round(self.flash[0] / self.rate, 3),
            "title": round(self.title / self.rate, 3),
            "tolerance": self.tolerance,
        }


HOOKS = {
    # Not left to right, so the order must be read.
    "hook-collage-synthetic": Hook(30, 6, [(12, 0, 0), (18, 2, 0), (24, 1, 0), (30, 3, 0), (36, 5, 0), (42, 4, 0)], (54, 2), 90, 0.1),
    # Harder: 60 frames a second, nine strips at uneven gaps (two only three frames apart), two that fade in,
    # a one-frame flash, a ball crossing the frame throughout, and times judged to just over one frame.
    "hook-collage-hard": Hook(
        60, 9,
        [(20, 4, 0), (31, 0, 0), (38, 7, 8), (52, 2, 0), (55, 8, 0), (70, 1, 0), (78, 5, 10), (96, 3, 0), (101, 6, 0)],
        (130, 1), 180, 0.02, ball=True,
    ),
}  # fmt: skip

ANSWERS = {
    **{name: hook.answer() for name, hook in HOOKS.items()},
    # Measured with `events` (each strip's first frame at 60 frames a second) and seen on a 15 fps sheet.
    # The flash is the white outline replacing the person, which stays for five frames.
    "hook-collage-reel": {
        "strips": [{"t": t, "column": c} for c, t in enumerate([0.183, 0.35, 0.517, 0.683, 0.883, 1.05])],
        "flash": 1.433,
        "title": None,  # not graded: it comes after closing bars, and its first frame was not pinned down
        "tolerance": 0.1,
    },
}

SOURCES = ["smptebars", "rgbtestsrc", "smptehdbars", "yuvtestsrc", "testsrc", "color=c=0xe08020", "color=c=0x2080e0",
           "color=c=0x30c060", "color=c=0xc03090"]  # fmt: skip  # each unlike the background


def synthetic(out: Path, hook: Hook | None = None) -> Path:
    """Write a generated hook: a moving picture, strips that appear one by one, a flash, a title card."""
    hook = hook or HOOKS["hook-collage-synthetic"]
    rate, width = hook.rate, WIDTH // hook.columns
    clock = f"rate={rate}:duration={LENGTH}"
    inputs = ["-f", "lavfi", "-i", f"testsrc2=size={WIDTH}x{HEIGHT}:{clock}"]
    for source in SOURCES[: len(hook.strips)]:
        inputs += ["-f", "lavfi", "-i", f"{source}{':' if '=' in source else '='}size={width}x{HEIGHT}:{clock}"]
    flash_in, card, ball = len(hook.strips) + 1, len(hook.strips) + 2, len(hook.strips) + 3
    inputs += ["-f", "lavfi", "-i", f"color=c=white:size=200x420:{clock}"]
    inputs += ["-f", "lavfi", "-i", f"color=c=0x101418:size={WIDTH}x{HEIGHT}:{clock}"]
    inputs += ["-f", "lavfi", "-i", f"color=c=white:size=36x36:{clock}"]
    graph, last = [], "0:v"
    for i, (frame, column, fade) in enumerate(hook.strips):
        strip = f"{i + 1}:v"
        if fade:
            graph.append(f"[{strip}]format=rgba,fade=t=in:st={frame / rate:.6f}:d={fade / rate:.6f}:alpha=1[a{i}]")
            strip = f"a{i}"
        graph.append(f"[{last}][{strip}]overlay=x={column * width}:y=0:enable='gte(n,{frame})'[s{i}]")
        last = f"s{i}"
    if hook.ball:
        graph.append(f"[{last}][{ball}:v]overlay=x='mod(t*520,{WIDTH})':y='300+200*sin(t*5)'[b]")
        last = "b"
    first, count = hook.flash
    graph.append(f"[{last}][{flash_in}:v]overlay=x=170:y=270:enable='between(n,{first},{first + count - 1})'[f]")
    graph.append(f"[{card}:v]drawbox=x=60:y=400:w=420:h=120:color=0xd02020:t=fill[c]")
    graph.append(f"[f][c]overlay=enable='gte(n,{hook.title})',format=yuv420p[v]")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", "[v]",
         "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-g", str(rate), "-threads", "1", str(out)],
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
    for name, hook in HOOKS.items():
        materials = TASKS / name / "materials"
        materials.mkdir(exist_ok=True)
        synthetic(materials / "hook.mp4", hook)


def fetch() -> None:
    REEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["yt-dlp", "-o", str(REEL_FILE.with_suffix(".%(ext)s")), "--merge-output-format", "mp4", REEL], check=True)


if __name__ == "__main__":
    {"make": make, "fetch": fetch}[sys.argv[1] if len(sys.argv) > 1 else "make"]()
