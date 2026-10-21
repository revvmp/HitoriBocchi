import sqlite3

from database.models import CommentData
from utils.logger import get_logger


logger = get_logger(__name__)


class CommentRepository:
    """
    Episode comments.
    """
    def create_comment(self, user_id: int, episode_id: int, comment_text: str, parent_id: int | None = None) -> int | None:
        """
        Creates a comment for an episode.
        Returns the new comment id if the comment was created successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO comments (user_id, episode_id, comment_text, parent_id)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, episode_id, comment_text, parent_id,)
            )
            self.conn.commit()
            return cursor.lastrowid

        except sqlite3.OperationalError as e:
            logger.error(f"Error creating comment: {e}")
            return None
        except sqlite3.IntegrityError as e:
            logger.error(f"Comment creation failed. {e}")
            return None

    def fetch_comment_by_id(self, comment_id: int) -> CommentData | None:
        """
        Fetches a comment by its id.
        Returns the comment with its user's username.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT comments.*, users.username FROM comments
                INNER JOIN users ON users.id = comments.user_id
                WHERE comments.id = ?
                """,
                (comment_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return CommentData().load(row[:6], row[6])

        except Exception as e:
            logger.error(f"Error fetching comment: {e}")
            return None

    def fetch_comments_by_episode_id(self, episode_id: int, limit: int = 20, offset: int = 0) -> list[CommentData] | None:
        """
        Fetches comments for an episode.
        Returns the amount of comments within limit with each user's username.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT comments.*, users.username FROM comments
                INNER JOIN users ON users.id = comments.user_id
                WHERE comments.episode_id = ?
                ORDER BY comments.created_at ASC, comments.id ASC
                LIMIT ? OFFSET ?
                """,
                (episode_id, limit, offset,)
            )
            rows = cursor.fetchall()
            return [CommentData().load(row[:6], row[6]) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching comments: {e}")
            return None

    def edit_comment(self, comment_id: int, comment_text: str) -> bool:
        """
        Changes a comment's text.
        Returns True if the comment was changed successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("UPDATE comments SET comment_text = ? WHERE id = ?",
                           (comment_text, comment_id,))
            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error changing comment: {e}")
            return False

    def delete_comment(self, comment_id: int) -> bool:
        """
        Deletes a comment with the given id.
        Returns True if the comment was deleted successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("DELETE FROM comments WHERE id = ?",
                           (comment_id,))
            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error deleting comment: {e}")
            return False
