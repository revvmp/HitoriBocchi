class MangaData:
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
        self.media_type = ""
        self.current_chapters = 0
        self.latest_chapter_number = ""
        self.total_chapters = ""
        self.updated_at = ""
        self.anilist_id = None
        self.mangakatana_id = None

    def load(self, row: tuple) -> "MangaData":
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
        self.media_type = row[10]
        self.current_chapters = row[11]
        self.total_chapters = row[12]
        self.updated_at = row[13]
        self.anilist_id = row[14]
        self.mangakatana_id = row[15]
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
            "media_type": self.media_type,
            "current_chapters": self.current_chapters,
            "latest_chapter_number": self.latest_chapter_number,
            "total_chapters": self.total_chapters,
            "updated_at": self.updated_at,
        }
