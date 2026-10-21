import sqlite3

from database.models import UserData
from utils.password_hasher import hash_password
from utils.logger import get_logger


logger = get_logger(__name__)


class UserRepository:
    """
    User accounts.
    """
    def fetch_user_by_id(self, user_id: int) -> UserData | None:
        """
        Fetches a user by id.
        Returns all information of the user.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE id=?",
                           (user_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return UserData().load(row)

        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            return None

    def fetch_user(self, username: str) -> UserData | None:
        """
        Fetches a user by username.
        Returns all information of the user.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE username=?",
                           (username,))
            row = cursor.fetchone()
            if row is None:
                return None
            return UserData().load(row)

        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            return None

    def fetch_user_by_email(self, email: str) -> UserData | None:
        """
        Fetches a user by email.
        Returns all information of the user.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE email = ?",
                           (email,))
            row = cursor.fetchone()
            if row is None:
                return None
            return UserData().load(row)

        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    def fetch_all_users(self) -> list[UserData] | None:
        """
        Fetch all users.
        Returns a list of UserData.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM users")
            users = []
            rows = cursor.fetchall()
            for row in rows:
                users.append(UserData().load(row))
            return users

        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            return None

    def get_password_hash(self, username: str) -> str | None:
        """
        Fetches the hashed password of a user.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT password FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()

            return row[0] if row else None

        except Exception as e:
            logger.error(f"Error fetching password hash: {e}")
            return None

    def create_user(self, username: str, email: str, password: str) -> bool:
        """
        Registers a user with the given username, email, and password.
        Returns True if the user was registered successfully.
        """
        cursor = self.conn.cursor()
        hashed_password = hash_password(password)

        try:
            cursor.execute("INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)",
                           (username, email, hashed_password, 0,))
            self.conn.commit()
            return True

        except sqlite3.OperationalError as e:
            logger.error(f"Error creating user: {e}")
            return False
        except sqlite3.IntegrityError as e:
            logger.error(f"User already exists. {e}")
            return False

    def delete_user(self, user_id: int) -> bool:
        """
        Deletes a user with the given id.
        Returns True if the user was deleted successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("DELETE FROM users WHERE id = ?",
                           (user_id,))
            self.conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False

    def edit_user(self, user_id: int, username: str, email: str, is_admin: int, password: str = "") -> bool:
        """
        Changes a user's account information.
        Leaves the existing password unchanged when password is empty.
        """
        cursor = self.conn.cursor()

        try:
            if password:
                cursor.execute(
                    """
                    UPDATE users
                    SET username = ?, email = ?, password = ?, is_admin = ?
                    WHERE id = ?
                    """,
                    (
                        username,
                        email,
                        hash_password(password),
                        is_admin,
                        user_id,
                    )
                )
            else:
                cursor.execute(
                    """
                    UPDATE users
                    SET username = ?, email = ?, is_admin = ?
                    WHERE id = ?
                    """,
                    (username, email, is_admin, user_id,)
                )
            self.conn.commit()
            return cursor.rowcount > 0

        except sqlite3.IntegrityError as e:
            logger.error(f"User account information already exists. {e}")
            return False
        except Exception as e:
            logger.error(f"Error changing user account information: {e}")
            return False
