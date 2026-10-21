import sqlite3

from database.models import AnimeData
from utils.logger import get_logger


logger = get_logger(__name__)


class AnimeRepository:
    """
    Anime metadata and catalog listings.
    """
    def upsert_anime(self, anime_data) -> bool:
        """
        anime_data = {
            "mal_id": int,
            "title": str,
            "title_english": str,
            "slug": str,
            "synopsis": str,
            "image": str,
            "rating": float,
            "genres": str,
            "status": str,
            "popularity": int,
            "current_episodes": int,
            "total_episodes": str,
            "anilist_id": int | None
        }
        Inserts or updates an anime with the given data.
        Returns True if anime was successfully inserted or updated.
        """
        cursor = self.conn.cursor()

        try:
            slug = anime_data["slug"]
            cursor.execute(
                "SELECT id FROM animes WHERE slug = ? AND id != ?",
                (slug, anime_data["mal_id"],)
            )

            if cursor.fetchone() is not None:
                slug = f"{slug}-{anime_data['mal_id']}"

            cursor.execute(
                """
                INSERT INTO animes (id, title, title_english, slug, synopsis, image, rating, genres, status, popularity, current_episodes, total_episodes, anilist_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    total_episodes = excluded.total_episodes,
                    anilist_id = COALESCE(excluded.anilist_id, animes.anilist_id),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    anime_data["mal_id"],
                    anime_data["title"],
                    anime_data["title_english"],
                    slug,
                    anime_data["synopsis"],
                    anime_data["image"],
                    anime_data["rating"],
                    anime_data["genres"],
                    anime_data["status"],
                    anime_data["popularity"],
                    anime_data["current_episodes"],
                    anime_data["total_episodes"],
                    anime_data.get("anilist_id"),
                )
            )
            self.conn.commit()
            return True

        except sqlite3.OperationalError as e:
            logger.error(f"Error upserting anime: {e}")
            return False
        except sqlite3.IntegrityError as e:
            logger.error(f"Anime upsert failed. {e}")
            return False

    def fetch_anime_by_id(self, mal_id: int) -> AnimeData | None:
        """
        Fetch an anime by its mal_id.
        Returns all information on the anime.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT * FROM animes WHERE id = ?",
                           (mal_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return AnimeData().load(row)

        except Exception as e:
            logger.error(f"Error fetching anime: {e}")
            return None

    def fetch_anime_by_slug(self, slug: str) -> AnimeData | None:
        """
        Fetch an anime by its slug.
        Returns all information on the anime.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT * FROM animes WHERE slug = ?",
                           (slug,))
            row = cursor.fetchone()
            if row is None:
                return None
            return AnimeData().load(row)

        except Exception as e:
            logger.error(f"Error fetching anime by slug: {e}")
            return None

    def fetch_anime_by_anilist_id(self, anilist_id: int) -> AnimeData | None:
        """Fetch stored MAL metadata for an AniList-based provider request."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM animes WHERE anilist_id = ?", (anilist_id,))
        row = cursor.fetchone()
        return AnimeData().load(row) if row is not None else None

    def update_anime_anilist_id(self, anime_id: int, anilist_id: int) -> bool:
        """
        Updates the AniList ID for an anime without changing its catalog update time.
        Returns True if the AniList ID was updated successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "UPDATE animes SET anilist_id = ? WHERE id = ?",
                (anilist_id, anime_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except sqlite3.IntegrityError as e:
            logger.error(f"AniList ID is already assigned to another anime. {e}")
            return False
        except sqlite3.OperationalError as e:
            logger.error(f"Error updating anime AniList ID: {e}")
            return False

    def fetch_all_animes(self, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[AnimeData] | None:
        """
        Fetch all animes.
        Returns the amount of animes within limit.
        """
        cursor = self.conn.cursor()
        availability_filter = """
                WHERE EXISTS (
                    SELECT 1 FROM episodes
                    WHERE episodes.anime_id = animes.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM animes
                {availability_filter}
                ORDER BY title ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset,)
            )
            rows = cursor.fetchall()
            return [AnimeData().load(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching all animes: {e}")
            return None

    def search_anime(self, search_query: str, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[AnimeData] | None:
        """
        Fetch animes given the search_query.
        Returns the amount of animes within limit.
        """
        cursor = self.conn.cursor()
        search_pattern = f"%{search_query.strip()}%"
        availability_filter = """
            AND EXISTS (
                SELECT 1 FROM episodes
                WHERE episodes.anime_id = animes.id
            )
            """ if available_only else ""

        try:
            cursor.execute(
            f"""
            SELECT * FROM animes
            WHERE (title LIKE ? OR title_english LIKE ?)
            {availability_filter}
            ORDER BY popularity IS NULL ASC,
                popularity ASC,
                rating DESC,
                title ASC
            LIMIT ? OFFSET ?
            """,
            (search_pattern, search_pattern, limit, offset)
        )
            rows = cursor.fetchall()
            return [AnimeData().load(row) for row in rows]

        except Exception as e:
            logger.error(f"Error searching for animes: {e}")
            return None

    def fetch_animes_by_status(self, status: str, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[AnimeData] | None:
        """
        Fetch animes with the given status.
        """
        cursor = self.conn.cursor()
        availability_filter = """
                AND EXISTS (
                    SELECT 1 FROM episodes
                    WHERE episodes.anime_id = animes.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM animes
                WHERE status = ?
                {availability_filter}
                ORDER BY rating DESC
                LIMIT ? OFFSET ?
                """,
                (status, limit, offset,)
            )
            rows = cursor.fetchall()
            return [AnimeData().load(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching animes by status: {e}")
            return None

    def fetch_ongoing_animes(self, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[AnimeData] | None:
        """
        Fetch all ongoing animes.
        """
        return self.fetch_animes_by_status("Currently Airing", limit, offset, available_only)

    def fetch_anime_by_popularity(self, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[AnimeData] | None:
        """
        Fetches animes ordered by popularity ranking.
        """
        cursor = self.conn.cursor()
        availability_filter = """
                AND EXISTS (
                    SELECT 1 FROM episodes
                    WHERE episodes.anime_id = animes.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM animes
                WHERE popularity IS NOT NULL
                {availability_filter}
                ORDER BY popularity ASC, title ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset,)
            )
            rows = cursor.fetchall()
            return [AnimeData().load(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching animes by popularity: {e}")
            return None

    def fetch_animes_by_genre(self, genre: str, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[AnimeData] | None:
        """
        Fetches animes by genre.
        Returns the amount of animes within limit.
        """
        cursor = self.conn.cursor()
        genre_pattern = f"%{genre.strip()}%"
        availability_filter = """
                AND EXISTS (
                    SELECT 1 FROM episodes
                    WHERE episodes.anime_id = animes.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM animes
                WHERE genres LIKE ?
                {availability_filter}
                ORDER BY title ASC
                LIMIT ? OFFSET ?
                """,
                (genre_pattern, limit, offset,)
            )
            rows = cursor.fetchall()
            return [AnimeData().load(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching animes by genre: {e}")
            return None

    def fetch_anime_by_rating(self, limit: int = 20, offset: int = 0, available_only: bool = False) -> list[AnimeData] | None:
        """
        Fetches animes ordered by rating.
        """
        cursor = self.conn.cursor()
        availability_filter = """
                AND EXISTS (
                    SELECT 1 FROM episodes
                    WHERE episodes.anime_id = animes.id
                )
                """ if available_only else ""

        try:
            cursor.execute(
                f"""
                SELECT * FROM animes
                WHERE rating IS NOT NULL
                {availability_filter}
                ORDER BY rating DESC, title ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset,)
            )
            rows = cursor.fetchall()
            return [AnimeData().load(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching animes by rating: {e}")
            return None

    def fetch_animes_by_latest_episode(self, limit: int = 20, offset: int = 0) -> list[AnimeData] | None:
        """
        Fetches animes with their latest episode ordered by when it was added.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT animes.*, latest_episode.episode_number
                FROM animes
                INNER JOIN episodes AS latest_episode
                    ON latest_episode.id = (
                        SELECT episodes.id
                        FROM episodes
                        WHERE episodes.anime_id = animes.id
                        ORDER BY episodes.created_at DESC, episodes.id DESC
                        LIMIT 1
                    )
                WHERE animes.status = ?
                ORDER BY latest_episode.created_at DESC,
                    latest_episode.id DESC,
                    animes.title ASC
                LIMIT ? OFFSET ?
                """,
                ("Currently Airing", limit, offset,)
            )
            rows = cursor.fetchall()
            animes = []

            for row in rows:
                anime = AnimeData().load(row[:-1])
                anime.latest_episode_number = row[-1]
                animes.append(anime)

            return animes

        except Exception as e:
            logger.error(f"Error fetching animes by latest episode: {e}")
            return None

    def update_anime_episode_counts(self, anime_id: int, current_episodes: int) -> bool:
        """
        Updates the current episode count for an anime.
        Returns True if episode counts were successfully updated.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE animes
                SET current_episodes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (current_episodes, anime_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating anime episode counts: {e}")
            return False

    def delete_anime(self, anime_id: int) -> bool:
        """
        Deletes an anime with the given id.
        Returns True if the anime was deleted successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("DELETE FROM animes WHERE id = ?",
                           (anime_id,))
            self.conn.commit()
            return cursor.rowcount > 0

        except sqlite3.OperationalError as e:
            logger.error(f"Error deleting anime: {e}")
            return False

    def delete_animes_without_episodes(self) -> int | None:
        """
        Deletes all anime that have no stored episodes.
        Returns the number of anime deleted.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                DELETE FROM animes
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM episodes
                    WHERE episodes.anime_id = animes.id
                )
                """
            )
            self.conn.commit()
            return cursor.rowcount

        except sqlite3.OperationalError as e:
            logger.error(f"Error deleting anime without episodes: {e}")
            return None
