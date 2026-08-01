"""
store.py — persistent metadata store for Sage sessions.

A session's actual *data* already lives in its own SQLite file (see
tools.SessionData, which now points at backend/session_data/ instead of the
OS temp dir). This module persists everything else needed to list past
sessions and reopen ("resume") them later: upload metadata (filename, row/
col counts, the column profile) and the full question/answer chat history —
so a manager can come back later and see the report they ran last week, not
just the one still open in their browser tab.

This is a plain SQLite file next to the code (backend/sage_meta.db). Like
session_data/, it survives process restarts but NOT a fresh redeploy unless
a persistent volume is mounted over the backend directory on the host.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

_META_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sage_meta.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_META_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist yet. Safe to call on every startup."""
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            filename TEXT,
            dataset_name TEXT,
            uploaded_at REAL,
            rows INTEGER,
            cols INTEGER,
            columns_json TEXT,
            profile_json TEXT,
            cleaning_report_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tools_called_json TEXT,
            created_at REAL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    conn.commit()
    conn.close()


def save_session_meta(
    session_id: str,
    filename: str,
    dataset_name: str,
    rows: int,
    cols: int,
    columns: List[str],
    profile: Optional[Dict[str, Any]],
    cleaning_report: List[str],
) -> None:
    """Upsert a session's metadata. Called once on upload."""
    conn = _conn()
    conn.execute(
        """INSERT INTO sessions
               (id, filename, dataset_name, uploaded_at, rows, cols, columns_json, profile_json, cleaning_report_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               filename=excluded.filename, dataset_name=excluded.dataset_name,
               rows=excluded.rows, cols=excluded.cols, columns_json=excluded.columns_json,
               profile_json=excluded.profile_json, cleaning_report_json=excluded.cleaning_report_json""",
        (
            session_id, filename, dataset_name, time.time(), rows, cols,
            json.dumps(columns), json.dumps(profile, default=str), json.dumps(cleaning_report),
        ),
    )
    conn.commit()
    conn.close()


def list_sessions(limit: int = 100) -> List[Dict[str, Any]]:
    """Newest-first list of past sessions, for the history browser."""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, filename, dataset_name, uploaded_at, rows, cols FROM sessions ORDER BY uploaded_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_meta(session_id: str) -> Optional[Dict[str, Any]]:
    conn = _conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["columns"] = json.loads(d.pop("columns_json") or "[]")
    d["profile"] = json.loads(d.pop("profile_json") or "null")
    d["cleaning_report"] = json.loads(d.pop("cleaning_report_json") or "[]")
    return d


def add_message(session_id: str, role: str, content: str, tools_called: Optional[list] = None) -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tools_called_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, json.dumps(tools_called or []), time.time()),
    )
    conn.commit()
    conn.close()


def get_messages(session_id: str) -> List[Dict[str, Any]]:
    """Full chat history for a session, oldest first."""
    conn = _conn()
    rows = conn.execute(
        "SELECT role, content, tools_called_json, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["tools_called"] = json.loads(d.pop("tools_called_json") or "[]")
        out.append(d)
    return out
