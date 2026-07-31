import json
import sqlite3
from pathlib import Path

from .config import DATABASE_PATH, STORAGE_ROOT


def initialize_database() -> None:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                transcript_json TEXT,
                plan_json TEXT,
                error TEXT
            )
        """)


def create_task(task_id: str, metadata: dict) -> None:
    initialize_database()
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "INSERT INTO tasks (task_id, status, metadata_json) VALUES (?, ?, ?)",
            (task_id, "processing", json.dumps(metadata, ensure_ascii=False)),
        )


def update_task(task_id: str, status: str, transcript: dict | None = None, plan: dict | None = None, error: str | None = None) -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """UPDATE tasks SET status = ?, transcript_json = COALESCE(?, transcript_json),
               plan_json = COALESCE(?, plan_json), error = ? WHERE task_id = ?""",
            (status, json.dumps(transcript, ensure_ascii=False) if transcript else None,
             json.dumps(plan, ensure_ascii=False) if plan else None, error, task_id),
        )


def get_task(task_id: str) -> dict | None:
    initialize_database()
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    return {
        "task_id": row["task_id"], "status": row["status"],
        "metadata": json.loads(row["metadata_json"]),
        "transcript": json.loads(row["transcript_json"]) if row["transcript_json"] else None,
        "plan": json.loads(row["plan_json"]) if row["plan_json"] else None,
        "error": row["error"],
    }
