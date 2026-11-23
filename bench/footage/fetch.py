"""Fetch the footage in the manifest into `data/footage/`: `uv run python -m bench.footage.fetch`.

Each file is checked against the SHA-256 in the manifest. `--pin` writes the hash of a file fetched for
the first time, so a new entry only needs its URL.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

MANIFEST = Path(__file__).parent / "manifest.toml"
FOLDER = Path("data/footage")


def videos() -> dict[str, dict]:
    return tomllib.loads(MANIFEST.read_text())["video"]


def path(name: str) -> Path:
    return FOLDER / f"{name}.mp4"


def _sha256(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(name: str, entry: dict) -> str:
    target = path(name)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(entry["url"], headers={"User-Agent": "uberseek-bench/0.1"})
        partial = target.with_suffix(".part")
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
        partial.rename(target)
    return _sha256(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="which videos (default: all)")
    parser.add_argument("--pin", action="store_true", help="write the hash of entries that have none")
    args = parser.parse_args()
    failed = 0
    for name, entry in videos().items():
        if args.names and name not in args.names:
            continue
        got, want = fetch(name, entry), entry.get("sha256", "")
        if not want and args.pin:
            text = MANIFEST.read_text()
            block = re.search(rf"\[video\.{re.escape(name)}\]\n", text)
            MANIFEST.write_text(text[: block.end()] + f'sha256 = "{got}"\n' + text[block.end() :])
            print(f"{name}: pinned {got[:12]}")
        elif got != want:
            failed += 1
            print(f"{name}: hash is {got}, the manifest says {want or 'nothing'}", file=sys.stderr)
        else:
            print(f"{name}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
