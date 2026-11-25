"""A person cut out of their background, frame by frame, with a matting model.

    python -m uberseek.lab.matte take.mov out.webm --rvm <RobustVideoMatting folder> --weights rvm_resnet50.pth

It writes either the matte alone (white where the person is, grey at hair and motion blur), or the person over pure
green, which an editor that has no matte input can key out. The model is RobustVideoMatting (Lin et al., 2021): the
best of seven tried on an interview (see notes/cutout-decision.md). It is GPL-3.0, so it is not in this repository:
clone it and fetch its weights yourself. It also returns its estimate of the person's colour at the edges, used here
so the old background's tint does not come along.

Needs numpy, torch and torchvision. About 0.2 s a frame at 1080p on four CPU cores.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def probe(path: Path, ffprobe: str = "ffprobe") -> tuple[int, int, str]:
    """Width, height and frame rate (as FFmpeg writes it) of the first video stream."""
    out = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    return int(stream["width"]), int(stream["height"]), stream["r_frame_rate"]


def cutout(
    source: Path,
    out: Path,
    rvm: Path,
    weights: Path,
    seconds: float | None = None,
    mode: str = "green",
    variant: str = "resnet50",
    bitrate: str = "9M",
) -> int:
    """Writes the cut-out of `source` to `out` and returns the number of frames. `mode` is "green" or "matte"."""
    import numpy as np
    import torch

    if mode not in ("green", "matte"):
        raise ValueError('mode is "green" (the person over green) or "matte" (the matte alone)')
    sys.path.insert(0, str(rvm))
    from model import MattingNetwork  # RobustVideoMatting's own module

    width, height, rate = probe(source)
    net = MattingNetwork(variant).eval()
    net.load_state_dict(torch.load(weights, map_location="cpu"))
    span = ["-t", str(seconds)] if seconds else []
    reader = subprocess.Popen(
        ["ffmpeg", "-v", "error", *span, "-i", str(source), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE
    )
    writer = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", rate, "-i", "-"]
        + ["-c:v", "libvpx-vp9", "-b:v", bitrate, "-g", "24", "-deadline", "good", "-cpu-used", "4", "-row-mt", "1"]
        + ["-pix_fmt", "yuv420p", "-an", str(out)],
        stdin=subprocess.PIPE,
    )
    assert reader.stdout is not None and writer.stdin is not None
    green = torch.tensor([0.0, 1.0, 0.0]).view(3, 1, 1)
    # The model works on a smaller copy and refines the edge at full size. A quarter is what was used at 1080p.
    ratio = 0.25 if min(width, height) >= 720 else 0.5
    state = [None] * 4
    frames = 0
    with torch.no_grad():
        while True:
            raw = reader.stdout.read(width * height * 3)
            if len(raw) < width * height * 3:
                break
            frame = torch.from_numpy(np.frombuffer(raw, np.uint8).reshape(height, width, 3).copy())
            x = frame.permute(2, 0, 1).float().div(255).unsqueeze(0)
            if frames == 0:
                # The model is recurrent and starts cold: the first frame is run a few times so it has settled.
                for _ in range(6):
                    _, _, *state = net(x, *state, downsample_ratio=ratio)
            colour, alpha, *state = net(x, *state, downsample_ratio=ratio)
            picture = alpha[0].expand(3, -1, -1) if mode == "matte" else colour[0] * alpha[0] + green * (1 - alpha[0])
            writer.stdin.write((picture.clamp(0, 1) * 255).byte().permute(1, 2, 0).numpy().tobytes())
            frames += 1
    writer.stdin.close()
    writer.wait()
    return frames


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A person cut out of their background.")
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--rvm", type=Path, required=True, help="a clone of github.com/PeterL1n/RobustVideoMatting")
    parser.add_argument("--weights", type=Path, required=True, help="rvm_resnet50.pth or rvm_mobilenetv3.pth")
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--mode", choices=["green", "matte"], default="green")
    parser.add_argument("--variant", choices=["resnet50", "mobilenetv3"], default="resnet50")
    given = parser.parse_args()
    made = cutout(given.source, given.out, given.rvm, given.weights, given.seconds, given.mode, given.variant)
    print(f"{given.out}: {made} frames")
