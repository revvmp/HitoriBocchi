"""
Database schema and idempotent migrations.
`migrate()` is safe to run on every startup: it only creates missing tables, columns, and indexes.
"""
from database import connection


TABLES = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS animes (
        id INTEGER PRIMARY KEY,
        title TEXT,
        title_english TEXT,
        slug TEXT UNIQUE NOT NULL,
        synopsis TEXT,
        image TEXT,
        rating REAL,
        genres TEXT,
        status TEXT,
        popularity INTEGER,
        current_episodes INTEGER,
        total_episodes TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        anilist_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY,
        anime_id INTEGER NOT NULL,
        episode_number INTEGER NOT NULL,
        provider_episode_id TEXT,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (anime_id) REFERENCES animes(id) ON DELETE CASCADE,
        UNIQUE(anime_id, episode_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mangas (
        id INTEGER PRIMARY KEY,
        title TEXT,
        title_english TEXT,
        slug TEXT UNIQUE NOT NULL,
        synopsis TEXT,
        image TEXT,
        rating REAL,
        genres TEXT,
        status TEXT,
        popularity INTEGER,
        media_type TEXT,
        current_chapters INTEGER,
        total_chapters TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        anilist_id INTEGER,
        mangakatana_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chapters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        manga_id INTEGER NOT NULL,
        chapter_number TEXT NOT NULL,
        provider_chapter_id TEXT,
        title TEXT,
        released_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (manga_id) REFERENCES mangas(id) ON DELETE CASCADE,
        UNIQUE(manga_id, chapter_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS manga_bookmarks (
        user_id INTEGER NOT NULL,
        manga_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, manga_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (manga_id) REFERENCES mangas(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watch_history (
        user_id INTEGER NOT NULL,
        episode_id INTEGER NOT NULL,
        current_time_seconds INTEGER NOT NULL DEFAULT 0,
        duration_seconds INTEGER NOT NULL DEFAULT 0,
        last_watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, episode_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_episode_completions (
        user_id INTEGER NOT NULL,
        episode_id INTEGER NOT NULL,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, episode_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        watch_history_tracking_enabled INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        episode_id INTEGER NOT NULL,
        comment_text TEXT,
        parent_id INTEGER DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
        FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS site_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL
    )
    """,
)

# Columns added after the original schema. Older databases receive them through ALTER TABLE.
ADDED_COLUMNS = (
    ("animes", "anilist_id", "INTEGER"),
    ("mangas", "anilist_id", "INTEGER"),
    ("mangas", "mangakatana_id", "TEXT"),
)

INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_animes_title ON animes(title)",
    "CREATE INDEX IF NOT EXISTS idx_animes_status ON animes(status)",
    "CREATE INDEX IF NOT EXISTS idx_animes_popularity ON animes(popularity)",
    "CREATE INDEX IF NOT EXISTS idx_animes_rating ON animes(rating)",
    "CREATE INDEX IF NOT EXISTS idx_animes_anilist_id ON animes(anilist_id)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_anime_created ON episodes(anime_id, created_at DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS idx_mangas_title ON mangas(title)",
    "CREATE INDEX IF NOT EXISTS idx_mangas_status ON mangas(status)",
    "CREATE INDEX IF NOT EXISTS idx_mangas_popularity ON mangas(popularity)",
    "CREATE INDEX IF NOT EXISTS idx_mangas_rating ON mangas(rating)",
    "CREATE INDEX IF NOT EXISTS idx_chapters_manga_created ON chapters(manga_id, created_at DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS idx_manga_bookmarks_user_created ON manga_bookmarks(user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_manga_bookmarks_manga ON manga_bookmarks(manga_id)",
    "CREATE INDEX IF NOT EXISTS idx_watch_history_user_watched ON watch_history(user_id, last_watched_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_watch_history_episode ON watch_history(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_completions_episode ON user_episode_completions(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_comments_episode_created ON comments(episode_id, created_at, id)",
    "CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_id)",
    "CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(user_id)",
)

DEFAULT_SITE_SETTINGS = (
    ("login_required", "1"),
)


def _column_names(conn, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def apply(conn):
    """
    Brings an open connection's schema up to date without touching existing rows.
    """
    for statement in TABLES:
        conn.execute(statement)

    for table, column, column_type in ADDED_COLUMNS:
        if column not in _column_names(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    for statement in INDEXES:
        conn.execute(statement)

    conn.executemany("INSERT OR IGNORE INTO site_settings (setting_key, setting_value) VALUES (?, ?)", DEFAULT_SITE_SETTINGS)
    conn.commit()


def migrate(database_path: str | None = None):
    """
    Updates the database file and enables write-ahead logging so readers never block on sync job writes.
    """
    conn = connection.connect(database_path)

    try:
        conn.execute("PRAGMA journal_mode = WAL")
        apply(conn)
    finally:
        conn.close()
