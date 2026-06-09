import sqlite3
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    samples  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    ts         REAL NOT NULL,
    value      REAL NOT NULL
);
"""


class DataManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def _init_db(self) -> None:
        con = self._connect()
        try:
            con.executescript(_SCHEMA)
            con.commit()
        finally:
            con.close()

    def save_session(self, name: str, data: list) -> int:
        saved_at = datetime.now(timezone.utc).isoformat()
        con = self._connect()
        try:
            cur = con.execute(
                "INSERT INTO sessions (name, saved_at, samples) VALUES (?, ?, ?)",
                (name, saved_at, len(data)),
            )
            sid = cur.lastrowid
            con.executemany(
                "INSERT INTO measurements (session_id, ts, value) VALUES (?, ?, ?)",
                [(sid, ts, val) for ts, val in data],
            )
            con.commit()
            return sid
        finally:
            con.close()

    def load_sessions(self) -> list:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT id, name, saved_at, samples FROM sessions ORDER BY saved_at DESC"
            ).fetchall()
            return [{"id": r[0], "name": r[1], "saved_at": r[2], "samples": r[3]} for r in rows]
        except Exception as exc:
            print(f"[db] load_sessions error: {exc}")
            return []
        finally:
            con.close()

    def load_measurements(self, session_id: int) -> list:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT ts, value FROM measurements WHERE session_id = ? ORDER BY ts",
                (session_id,),
            ).fetchall()
            return [{"ts": r[0], "value": r[1]} for r in rows]
        except Exception as exc:
            print(f"[db] load_measurements error: {exc}")
            return []
        finally:
            con.close()

    def delete_session(self, session_id: int) -> None:
        con = self._connect()
        try:
            con.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            con.commit()
        finally:
            con.close()
