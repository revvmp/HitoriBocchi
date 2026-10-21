import sqlite3

from database.models import MangaData
from utils.logger import get_logger


logger = get_logger(__name__)


class BookmarkRepository:
    """
    Account manga bookmarks.
    """
    def add_manga_bookmark(self, user_id: int, manga_id: int) -> bool:
        """Adds a manga to a user's bookmarks."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "INSERT OR IGNORE INTO manga_bookmarks (user_id, manga_id) VALUES (?, ?)",
                (user_id, manga_id,)
            )
            self.conn.commit()
            return True

        except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
            logger.error(f"Error adding manga bookmark: {e}")
            return False

    def delete_manga_bookmark(self, user_id: int, manga_id: int) -> bool:
        """Removes a manga from a user's bookmarks."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM manga_bookmarks WHERE user_id = ? AND manga_id = ?",
                (user_id, manga_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except sqlite3.OperationalError as e:
            logger.error(f"Error deleting manga bookmark: {e}")
            return False

    def is_manga_bookmarked(self, user_id: int, manga_id: int) -> bool:
        """Returns whether a user has bookmarked a manga."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "SELECT 1 FROM manga_bookmarks WHERE user_id = ? AND manga_id = ?",
                (user_id, manga_id,)
            )
            return cursor.fetchone() is not None

        except sqlite3.OperationalError as e:
            logger.error(f"Error fetching manga bookmark: {e}")
            return False

    def fetch_manga_bookmarks(self, user_id: int, limit: int = 20, offset: int = 0) -> list[MangaData] | None:
        """Fetches a user's bookmarked manga ordered by bookmark recency."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT mangas.*
                FROM manga_bookmarks
                INNER JOIN mangas ON mangas.id = manga_bookmarks.manga_id
                WHERE manga_bookmarks.user_id = ?
                ORDER BY manga_bookmarks.created_at DESC, mangas.title ASC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset,)
            )
            return [MangaData().load(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching manga bookmarks: {e}")
            return None
