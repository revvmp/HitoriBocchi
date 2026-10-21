class UserData:
    def __init__(self):
        self.id = 0
        self.username = ""
        self.email = ""
        self.is_admin = 0
        self.created_at = ""

    def load(self, row: tuple) -> "UserData":
        self.id = row[0]
        self.username = row[1]
        self.email = row[3]
        self.is_admin = row[4]
        self.created_at = row[5]
        return self

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_admin": self.is_admin,
            "created_at": self.created_at,
        }
