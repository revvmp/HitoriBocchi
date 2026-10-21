from database import connection
from database.anime import AnimeRepository
from database.bookmarks import BookmarkRepository
from database.chapters import ChapterRepository
from database.comments import CommentRepository
from database.completions import CompletionRepository
from database.episodes import EpisodeRepository
from database.manga import MangaRepository
from database.settings import SettingsRepository
from database.users import UserRepository
from database.watch_history import WatchHistoryRepository


class AnimeDatabase(SettingsRepository, UserRepository, AnimeRepository, EpisodeRepository, MangaRepository, ChapterRepository, BookmarkRepository, CommentRepository, CompletionRepository, WatchHistoryRepository):
    """
    Context manager for the application database.
    Queries are grouped by feature into the mixins defined alongside this module, sharing one connection.
    """
    def __init__(self):
        self.conn = None

    def __enter__(self):
        self.conn = connection.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.close()
