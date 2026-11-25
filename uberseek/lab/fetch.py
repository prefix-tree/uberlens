"""A few seconds out of a very large remote video, without downloading the rest.

A QuickTime or MP4 file with its index at the front (the `moov` box) says where every frame's bytes are. So the
index is fetched first, the byte range of the seconds wanted is worked out from it, and only that range is fetched,
into a sparse local file that FFmpeg reads as if it were whole.

    python -m uberseek.lab.fetch <url> <start seconds> <end seconds> <out.mov>

It came from an interview whose only full copy was 12.8 GB of ProRes; the 40 seconds needed were 960 MB.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path


class FetchError(RuntimeError):
    pass


def _boxes(data: bytes, start: int, end: int):
    """Each box in data[start:end] as (type, body start, box end)."""
    at = start
    while at + 8 <= end:
        size, kind = struct.unpack(">I4s", data[at : at + 8])
        head = 8
        if size == 1:
            size = struct.unpack(">Q", data[at + 8 : at + 16])[0]
            head = 16
        if size < 8:
            break
        yield kind, at + head, at + size
        at += size


def _find(data: bytes, start: int, end: int, path: list[bytes]):
    for kind, body, stop in _boxes(data, start, end):
        if kind == path[0]:
            if len(path) == 1:
                yield body, stop
            else:
                yield from _find(data, body, stop, path[1:])


def index_size(head: bytes) -> int:
    """How many bytes from the start of the file hold its index, read from the file's first bytes.

    Raises when the index is not at the front: such a file has to be fetched whole, or remuxed with its index first.
    """
    for kind, _body, stop in _boxes(head, 0, len(head)):
        if kind == b"moov":
            return stop
        if kind == b"mdat":
            break
    # A box header that runs past what was read still tells its size.
    at = 0
    while at + 16 <= len(head):
        size, kind = struct.unpack(">I4s", head[at : at + 8])
        if size == 1:
            size = struct.unpack(">Q", head[at + 8 : at + 16])[0]
        if kind == b"moov":
            return at + size
        if kind == b"mdat" or size < 8:
            break
        at += size
    raise FetchError("the file's index (moov) is not at its front, so a part of it cannot be fetched on its own")


def span_range(head: bytes, start: float, end: float) -> tuple[int, int]:
    """The byte range [lo, hi) that holds every sample between `start` and `end` seconds, on every track.

    `head` is the file's first bytes, with the whole index in them (see `index_size`).
    """
    lo: int | None = None
    hi = 0
    for track, track_end in _find(head, 0, len(head), [b"moov", b"trak"]):
        header = next(_find(head, track, track_end, [b"mdia", b"mdhd"]), None)
        table = next(_find(head, track, track_end, [b"mdia", b"minf", b"stbl"]), None)
        if header is None or table is None:
            continue
        version = head[header[0]]
        scale = struct.unpack(">I", head[header[0] + (20 if version else 12) : header[0] + (24 if version else 16)])[0]

        def box(name: bytes, table=table):
            return next(_find(head, table[0], table[1], [name]), None)

        stts, stsc, stsz = box(b"stts"), box(b"stsc"), box(b"stsz")
        offsets_box, wide = box(b"co64"), True
        if offsets_box is None:
            offsets_box, wide = box(b"stco"), False
        if None in (stts, stsc, stsz, offsets_box):
            continue

        runs = struct.unpack(">I", head[stts[0] + 4 : stts[0] + 8])[0]
        deltas = [struct.unpack(">II", head[stts[0] + 8 + i * 8 : stts[0] + 16 + i * 8]) for i in range(runs)]
        one_size, count = struct.unpack(">II", head[stsz[0] + 4 : stsz[0] + 12])
        sizes = None if one_size else struct.unpack(f">{count}I", head[stsz[0] + 12 : stsz[0] + 12 + 4 * count])
        chunks = struct.unpack(">I", head[offsets_box[0] + 4 : offsets_box[0] + 8])[0]
        width = 8 if wide else 4
        offsets = struct.unpack(f">{chunks}{'Q' if wide else 'I'}", head[offsets_box[0] + 8 : offsets_box[0] + 8 + chunks * width])
        groups = struct.unpack(">I", head[stsc[0] + 4 : stsc[0] + 8])[0]
        per_chunk = [struct.unpack(">III", head[stsc[0] + 8 + i * 12 : stsc[0] + 20 + i * 12]) for i in range(groups)]

        # Walk the samples in file order: each chunk holds some, back to back from the chunk's offset.
        sample = 0
        ticks = 0
        run = 0
        left_in_run = deltas[0][0] if deltas else 0
        group = 0
        for chunk in range(chunks):
            while group + 1 < groups and per_chunk[group + 1][0] <= chunk + 1:
                group += 1
            at = offsets[chunk]
            for _ in range(per_chunk[group][1]):
                if sample >= count:
                    break
                size = one_size or sizes[sample]
                if start <= ticks / scale <= end:
                    lo = at if lo is None else min(lo, at)
                    hi = max(hi, at + size)
                at += size
                sample += 1
                if run < runs:
                    ticks += deltas[run][1]
                    left_in_run -= 1
                    if left_in_run == 0 and run + 1 < runs:
                        run += 1
                        left_in_run = deltas[run][0]
    if lo is None:
        raise FetchError(f"nothing in the file lies between {start} and {end} seconds")
    return lo, hi


def _curl(url: str, *args: str) -> bytes:
    done = subprocess.run(["curl", "-sS", "-L", "--fail", *args, url], capture_output=True)
    if done.returncode != 0:
        raise FetchError(f"cannot fetch {url}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def remote_size(url: str) -> int:
    for line in _curl(url, "-I").decode(errors="replace").splitlines():
        name, _, value = line.partition(":")
        if name.strip().lower() == "content-length":
            return int(value.strip())
    raise FetchError(f"{url} does not say how long it is")


def sparse_copy(url: str, start: float, end: float, path: Path, margin: float = 1.0) -> Path:
    """A local file as long as the remote one, holding only its index and the bytes of `start` to `end` seconds.

    Reading it anywhere else gives zeros, so cut from it only inside the span (`cut` does).
    """
    size = remote_size(url)
    head = _curl(url, "-r", "0-65535")
    head = _curl(url, "-r", f"0-{index_size(head) - 1}")
    lo, hi = span_range(head, max(0.0, start - margin), end + margin)
    if hi > size:
        raise FetchError(f"the file is cut short on the server: its index needs {hi} bytes and it has {size}")
    with open(path, "wb") as out:
        out.truncate(size)
        out.write(head)
    with open(path, "r+b") as out:
        out.seek(lo)
        fetch = subprocess.Popen(["curl", "-sS", "-L", "--fail", "-r", f"{lo}-{hi - 1}", url], stdout=subprocess.PIPE)
        assert fetch.stdout is not None
        while block := fetch.stdout.read(1 << 20):
            out.write(block)
        if fetch.wait() != 0:
            raise FetchError(f"the fetch of bytes {lo} to {hi} of {url} failed")
    return path


def cut(sparse: Path, start: float, end: float, out: Path, ffmpeg: str = "ffmpeg") -> Path:
    """The span as a file of its own: H.264 near lossless and PCM sound, good to work from."""
    done = subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-ss", str(start), "-i", str(sparse), "-map", "0:v:0", "-map", "0:a:0?"]
        + ["-t", str(end - start), "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p"]
        + ["-c:a", "pcm_s16le", str(out)],
        capture_output=True,
    )
    if done.returncode != 0 or not out.exists() or out.stat().st_size < 1024:
        raise FetchError(f"cannot cut {start} to {end} s: {done.stderr.decode(errors='replace').strip()[-400:]}")
    return out


def fetch_span(url: str, start: float, end: float, out: Path, ffmpeg: str = "ffmpeg") -> Path:
    """`start` to `end` seconds of the video at `url`, written to `out`, fetching only what those seconds need."""
    sparse = out.with_suffix(".sparse" + out.suffix)
    try:
        sparse_copy(url, start, end, sparse)
        return cut(sparse, start, end, out, ffmpeg)
    finally:
        if sparse.exists():
            os.remove(sparse)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    made = fetch_span(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), Path(sys.argv[4]))
    print(f"{made}: {made.stat().st_size} bytes")
