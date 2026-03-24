import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

class Config:
    #  FIX 7: SECRET_KEY must come from the environment, never hardcoded.
    # The hardcoded string was overriding the env var on the line below it.
    # Generate a strong key with: python -c "import secrets; print(secrets.token_hex(32))"
    # Then add SECRET_KEY=<that value> to your .env file.
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(32))

    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
    DB_HOST = os.getenv("DB_HOST")
    DB_NAME = os.getenv("DB_NAME")

    # Use SQLite for local development when no MySQL host is configured.
    # Set DB_HOST, DB_USER, DB_PASSWORD, DB_NAME in .env to use MySQL instead.
    if DB_HOST:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
        )
    else:
        _db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rro_local.db")
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{_db_path}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    #  FIX 8: Strict session cookie settings.
    # SESSION_COOKIE_SAMESITE='Lax' prevents the cookie from being sent on
    # cross-site requests, and HTTPONLY blocks JS from reading the cookie.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set to True in production when using HTTPS
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV") == "production"
    TAB_SESSION_TTL_SECONDS = int(os.getenv("TAB_SESSION_TTL_SECONDS", 28800))

    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
    SERIALIZER_SECRET_KEY = os.getenv("SERIALIZER_SECRET_KEY", "fallback-secret-key")

    # ---------------------------------------------------------------------------
    # Bugzilla credentials  (sourced from .env — never hardcode)
    # ---------------------------------------------------------------------------
    BUGZ_USER     = os.getenv("BUGZ_USER")       # e.g. UDU-RT@hpe.com
    BUGZ_PASSWORD = os.getenv("BUGZ_PASSWORD")   # service account password

    # ---------------------------------------------------------------------------
    # ChatHPE credentials  (sourced from .env — never hardcode)
    # ---------------------------------------------------------------------------
    CHATHPE_CLIENT_ID  = os.getenv("CHATHPE_CLIENT_ID")
    CHATHPE_JWT_TOKEN  = os.getenv("CHATHPE_JWT_TOKEN")   # must start with 'Bearer '
    CHATHPE_USER_ID    = os.getenv("CHATHPE_USER_ID")
    CHATHPE_USERNAME   = os.getenv("CHATHPE_USERNAME")
