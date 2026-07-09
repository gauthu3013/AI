"""Local persistence layer for the digital twin.

Every simulator tick writes a snapshot of each asset to a local SQLite
database under ./data — this is the "digital twin connected to local cloud
storage" leg of the pipeline, without needing a real cloud account for the
demo. Swapping this module for an actual cloud database later does not
require changing the simulator or the risk agents.
"""

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "twin_history.db"
MAX_ROWS = 20000

_conn: sqlite3.Connection | None = None
_tick_count = 0


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_epoch REAL NOT NULL,
                sim_minutes REAL NOT NULL,
                asset_id TEXT NOT NULL,
                discipline TEXT NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_ts ON readings(asset_id, id)")
        _conn.commit()
    return _conn


def record_snapshot(snapshot: dict) -> None:
    """Persist one row per asset for this tick."""
    global _tick_count
    conn = _get_conn()
    ts = time.time()
    rows = []
    for asset_id, asset in snapshot["electrical"].items():
        rows.append((ts, snapshot["sim_minutes"], asset_id, "electrical", json.dumps(asset)))
    for asset_id, asset in snapshot["process"].items():
        rows.append((ts, snapshot["sim_minutes"], asset_id, "process", json.dumps(asset)))
    conn.executemany(
        "INSERT INTO readings (ts_epoch, sim_minutes, asset_id, discipline, payload) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()

    _tick_count += 1
    if _tick_count % 50 == 0:
        conn.execute(
            "DELETE FROM readings WHERE id NOT IN (SELECT id FROM readings ORDER BY id DESC LIMIT ?)",
            (MAX_ROWS,),
        )
        conn.commit()


def history(asset_id: str, limit: int = 60) -> list[dict]:
    """Most recent readings for one asset, oldest first."""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT sim_minutes, payload FROM readings WHERE asset_id = ? ORDER BY id DESC LIMIT ?",
        (asset_id, limit),
    )
    rows = cur.fetchall()
    out = []
    for sim_minutes, payload in reversed(rows):
        record = json.loads(payload)
        record["sim_minutes"] = sim_minutes
        out.append(record)
    return out


def reset() -> None:
    """Wipe stored history (used when the demo scenario is reset)."""
    global _tick_count
    conn = _get_conn()
    conn.execute("DELETE FROM readings")
    conn.commit()
    _tick_count = 0
