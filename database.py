import sqlite3
import json
import os

# Allow overriding the DB path via environment variable for production
DB_PATH = os.environ.get("DB_PATH", "entries.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                submitted_at  TEXT    NOT NULL,
                name          TEXT    NOT NULL,
                email         TEXT    NOT NULL,
                players       TEXT    NOT NULL,
                total_salary  INTEGER NOT NULL
            )
        """)


def save_entry(submitted_at, name, email, players, total_salary):
    """Insert a new submission. players is a list of player name strings."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO entries (submitted_at, name, email, players, total_salary) VALUES (?, ?, ?, ?, ?)",
            (submitted_at, name, email, json.dumps(players), total_salary),
        )


def get_all_entries():
    """Return all entries as a list of {name, players} dicts, ordered by submission time."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name, players FROM entries ORDER BY submitted_at"
        ).fetchall()
    return [{"name": row["name"], "players": json.loads(row["players"])} for row in rows]
