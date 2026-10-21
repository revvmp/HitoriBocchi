import sqlite3

from utils.logger import get_logger


logger = get_logger(__name__)


class CompletionRepository:
    """
    Unique episode completions recorded at 90% watched.
    """
    def mark_episode_completed(self, user_id: int, episode_id: int) -> bool | None:
        """
        Marks an episode as completed by a user.
        Returns True when a completion was added and False when it already existed.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_episode_completions (user_id, episode_id)
                VALUES (?, ?)
                """,
                (user_id, episode_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except sqlite3.OperationalError as e:
            logger.error(f"Error marking episode completed: {e}")
            return None
        except sqlite3.IntegrityError as e:
            logger.error(f"Episode completion failed. {e}")
            return None

    def fetch_completed_episode_count(self, user_id: int) -> int | None:
        """
        Fetches the number of unique episodes completed by a user.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM user_episode_completions
                WHERE user_id = ?
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else 0

        except Exception as e:
            logger.error(f"Error fetching completed episode count: {e}")
            return None

    def fetch_completed_episode_counts(self) -> dict[int, int] | None:
        """
        Fetches unique episode completion counts grouped by user.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT user_id, COUNT(*)
                FROM user_episode_completions
                GROUP BY user_id
                """
            )
            return {
                row[0]: row[1]
                for row in cursor.fetchall()
            }

        except Exception as e:
            logger.error(f"Error fetching completed episode counts: {e}")
            return None
