class WatchHistoryData:
    def __init__(self):
        self.user_id = 0
        self.episode_id = 0
        self.current_time_seconds = 0
        self.duration_seconds = 0
        self.last_watched_at = ""
        self.anime_title = ""
        self.episode_number = 0
        self.episode_title = ""
        self.anime_slug = ""
        self.anime_image = ""
        self.anime = None

    def load(self, row: tuple, joined_info: dict = None) -> "WatchHistoryData":
        self.user_id = row[0]
        self.episode_id = row[1]
        self.current_time_seconds = row[2]
        self.duration_seconds = row[3]
        self.last_watched_at = row[4]

        if joined_info:
            self.episode_number = joined_info.get("episode_number", 0)
            self.episode_title = joined_info.get("episode_title", "")
            self.anime = joined_info.get("anime")

            if self.anime:
                self.anime_title = self.anime.title
                self.anime_slug = self.anime.slug
                self.anime_image = self.anime.image
            else:
                self.anime_title = joined_info.get("anime_title", "")
                self.anime_slug = joined_info.get("anime_slug", "")
                self.anime_image = joined_info.get("anime_image", "")

        return self

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "episode_id": self.episode_id,
            "current_time_seconds": self.current_time_seconds,
            "duration_seconds": self.duration_seconds,
            "last_watched_at": self.last_watched_at,
            "anime_title": self.anime_title,
            "episode_number": self.episode_number,
            "episode_title": self.episode_title,
            "anime_slug": self.anime_slug,
            "anime_image": self.anime_image,
            "anime": self.anime.to_dict() if self.anime else None,
        }
