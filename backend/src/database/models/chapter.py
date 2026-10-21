class ChapterData:
    def __init__(self):
        self.id = 0
        self.manga_id = 0
        self.chapter_number = ""
        self.provider_chapter_id = None
        self.title = ""
        self.released_at = None
        self.created_at = ""

    def load(self, row: tuple) -> "ChapterData":
        self.id = row[0]
        self.manga_id = row[1]
        self.chapter_number = row[2]
        self.provider_chapter_id = row[3]
        self.title = row[4]
        self.released_at = row[5]
        self.created_at = row[6]
        return self

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "manga_id": self.manga_id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "released_at": self.released_at,
            "created_at": self.created_at,
        }
