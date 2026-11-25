"""How loud a file is, as the platforms measure it: integrated loudness (LUFS) and true peak (dBTP).

    python -m uberseek.lab.loudness clip.mp4

Measure the file that is delivered, not the mix: an encode can raise peaks, and a mono track played on two channels
reads about 3 LU louder than its file. For the web, about -14 LUFS and a true peak of -2 dBTP or less.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def measure(path: Path | str, ffmpeg: str = "ffmpeg") -> dict:
    """{"lufs": integrated loudness, "true_peak": dBTP, "range": loudness range in LU}; None for silence."""
    done = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise ValueError(f"cannot measure {path}: {done.stderr.strip()[-300:]}")
    summary = done.stderr.rsplit("Summary:", 1)[-1]

    def read(label: str) -> float | None:
        found = re.search(rf"{label}:\s+(-?[\d.]+|-inf)", summary)
        if not found or found.group(1) == "-inf":
            return None
        value = float(found.group(1))
        return None if value <= -70 else value

    return {"lufs": read("I"), "true_peak": read("Peak"), "range": read("LRA")}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(measure(sys.argv[1]))
