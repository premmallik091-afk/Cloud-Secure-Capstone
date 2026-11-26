"""Configuration read from environment variables (never hard-code secrets)."""
import os
from urllib.parse import quote_plus

DEFAULT_SECRET = "dev-only-change-me"


def build_db_uri():
    if os.getenv("DATABASE_URL"):          # handy for local dev (e.g. sqlite:///dev.db)
        return os.environ["DATABASE_URL"]
    user = os.getenv("DB_USER", "appuser")
    pwd = quote_plus(os.getenv("DB_PASSWORD", ""))
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "capstone")
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{name}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET)
    SQLALCHEMY_DATABASE_URI = build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    if os.getenv("DB_SSL_CA"):             # encrypt app -> RDS traffic
        SQLALCHEMY_ENGINE_OPTIONS["connect_args"] = {"ssl": {"ca": os.environ["DB_SSL_CA"]}}
    TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "2"))
    LOG_FILE = os.getenv("LOG_FILE", "")   # e.g. /var/log/capstone/app.log
    RATELIMIT_STORAGE_URI = "memory://"
