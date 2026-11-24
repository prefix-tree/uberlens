"""State kept outside the model's context, in the project folder.

The observation log is append-only: SQLite refuses to change or delete an entry. Pictures are stored once,
under their content hash. Anything derived from a file (its index, its signals) is cached by the file's hash.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    seq INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    focus TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS observations_source ON observations (source);
CREATE TRIGGER IF NOT EXISTS observations_keep BEFORE UPDATE ON observations
    BEGIN SELECT RAISE(ABORT, 'the observation log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS observations_stay BEFORE DELETE ON observations
    BEGIN SELECT RAISE(ABORT, 'the observation log is append-only'); END;
CREATE TABLE IF NOT EXISTS executions (
    seq INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS executions_keep BEFORE UPDATE ON executions
    BEGIN SELECT RAISE(ABORT, 'the execution log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS executions_stay BEFORE DELETE ON executions
    BEGIN SELECT RAISE(ABORT, 'the execution log is append-only'); END;
CREATE TABLE IF NOT EXISTS selections (
    seq INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS selections_keep BEFORE UPDATE ON selections
    BEGIN SELECT RAISE(ABORT, 'the selection log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS selections_stay BEFORE DELETE ON selections
    BEGIN SELECT RAISE(ABORT, 'the selection log is append-only'); END;
CREATE TABLE IF NOT EXISTS clips (
    seq INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS clips_keep BEFORE UPDATE ON clips
    BEGIN SELECT RAISE(ABORT, 'the clip log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS clips_stay BEFORE DELETE ON clips
    BEGIN SELECT RAISE(ABORT, 'the clip log is append-only'); END;
CREATE TABLE IF NOT EXISTS derived (
    source TEXT NOT NULL,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (source, name)
);
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    hash TEXT NOT NULL
);
"""


def obs_id(seq: int) -> str:
    return f"obs_{seq:06d}"


class Log:
    def __init__(self, root: Path):
        self.root = Path(root) / ".uberseek"
        (self.root / "artifacts").mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.db.executescript(_SCHEMA)

    @property
    def db(self) -> sqlite3.Connection:
        """One connection per thread: a host harness may run tools on worker threads."""
        if not hasattr(self._local, "db"):
            self._local.db = sqlite3.connect(self.root / "log.sqlite", isolation_level=None, timeout=30)
        return self._local.db

    # Observations

    def append(self, record: dict) -> dict:
        """Store the record and return it with its id and time."""
        created = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            seq = self.db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM observations").fetchone()[0]
            full = {"id": obs_id(seq), "created_at": created, **record}
            self.db.execute(
                "INSERT INTO observations VALUES (?, ?, ?, ?, ?)",
                (seq, created, record["source"]["hash"], record["request"]["focus"], json.dumps(full)),
            )
        return full

    def get(self, id: str) -> dict:
        row = self.db.execute("SELECT record FROM observations WHERE seq = ?", (int(id.removeprefix("obs_")),)).fetchone()
        if row is None:
            raise KeyError(f"no observation {id}")
        return json.loads(row[0])

    def observations(self, source: str | None = None) -> list[dict]:
        where, args = ("WHERE source = ?", (source,)) if source else ("", ())
        rows = self.db.execute(f"SELECT record FROM observations {where} ORDER BY seq", args)
        return [json.loads(r[0]) for r in rows]

    # Executions, selections and clips: each an append-only list of records with its own ids

    def _append(self, table: str, prefix: str, record: dict) -> dict:
        created = datetime.now(UTC).isoformat(timespec="milliseconds")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            seq = self.db.execute(f"SELECT COALESCE(MAX(seq), 0) + 1 FROM {table}").fetchone()[0]
            full = {"id": f"{prefix}_{seq:06d}", "created_at": created, **record}
            self.db.execute(f"INSERT INTO {table} VALUES (?, ?, ?)", (seq, created, json.dumps(full, default=str)))
        return full

    def _all(self, table: str) -> list[dict]:
        return [json.loads(r[0]) for r in self.db.execute(f"SELECT record FROM {table} ORDER BY seq")]

    def append_execution(self, record: dict) -> dict:
        """A program run, whether it worked or not."""
        return self._append("executions", "exec", record)

    def executions(self) -> list[dict]:
        return self._all("executions")

    def append_selection(self, record: dict) -> dict:
        """A span chosen for use, with its reason and the looks it rests on."""
        return self._append("selections", "sel", record)

    def selections(self) -> list[dict]:
        return self._all("selections")

    def append_clip(self, record: dict) -> dict:
        """A file cut from selections, with the map from source time to its own time."""
        return self._append("clips", "clip", record)

    def clips(self) -> list[dict]:
        return self._all("clips")

    # Pictures, by content hash

    def put_artifact(self, data: bytes, suffix: str) -> str:
        digest = hashlib.sha256(data).hexdigest()
        path = self.root / "artifacts" / f"{digest}{suffix}"
        if not path.exists():
            path.write_bytes(data)
        return digest

    def artifact(self, digest: str, suffix: str) -> bytes:
        return (self.root / "artifacts" / f"{digest}{suffix}").read_bytes()

    # Derived data, by the source's content hash

    def derived(self, source: str, name: str, make) -> dict:
        row = self.db.execute("SELECT data FROM derived WHERE source = ? AND name = ?", (source, name)).fetchone()
        if row:
            return json.loads(row[0])
        data = make()
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO derived VALUES (?, ?, ?)", (source, name, json.dumps(data)))
        return data

    def has_derived(self, source: str, name: str) -> bool:
        row = self.db.execute("SELECT 1 FROM derived WHERE source = ? AND name = ?", (source, name)).fetchone()
        return row is not None

    def content_hash(self, path: Path) -> str:
        """SHA-256 of the file. Reused while the file's size and modification time are unchanged."""
        stat = path.stat()
        key = str(path.resolve())
        row = self.db.execute("SELECT size, mtime_ns, hash FROM files WHERE path = ?", (key,)).fetchone()
        if row and (row[0], row[1]) == (stat.st_size, stat.st_mtime_ns):
            return row[2]
        digest = hashlib.sha256()
        with path.open("rb") as file:
            while chunk := file.read(1 << 20):
                digest.update(chunk)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?)", (key, stat.st_size, stat.st_mtime_ns, digest.hexdigest()))
        return digest.hexdigest()
