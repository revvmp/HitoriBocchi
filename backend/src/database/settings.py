from utils.logger import get_logger


logger = get_logger(__name__)


class SettingsRepository:
    """
    Site-wide and per-user settings.
    """
    def get_login_required(self) -> bool:
        """
        Returns whether users must log in to access the public site.
        Defaults to requiring login if the setting cannot be read.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT setting_value
                FROM site_settings
                WHERE setting_key = 'login_required'
                """
            )
            row = cursor.fetchone()
            return row is None or row[0] != "0"

        except Exception as e:
            logger.error(f"Error fetching login requirement: {e}")
            return True

    def set_login_required(self, login_required: bool) -> bool:
        """
        Changes whether users must log in to access the public site.
        Returns True if the setting was changed successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO site_settings (setting_key, setting_value)
                VALUES ('login_required', ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                    setting_value = excluded.setting_value
                """,
                ("1" if login_required else "0",)
            )
            self.conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error changing login requirement: {e}")
            return False

    def get_watch_history_tracking_enabled(self, user_id: int) -> bool:
        """
        Returns whether watch history tracking is enabled for a user.
        Defaults to disabled if no preference has been saved.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT watch_history_tracking_enabled
                FROM user_settings
                WHERE user_id = ?
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            return row is not None and row[0] == 1

        except Exception as e:
            logger.error(f"Error fetching watch history setting: {e}")
            return False

    def set_watch_history_tracking_enabled(self, user_id: int, tracking_enabled: bool) -> bool:
        """
        Changes whether watch history is tracked for a user.
        Returns True if the setting was changed successfully.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO user_settings (user_id, watch_history_tracking_enabled)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    watch_history_tracking_enabled = excluded.watch_history_tracking_enabled
                """,
                (user_id, 1 if tracking_enabled else 0)
            )
            self.conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error changing watch history setting: {e}")
            return False
