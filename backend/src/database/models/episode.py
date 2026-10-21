class EpisodeData:
    def __init__(self):
        self.id = 0
        self.anime_id = 0
        self.episode_number = 0
        self.provider_episode_id = ""
        self.title = ""
        self.created_at = ""

    def load(self, row: tuple) -> "EpisodeData":
        self.id = row[0]
        self.anime_id = row[1]
        self.episode_number = row[2]
        self.provider_episode_id = row[3]
        self.title = row[4]
        self.created_at = row[5]
        return self

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "anime_id": self.anime_id,
            "episode_number": self.episode_number,
            "provider_episode_id": self.provider_episode_id,
            "title": self.title,
            "created_at": self.created_at,
        }
