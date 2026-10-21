import sqlite3

from database.models import EpisodeData
from utils.logger import get_logger


logger = get_logger(__name__)


class EpisodeRepository:
    """
    Stored episode rows.
    """
    def upsert_episode(self, episode_data) -> bool:
        """
        episode_data = {
            "anime_id": int,
            "episode_number": int,
            "provider_episode_id": str,
            "title": str,
        }
        Inserts or updates an episode with the given data.
        Returns True if episode was successfully inserted or updated.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO episodes (anime_id, episode_number, provider_episode_id, title)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(anime_id, episode_number) DO UPDATE SET
                    provider_episode_id = excluded.provider_episode_id,
                    title = excluded.title
                """,
                (
                    episode_data["anime_id"],
                    episode_data["episode_number"],
                    episode_data["provider_episode_id"],
                    episode_data["title"],
                )
            )
            self.conn.commit()
            return True

        except sqlite3.OperationalError as e:
            logger.error(f"Error upserting episode: {e}")
            return False
        except sqlite3.IntegrityError as e:
            logger.error(f"Episode upsert failed. {e}")
            return False

    def upsert_episodes(self, episodes_data: list) -> bool:
        """
        Inserts or updates multiple episodes in one transaction.
        Returns True if every episode was successfully inserted or updated.
        """
        cursor = self.conn.cursor()

        try:
            cursor.executemany(
                """
                INSERT INTO episodes (anime_id, episode_number, provider_episode_id, title)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(anime_id, episode_number) DO UPDATE SET
                    provider_episode_id = excluded.provider_episode_id,
                    title = excluded.title
                """,
                [
                    (
                        episode_data["anime_id"],
                        episode_data["episode_number"],
                        episode_data["provider_episode_id"],
                        episode_data["title"],
                    )
                    for episode_data in episodes_data
                ]
            )
            self.conn.commit()
            return True

        except sqlite3.OperationalError as e:
            self.conn.rollback()
            logger.error(f"Error upserting episodes: {e}")
            return False
        except sqlite3.IntegrityError as e:
            self.conn.rollback()
            logger.error(f"Episode batch upsert failed. {e}")
            return False

    def fetch_episode_by_anime_and_number(self, anime_id: int, episode_number: int) -> EpisodeData | None:
        """
        Fetch an episode by its anime id and episode number.
        Returns all information on the episode.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT * FROM episodes WHERE anime_id = ? AND episode_number = ?",
                           (anime_id, episode_number,))
            row = cursor.fetchone()
            if row is None:
                return None
            return EpisodeData().load(row)

        except Exception as e:
            logger.error(f"Error fetching episode: {e}")
            return None

    def fetch_episodes_by_anime_id(self, anime_id: int) -> list[EpisodeData] | None:
        """
        Fetch all episodes for an anime.
        Returns a list of EpisodeData.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM episodes
                WHERE anime_id = ?
                ORDER BY episode_number ASC
                """,
                (anime_id,)
            )
            rows = cursor.fetchall()
            return [EpisodeData().load(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching episodes: {e}")
            return None
