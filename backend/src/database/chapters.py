import sqlite3

from database.models import ChapterData
from utils.logger import get_logger


logger = get_logger(__name__)


class ChapterRepository:
    """
    Stored manga chapter rows.
    """
    def upsert_chapters(self, chapters_data: list) -> bool:
        """Inserts or updates multiple manga chapters in one transaction."""
        cursor = self.conn.cursor()

        try:
            cursor.executemany(
                """
                INSERT INTO chapters (manga_id, chapter_number, provider_chapter_id, title, released_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(manga_id, chapter_number) DO UPDATE SET
                    provider_chapter_id = excluded.provider_chapter_id,
                    title = excluded.title,
                    released_at = COALESCE(excluded.released_at, chapters.released_at)
                """,
                [
                    (
                        chapter_data["manga_id"],
                        chapter_data["chapter_number"],
                        chapter_data["provider_chapter_id"],
                        chapter_data["title"],
                        chapter_data.get("released_at"),
                    )
                    for chapter_data in chapters_data
                ]
            )
            self.conn.commit()
            return True

        except sqlite3.OperationalError as e:
            self.conn.rollback()
            logger.error(f"Error upserting chapters: {e}")
            return False
        except sqlite3.IntegrityError as e:
            self.conn.rollback()
            logger.error(f"Chapter batch upsert failed. {e}")
            return False

    def fetch_chapter_by_manga_and_number(self, manga_id: int, chapter_number: str) -> ChapterData | None:
        """Fetches one chapter by manga ID and canonical chapter number."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "SELECT * FROM chapters WHERE manga_id = ? AND chapter_number = ?",
                (manga_id, chapter_number,)
            )
            row = cursor.fetchone()
            return ChapterData().load(row) if row else None

        except Exception as e:
            logger.error(f"Error fetching chapter: {e}")
            return None

    def fetch_chapters_by_manga_id(self, manga_id: int) -> list[ChapterData] | None:
        """Fetches all stored chapters for a manga, newest number first."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM chapters
                WHERE manga_id = ?
                ORDER BY CAST(chapter_number AS REAL) DESC, chapter_number DESC
                """,
                (manga_id,)
            )
            return [ChapterData().load(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching chapters: {e}")
            return None
