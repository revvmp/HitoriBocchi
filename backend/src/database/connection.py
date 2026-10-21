import os
import sqlite3


# Relative paths resolve against the process working directory, which is backend/src for the
# Flask service and every scheduled job. Set DATABASE_PATH to an absolute path to remove that dependency.
DATABASE_PATH = os.environ.get("DATABASE_PATH", "instance/anime.db")

# Seconds a connection waits for another writer, such as a scheduled sync job, to release its lock.
BUSY_TIMEOUT_SECONDS = 30


def connect(database_path: str | None = None) -> sqlite3.Connection:
    """
    Opens a SQLite connection with foreign keys enforced.
    """
    conn = sqlite3.connect(database_path or DATABASE_PATH, timeout=BUSY_TIMEOUT_SECONDS)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
