import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]
    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    REGISTRATION_KEY = os.environ["REGISTRATION_KEY"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ["JWT_ACCESS_TOKEN_EXPIRES"]))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ["JWT_REFRESH_TOKEN_EXPIRES"]))
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ERROR_MESSAGE_KEY = "message"
    JWT_COOKIE_SECURE = os.environ.get("JWT_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_SESSION_COOKIE = False
    JWT_ACCESS_COOKIE_PATH = "/api/"
    JWT_REFRESH_COOKIE_PATH = "/api/refresh"
