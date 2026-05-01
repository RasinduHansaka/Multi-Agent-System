"""
tools/db_logger.py
------------------
MEMBER 4 – Custom Tool
Persists completed review sessions to a local SQLite database.
Provides full CRUD operations so sessions can be queried, retrieved, and listed.
No external dependencies beyond Python's built-in sqlite3 module.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "logs", "sessions.db"
)


def _get_connection() -> sqlite3.Connection:
    """
    Opens a SQLite connection with row_factory set for dict-style access.

    Returns:
        An open sqlite3.Connection object.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Creates the sessions table if it does not already exist.
    Safe to call multiple times (uses IF NOT EXISTS).

    Args:
        db_path: Optional override for the database file path.
                 Defaults to the module-level DB_PATH constant.

    Raises:
        sqlite3.Error: If the database file cannot be created or written.
    """
    target = db_path or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    conn = sqlite3.connect(target)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id                INTEGER  PRIMARY KEY AUTOINCREMENT,
                session_id        TEXT     NOT NULL UNIQUE,
                timestamp         TEXT     NOT NULL,
                filepath          TEXT,
                language          TEXT,
                code_findings     TEXT,
                security_findings TEXT,
                total_findings    INTEGER  DEFAULT 0,
                report            TEXT,
                duration_seconds  REAL     DEFAULT 0.0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_session_report(
    session_id: str,
    filepath: str,
    language: str,
    code_findings: list[dict],
    security_findings: list[dict],
    report: str,
    duration_seconds: float = 0.0,
    db_path: Optional[str] = None,
) -> bool:
    """
    Persists a completed review session to the local SQLite database.

    Args:
        session_id:         Unique UUID string for the review session.
        filepath:           Path to the file that was analysed.
        language:           Detected programming language string.
        code_findings:      List of code issue dicts from the Code Analyzer agent.
        security_findings:  List of security issue dicts from the Security Auditor agent.
        report:             The full markdown report string.
        duration_seconds:   Total pipeline wall-clock time in seconds.
        db_path:            Optional override for the database path (used in tests).

    Returns:
        True if the record was inserted successfully, False if an error occurred.

    Raises:
        Nothing – all errors are caught and logged to stdout so the pipeline never crashes.

    Example:
        >>> ok = save_session_report("abc-123", "app.py", "Python", [], [], "# Report")
        >>> ok
        True
    """
    target = db_path or DB_PATH
    try:
        init_db(target)
        conn = sqlite3.connect(target)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, timestamp, filepath, language,
                    code_findings, security_findings,
                    total_findings, report, duration_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    datetime.now().isoformat(),
                    filepath,
                    language,
                    json.dumps(code_findings),
                    json.dumps(security_findings),
                    len(code_findings) + len(security_findings),
                    report,
                    round(duration_seconds, 2),
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except (sqlite3.Error, OSError, NotADirectoryError) as exc:
        print(f"[DB ERROR] Failed to save session {session_id}: {exc}")
        return False


def get_session(session_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    """
    Retrieves a single session record by session_id.

    Args:
        session_id: The UUID of the session to retrieve.
        db_path:    Optional override for the database path.

    Returns:
        A dict representation of the session row, or None if not found.

    Example:
        >>> session = get_session("abc-123")
        >>> session["language"]
        'Python'
    """
    target = db_path or DB_PATH
    if not os.path.exists(target):
        return None
    try:
        conn = sqlite3.connect(target)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def list_sessions(limit: int = 10, db_path: Optional[str] = None) -> list[dict]:
    """
    Returns the most recent review sessions from the database.

    Args:
        limit:   Maximum number of rows to return (default: 10).
        db_path: Optional override for the database path.

    Returns:
        A list of session dicts ordered by timestamp descending.

    Example:
        >>> sessions = list_sessions(limit=5)
        >>> len(sessions) <= 5
        True
    """
    target = db_path or DB_PATH
    if not os.path.exists(target):
        return []
    try:
        conn = sqlite3.connect(target)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT session_id, timestamp, filepath, language, total_findings "
                "FROM sessions ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def export_sessions_to_csv(csv_path: str, db_path: Optional[str] = None) -> bool:
    """
    Exports all session records from the SQLite database to a CSV file.
    Demonstrates advanced CRUD and data extraction capabilities.

    Args:
        csv_path: Path to the output CSV file.
        db_path:  Optional override for the database path.

    Returns:
        True if the export succeeded, False otherwise.
    """
    import csv
    target = db_path or DB_PATH
    if not os.path.exists(target):
        return False
    try:
        conn = sqlite3.connect(target)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM sessions ORDER BY timestamp DESC").fetchall()
            if not rows:
                return False
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(rows[0].keys())
                for row in rows:
                    writer.writerow(row)
            return True
        finally:
            conn.close()
    except Exception as exc:
        print(f"[DB ERROR] Failed to export sessions to CSV: {exc}")
        return False