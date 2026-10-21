class CommentData:
    def __init__(self):
        self.id = 0
        self.user_id = 0
        self.username = ""
        self.episode_id = 0
        self.comment_text = ""
        self.parent_id = None
        self.created_at = ""

    def load(self, row: tuple, joined_username: str = None) -> "CommentData":
        self.id = row[0]
        self.user_id = row[1]
        self.episode_id = row[2]
        self.comment_text = row[3]
        self.parent_id = row[4]
        self.created_at = row[5]
        self.username = joined_username or ""
        return self

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "episode_id": self.episode_id,
            "comment_text": self.comment_text,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
        }
