class AnimeData:
    def __init__(self):
        self.id = 0
        self.title = ""
        self.title_english = ""
        self.slug = ""
        self.synopsis = ""
        self.image = ""
        self.rating = 0.0
        self.genres = []
        self.status = ""
        self.popularity = 0
        self.current_episodes = 0
        self.latest_episode_number = 0
        self.total_episodes = ""
        self.updated_at = ""
        self.anilist_id = None

    def load(self, row: tuple) -> "AnimeData":
        self.id = row[0]
        self.title = row[1]
        self.title_english = row[2]
        self.slug = row[3]
        self.synopsis = row[4]
        self.image = row[5]
        self.rating = float(row[6] or 0.0)
        self.genres = row[7].split(",") if row[7] else []
        self.status = row[8]
        self.popularity = row[9]
        self.current_episodes = row[10]
        self.total_episodes = row[11]
        self.updated_at = row[12]
        self.anilist_id = row[13] if len(row) > 13 else None
        return self

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "title_english": self.title_english,
            "slug": self.slug,
            "synopsis": self.synopsis,
            "image": self.image,
            "rating": self.rating,
            "genres": self.genres,
            "status": self.status,
            "popularity": self.popularity,
            "current_episodes": self.current_episodes,
            "latest_episode_number": self.latest_episode_number,
            "total_episodes": self.total_episodes,
            "updated_at": self.updated_at,
        }
