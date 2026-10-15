from pathlib import Path
from sqlalchemy.engine.url import make_url
from sqlmodel import create_engine, Session  # noqa
from msflib.core.config import CoreSettings
from app.core.config import settings


def resolve_sqlite_database_uri(uri: str) -> str:
    """Resolve and sanitize a SQLite database URI.

    Handles:
    - 3-slash typos for container paths like 'sqlite:///app/test.db' when CWD is '/app'
    - Creating missing parent directories
    - Handling paths where Docker VOLUME or mkdir mistakenly created a directory
    - Correct formatting (4 slashes for absolute Unix paths, 3 slashes for Windows)
    """
    url = make_url(uri)
    db_str = url.database
    if not db_str or db_str == ":memory:":
        return uri

    target_path = Path(db_str)

    # If relative path starts with 'app/' while running inside a container whose root
    # directory is '/app' and there is no './app' subfolder, resolve to '/app/...'
    if not target_path.is_absolute():
        if target_path.parts and target_path.parts[0] == "app":
            app_root = Path("/app")
            if app_root.is_dir() and not (Path.cwd() / "app").is_dir():
                target_path = app_root / Path(*target_path.parts[1:])
            else:
                target_path = target_path.resolve()
        else:
            target_path = target_path.resolve()
    else:
        target_path = target_path.resolve()

    # If the target path is an existing directory (e.g. from Docker VOLUME instruction),
    # SQLite cannot open a directory as a file. If it's empty, remove it; if it cannot
    # be removed (such as an active mount point), place the database file inside it.
    if target_path.is_dir():
        try:
            target_path.rmdir()
        except OSError:
            target_path = target_path / "test.db"

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    posix_path = target_path.as_posix()
    if posix_path.startswith("/"):
        clean_path = posix_path.lstrip("/")
        return f"sqlite:////{clean_path}"
    return f"sqlite:///{posix_path}"


core_settings: CoreSettings = settings.scope("CORE")
if core_settings.USE_SQLITE:
    sqlite_uri = resolve_sqlite_database_uri(core_settings.SQLITE_DATABASE_URI)
    core_settings.SQLITE_DATABASE_URI = sqlite_uri
    engine = create_engine(
        sqlite_uri,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=core_settings.DB_DEBUG_MODE,
    )
else:
    engine = create_engine(
        str(core_settings.SQLALCHEMY_DATABASE_URI),
        pool_pre_ping=True,
        echo=core_settings.DB_DEBUG_MODE,
    )
