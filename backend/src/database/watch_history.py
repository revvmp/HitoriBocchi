import sqlite3

from database.models import AnimeData, WatchHistoryData
from utils.logger import get_logger


logger = get_logger(__name__)


class WatchHistoryRepository:
    """
    Resume positions for watch history tracking.
    """
    def upsert_watch_history(self, user_id: int, episode_id: int, current_time_seconds: int, duration_seconds: int) -> bool:
        """
        Inserts or updates a user's watch history for an episode.
        Returns True if the watch history was successfully inserted or updated.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO watch_history (user_id, episode_id, current_time_seconds, duration_seconds)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, episode_id) DO UPDATE SET
                    current_time_seconds = excluded.current_time_seconds,
                    duration_seconds = excluded.duration_seconds,
                    last_watched_at = CURRENT_TIMESTAMP
                """,
                (user_id, episode_id, current_time_seconds, duration_seconds,)
            )
            self.conn.commit()
            return True

        except sqlite3.OperationalError as e:
            logger.error(f"Error upserting watch history: {e}")
            return False
        except sqlite3.IntegrityError as e:
            logger.error(f"Watch history upsert failed. {e}")
            return False

    def fetch_watch_history_by_user_and_episode(self, user_id: int, episode_id: int) -> WatchHistoryData | None:
        """
        Fetches a user's watch history for an episode.
        Returns the watch history with its episode and anime information.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT watch_history.*, episodes.episode_number, episodes.title, animes.*
                FROM watch_history
                INNER JOIN episodes ON episodes.id = watch_history.episode_id
                INNER JOIN animes ON animes.id = episodes.anime_id
                WHERE watch_history.user_id = ? AND watch_history.episode_id = ?
                """,
                (user_id, episode_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None

            joined_info = {
                "episode_number": row[5],
                "episode_title": row[6],
                "anime": AnimeData().load(row[7:]),
            }
            return WatchHistoryData().load(row[:5], joined_info)

        except Exception as e:
            logger.error(f"Error fetching watch history: {e}")
            return None

    def fetch_watch_history_by_user_id(self, user_id: int, limit: int = 20, offset: int = 0) -> list[WatchHistoryData] | None:
        """
        Fetches the most recently watched unfinished episode for each anime.
        Returns the amount of watch history within limit ordered by recency.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT watch_history.*, episodes.episode_number, episodes.title, animes.*
                FROM watch_history
                INNER JOIN episodes ON episodes.id = watch_history.episode_id
                INNER JOIN animes ON animes.id = episodes.anime_id
                WHERE watch_history.user_id = ?
                    AND (
                        watch_history.duration_seconds <= 0
                        OR watch_history.current_time_seconds < watch_history.duration_seconds * 0.9
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM watch_history AS newer_history
                        INNER JOIN episodes AS newer_episode
                            ON newer_episode.id = newer_history.episode_id
                        WHERE newer_history.user_id = watch_history.user_id
                            AND newer_episode.anime_id = episodes.anime_id
                            AND (
                                newer_history.last_watched_at > watch_history.last_watched_at
                                OR (
                                    newer_history.last_watched_at = watch_history.last_watched_at
                                    AND newer_history.episode_id > watch_history.episode_id
                                )
                            )
                    )
                ORDER BY watch_history.last_watched_at DESC, watch_history.episode_id DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset,)
            )
            rows = cursor.fetchall()
            watch_history = []

            for row in rows:
                joined_info = {
                    "episode_number": row[5],
                    "episode_title": row[6],
                    "anime": AnimeData().load(row[7:]),
                }
                watch_history.append(WatchHistoryData().load(row[:5], joined_info))

            return watch_history

        except Exception as e:
            logger.error(f"Error fetching user watch history: {e}")
            return None

    def delete_watch_history_by_user_and_episode(self, user_id: int, episode_id: int) -> bool:
        """
        Deletes a user's watch history for an episode.
        Returns True if the watch history was deleted successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM watch_history WHERE user_id = ? AND episode_id = ?",
                (user_id, episode_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error deleting watch history: {e}")
            return False

    def delete_watch_history_by_user_id(self, user_id: int) -> bool:
        """
        Deletes all watch history for a user.
        Returns True if the watch history was cleared successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("DELETE FROM watch_history WHERE user_id = ?",
                           (user_id,))
            self.conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error deleting user watch history: {e}")
            return False
