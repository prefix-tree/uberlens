"""Several matting models on the same frames, side by side and in numbers.

    python -m uberseek.lab.matte_compare take.mov --start 16.2 --models models/ --rvm RobustVideoMatting/ --out out/

It runs each model it can find on the same four seconds, saves each one's matte, and writes `compare.png` (hair on
white, hands on white, the whole frame on a colour) and `compare.json`: seconds per frame, the share of each frame
that is a soft edge, how much the matte changes from frame to frame, and, when the background has one saturated
colour (`--wall blue`), how much of that colour is inside the cut-out, which is background leaking through.

The models, and where their files come from (none is in this repository; `--models` is the folder they are in):

| Name | File | Licence |
|---|---|---|
| rvm-mobilenet, rvm-resnet50 | `rvm_mobilenetv3.pth`, `rvm_resnet50.pth` (RobustVideoMatting releases) | GPL-3.0 |
| u2net-human | `u2net_human_seg.onnx` (rembg releases) | Apache-2.0 |
| isnet | `isnet-general-use.onnx` (rembg releases) | not checked |
| birefnet-portrait | `BiRefNet-portrait-epoch_150.onnx` (rembg releases) | MIT |
| mp-selfie, mp-multiclass | MediaPipe's `selfie_segmenter.tflite`, `selfie_multiclass_256x256.tflite` | Apache-2.0 |

Needs numpy and opencv, and per model: torch and torchvision (rvm), onnxruntime (the ONNX ones), mediapipe.
BiRefNet at 1080p needs a GPU: on a CPU it took 47 s a frame and ran out of memory on video, so it runs on a few
frames only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

RUN_IN = 12  # frames a recurrent model sees before the ones that count
WALLS = {"blue": 2, "green": 1, "red": 0}
IMAGENET = ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])


def read_frames(source: Path, start: float, count: int, width: int, height: int):
    import numpy as np

    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-frames:v",
            str(count),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, height, width, 3)


def run_rvm(frames, weights: Path, rvm: Path, variant: str):
    import torch

    sys.path.insert(0, str(rvm))
    from model import MattingNetwork

    net = MattingNetwork(variant).eval()
    net.load_state_dict(torch.load(weights, map_location="cpu"))
    state = [None] * 4
    mattes = []
    started = time.time()
    with torch.no_grad():
        for i, frame in enumerate(frames):
            if i == RUN_IN:
                started = time.time()
            x = torch.from_numpy(frame.copy()).permute(2, 0, 1).float().div(255).unsqueeze(0)
            _, alpha, *state = net(x, *state, downsample_ratio=0.25)
            if i >= RUN_IN:
                mattes.append(alpha[0, 0].numpy().copy())
    return mattes, (time.time() - started) / len(mattes), 1


def run_onnx(frames, model: Path, size: int, mean, std, sigmoid: bool = False, every: int = 1):
    import cv2
    import numpy as np
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(model), options, providers=["CPUExecutionProvider"])
    name = session.get_inputs()[0].name
    height, width = frames.shape[1:3]
    mean, std = np.array(mean, np.float32), np.array(std, np.float32)
    mattes, last, ran = [], None, 0
    started = time.time()
    for i, frame in enumerate(frames[RUN_IN:]):
        if i % every == 0:
            x = cv2.resize(frame, (size, size), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
            x = ((x / max(x.max(), 1e-6) - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)
            y = session.run(None, {name: x})[0][0, 0]
            if sigmoid:
                y = 1 / (1 + np.exp(-y))
            y = (y - y.min()) / max(y.max() - y.min(), 1e-6)
            last = cv2.resize(y, (width, height), interpolation=cv2.INTER_LINEAR)
            ran += 1
        mattes.append(last)
    return mattes, (time.time() - started) / ran, every


def run_mediapipe(frames, model: Path, foreground_first: bool):
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks import python as tasks
    from mediapipe.tasks.python import vision

    options = vision.ImageSegmenterOptions(base_options=tasks.BaseOptions(model_asset_path=str(model)), output_confidence_masks=True)
    segmenter = vision.ImageSegmenter.create_from_options(options)
    height, width = frames.shape[1:3]
    mattes = []
    started = time.time()
    for frame in frames[RUN_IN:]:
        result = segmenter.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame)))
        mask = result.confidence_masks[0].numpy_view().astype(np.float32).reshape(height, width)
        mattes.append(mask if foreground_first else 1 - mask)
    return mattes, (time.time() - started) / len(mattes), 1


def runners(models: Path, rvm: Path | None) -> dict:
    """Each model whose file is present, as a function of the frames."""
    found = {}

    def have(name: str) -> Path | None:
        path = models / name
        return path if path.exists() else None

    if (path := have("selfie_segmenter.tflite")) is not None:
        found["mp-selfie"] = lambda f, p=path: run_mediapipe(f, p, True)
    if (path := have("selfie_multiclass_256x256.tflite")) is not None:
        found["mp-multiclass"] = lambda f, p=path: run_mediapipe(f, p, False)
    if (path := have("u2net_human_seg.onnx")) is not None:
        found["u2net-human"] = lambda f, p=path: run_onnx(f, p, 320, *IMAGENET)
    if (path := have("isnet-general-use.onnx")) is not None:
        found["isnet"] = lambda f, p=path: run_onnx(f, p, 1024, [0.5] * 3, [1.0] * 3)
    if rvm is not None:
        if (path := have("rvm_mobilenetv3.pth")) is not None:
            found["rvm-mobilenet"] = lambda f, p=path: run_rvm(f, p, rvm, "mobilenetv3")
        if (path := have("rvm_resnet50.pth")) is not None:
            found["rvm-resnet50"] = lambda f, p=path: run_rvm(f, p, rvm, "resnet50")
    if (path := have("BiRefNet-portrait-epoch_150.onnx")) is not None:
        found["birefnet-portrait"] = lambda f, p=path: run_onnx(f, p, 1024, *IMAGENET, sigmoid=True, every=32)
    return found


def numbers(frames, mattes, wall: str | None) -> dict:
    """What can be measured of a matte without a ground truth."""
    import numpy as np

    picks = range(0, len(mattes), max(1, len(mattes) // 3))
    soft = float(np.mean([((mattes[i] > 0.05) & (mattes[i] < 0.95)).mean() for i in picks])) * 100
    change = float(np.mean([np.abs(mattes[i] - mattes[i - 1]).mean() for i in range(1, len(mattes), 3)])) * 255
    out = {"soft_edge_percent": round(soft, 2), "change_per_frame": round(change, 2)}
    if wall:
        leaks = []
        for i in picks:
            frame = frames[RUN_IN + i].astype(np.float32)
            colour = frame[..., WALLS[wall]]
            others = np.delete(frame, WALLS[wall], axis=2).max(axis=2)
            is_wall = (colour > 90) & ((colour - others) > 0.48 * colour)
            inside = mattes[i] > 0.5
            leaks.append((is_wall & inside).sum() / max(inside.sum(), 1))
        out["wall_in_cutout_percent"] = round(float(np.mean(leaks)) * 100, 2)
    return out


def sheet(frames, results: dict, out: Path, colour=(13, 44, 245)) -> None:
    """One row per model: hair on white, hands on white (both black and white), and the whole frame on a colour."""
    import cv2
    import numpy as np

    height, width = frames.shape[1:3]
    count = len(next(iter(results.values()))["mattes"])
    picks = [count // 10, count // 2, count * 5 // 6]

    def on(i: int, matte, ground, mono: bool):
        frame = frames[RUN_IN + i].astype(np.float32)
        if mono:
            grey = np.clip((frame @ np.array([0.299, 0.587, 0.114], np.float32) - 128) * 1.25 + 128, 0, 255)
            frame = np.stack([grey] * 3, -1)
        return (frame * matte[..., None] + np.array(ground, np.float32) * (1 - matte[..., None])).astype(np.uint8)

    rows = []
    for name, result in results.items():
        mattes = result["mattes"]
        hair = on(picks[0], mattes[picks[0]], (255, 255, 255), True)[: height * 2 // 5, width // 3 : width * 2 // 3]
        hands = on(picks[1], mattes[picks[1]], (255, 255, 255), True)[height // 2 :, width // 4 : width * 3 // 4]
        whole = on(picks[2], mattes[picks[2]], colour, False)
        cells = [cv2.resize(c, (int(c.shape[1] * 480 / c.shape[0]), 480), interpolation=cv2.INTER_AREA) for c in (hair, hands, whole)]
        row = np.concatenate(cells, 1)
        label = np.full((56, row.shape[1], 3), 22, np.uint8)
        facts = "   ".join(f"{k.replace('_', ' ')} {v}" for k, v in result["numbers"].items())
        cv2.putText(
            label,
            f"{name}   {result['seconds_per_frame']:g} s/frame   {facts}",
            (16, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (240, 240, 240),
            2,
        )
        rows.append(np.concatenate([label, row], 0))
    widest = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, widest - r.shape[1]), (0, 0))) for r in rows]
    cv2.imwrite(str(out), cv2.cvtColor(np.concatenate(rows, 0), cv2.COLOR_RGB2BGR))


def compare(
    source: Path, start: float, models: Path, rvm: Path | None, out: Path, wall: str | None, only: list[str] | None, frames: int = 96
):
    import numpy as np

    from .matte import probe

    width, height, _rate = probe(source)
    footage = read_frames(source, start, RUN_IN + frames, width, height)
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, run in runners(models, rvm).items():
        if only and name not in only:
            continue
        mattes, seconds, every = run(footage)
        mattes = [np.clip(m, 0, 1).astype(np.float32) for m in mattes]
        np.save(out / f"{name}.npy", (np.stack(mattes) * 255).astype(np.uint8))
        results[name] = {
            "mattes": mattes,
            "seconds_per_frame": round(seconds, 3),
            "every": every,
            "numbers": numbers(footage, mattes, wall),
        }
        print(name, results[name]["seconds_per_frame"], "s/frame", results[name]["numbers"], flush=True)
    if not results:
        raise SystemExit(f"no model files found in {models}; see this module's docstring for their names")
    sheet(footage, results, out / "compare.png")
    table = {n: {k: v for k, v in r.items() if k != "mattes"} for n, r in results.items()}
    (out / "compare.json").write_text(json.dumps(table, indent=1) + "\n")
    return table


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Several matting models on the same frames.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--start", type=float, default=0.0, help="where the four seconds start; pick hair and moving hands")
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--rvm", type=Path, help="a clone of RobustVideoMatting, for the rvm models")
    parser.add_argument("--out", type=Path, default=Path("matte-compare"))
    parser.add_argument("--wall", choices=sorted(WALLS), help="the background's colour, when it has one saturated colour")
    parser.add_argument("--only", help="model names, with commas between")
    given = parser.parse_args()
    compare(given.source, given.start, given.models, given.rvm, given.out, given.wall, given.only.split(",") if given.only else None)
