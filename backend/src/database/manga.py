import sqlite3

from database.models import MangaData
from utils.logger import get_logger


logger = get_logger(__name__)


class MangaRepository:
    """
    Manga metadata and catalog listings.
    """
    def upsert_manga(self, manga_data) -> bool:
        """
        Inserts or updates a manga with scraped MyAnimeList metadata.
        Returns True if the manga was successfully inserted or updated.
        """
        cursor = self.conn.cursor()

        try:
            slug = manga_data["slug"]
            cursor.execute(
                "SELECT id FROM mangas WHERE slug = ? AND id != ?",
                (slug, manga_data["mal_id"],)
            )

            if cursor.fetchone() is not None:
                slug = f"{slug}-{manga_data['mal_id']}"

            cursor.execute(
                """
                INSERT INTO mangas (id, title, title_english, slug, synopsis, image, rating, genres, status, popularity, media_type, current_chapters, total_chapters, anilist_id, mangakatana_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    title_english = excluded.title_english,
                    slug = excluded.slug,
                    synopsis = excluded.synopsis,
                    image = excluded.image,
                    rating = excluded.rating,
                    genres = excluded.genres,
                    status = excluded.status,
                    popularity = excluded.popularity,
                    media_type = excluded.media_type,
                    total_chapters = excluded.total_chapters,
                    anilist_id = COALESCE(excluded.anilist_id, mangas.anilist_id),
                    mangakatana_id = COALESCE(excluded.mangakatana_id, mangas.mangakatana_id),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    manga_data["mal_id"],
                    manga_data["title"],
                    manga_data["title_english"],
                    slug,
                    manga_data["synopsis"],
                    manga_data["image"],
                    manga_data["rating"],
                    manga_data["genres"],
                    manga_data["status"],
                    manga_data["popularity"],
                    manga_data["media_type"],
                    manga_data["current_chapters"],
                    manga_data["total_chapters"],
                    manga_data.get("anilist_id"),
                    manga_data.get("mangakatana_id"),
                )
            )
            self.conn.commit()
            return True

        except sqlite3.OperationalError as e:
            logger.error(f"Error upserting manga: {e}")
            return False
        except sqlite3.IntegrityError as e:
            logger.error(f"Manga upsert failed. {e}")
            return False

    def fetch_manga_by_id(self, mal_id: int) -> MangaData | None:
        """Fetches a manga by its MyAnimeList ID."""
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT * FROM mangas WHERE id = ?", (mal_id,))
            row = cursor.fetchone()
            return MangaData().load(row) if row else None

        except Exception as e:
            logger.error(f"Error fetching manga: {e}")
            return None

    def fetch_manga_by_slug(self, slug: str) -> MangaData | None:
        """Fetches a manga by its slug."""
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT * FROM mangas WHERE slug = ?", (slug,))
            row = cursor.fetchone()
            return MangaData().load(row) if row else None

        except Exception as e:
            logger.error(f"Error fetching manga by slug: {e}")
            return None

    def update_manga_anilist_id(self, manga_id: int, anilist_id: int) -> bool:
        """Updates a manga's AniList ID without changing catalog recency."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "UPDATE mangas SET anilist_id = ? WHERE id = ?",
                (anilist_id, manga_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except sqlite3.OperationalError as e:
            logger.error(f"Error updating manga AniList ID: {e}")
            return False

    def update_manga_mangakatana_id(self, manga_id: int, mangakatana_id: str) -> bool:
        """Updates a manga's MangaKatana ID without changing catalog recency."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "UPDATE mangas SET mangakatana_id = ? WHERE id = ?",
                (mangakatana_id, manga_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except sqlite3.OperationalError as e:
            logger.error(f"Error updating manga MangaKatana ID: {e}")
            return False

    def fetch_all_mangas(self, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[MangaData] | None:
        """Fetches manga ordered by title."""
        cursor = self.conn.cursor()
        availability_filter = """
                WHERE EXISTS (
                    SELECT 1 FROM chapters
                    WHERE chapters.manga_id = mangas.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM mangas
                {availability_filter}
                ORDER BY title ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset,)
            )
            return [MangaData().load(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching all manga: {e}")
            return None

    def search_manga(self, search_query: str, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[MangaData] | None:
        """Searches manga by original or English title."""
        cursor = self.conn.cursor()
        search_pattern = f"%{search_query.strip()}%"
        availability_filter = """
            AND EXISTS (
                SELECT 1 FROM chapters
                WHERE chapters.manga_id = mangas.id
            )
            """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM mangas
                WHERE (title LIKE ? OR title_english LIKE ?)
                {availability_filter}
                ORDER BY popularity IS NULL ASC,
                    popularity ASC,
                    rating DESC,
                    title ASC
                LIMIT ? OFFSET ?
                """,
                (search_pattern, search_pattern, limit, offset,)
            )
            return [MangaData().load(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error searching for manga: {e}")
            return None

    def fetch_mangas_by_status(self, status: str, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[MangaData] | None:
        """Fetches manga with the given status."""
        cursor = self.conn.cursor()
        availability_filter = """
                AND EXISTS (
                    SELECT 1 FROM chapters
                    WHERE chapters.manga_id = mangas.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM mangas
                WHERE status = ?
                {availability_filter}
                ORDER BY rating DESC, title ASC
                LIMIT ? OFFSET ?
                """,
                (status, limit, offset,)
            )
            return [MangaData().load(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching manga by status: {e}")
            return None

    def fetch_ongoing_mangas(self, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[MangaData] | None:
        """Fetches manga that MyAnimeList reports as publishing."""
        return self.fetch_mangas_by_status("Publishing", limit, offset, available_only)

    def fetch_manga_by_popularity(self, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[MangaData] | None:
        """Fetches manga ordered by MyAnimeList popularity rank."""
        cursor = self.conn.cursor()
        availability_filter = """
                AND EXISTS (
                    SELECT 1 FROM chapters
                    WHERE chapters.manga_id = mangas.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM mangas
                WHERE popularity IS NOT NULL
                {availability_filter}
                ORDER BY popularity ASC, title ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset,)
            )
            return [MangaData().load(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching manga by popularity: {e}")
            return None

    def fetch_manga_by_rating(self, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[MangaData] | None:
        """Fetches manga ordered by rating."""
        cursor = self.conn.cursor()
        availability_filter = """
                AND EXISTS (
                    SELECT 1 FROM chapters
                    WHERE chapters.manga_id = mangas.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM mangas
                WHERE rating IS NOT NULL
                {availability_filter}
                ORDER BY rating DESC, title ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset,)
            )
            return [MangaData().load(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching manga by rating: {e}")
            return None

    def fetch_mangas_by_latest_chapter(self, limit: int = 20, offset: int = 0) -> list[MangaData] | None:
        """Fetches manga ordered by when their newest stored chapter was added."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT mangas.*, latest_chapter.chapter_number
                FROM mangas
                INNER JOIN chapters AS latest_chapter
                    ON latest_chapter.id = (
                        SELECT chapters.id
                        FROM chapters
                        WHERE chapters.manga_id = mangas.id
                        ORDER BY chapters.created_at DESC, chapters.id DESC
                        LIMIT 1
                    )
                ORDER BY latest_chapter.created_at DESC,
                    latest_chapter.id DESC,
                    mangas.title ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset,)
            )
            mangas = []

            for row in cursor.fetchall():
                manga = MangaData().load(row[:-1])
                manga.latest_chapter_number = row[-1]
                mangas.append(manga)

            return mangas

        except Exception as e:
            logger.error(f"Error fetching manga by latest chapter: {e}")
            return None

    def update_manga_chapter_counts(self, manga_id: int, current_chapters: int) -> bool:
        """Updates a manga's stored chapter count and catalog update time."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE mangas
                SET current_chapters = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (current_chapters, manga_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating manga chapter count: {e}")
            return False

    def delete_manga(self, manga_id: int) -> bool:
        """Deletes a manga and its dependent records."""
        cursor = self.conn.cursor()

        try:
            cursor.execute("DELETE FROM mangas WHERE id = ?", (manga_id,))
            self.conn.commit()
            return cursor.rowcount > 0

        except sqlite3.OperationalError as e:
            logger.error(f"Error deleting manga: {e}")
            return False

    def delete_mangas_without_chapters(self) -> int | None:
        """Deletes all manga that have no stored chapter rows."""
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                DELETE FROM mangas
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM chapters
                    WHERE chapters.manga_id = mangas.id
                )
                """
            )
            self.conn.commit()
            return cursor.rowcount

        except sqlite3.OperationalError as e:
            logger.error(f"Error deleting manga without chapters: {e}")
            return None
