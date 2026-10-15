from msflib.account.config import AccountSettings
from msflib.auth.config import AuthSettings
from msflib.core.config import CoreSettings, SettingsBase
from msflib.tenancy import TenancySettings
from msflib.workspaces.config import WorkspaceSettings


class AppSettings(
    WorkspaceSettings, TenancySettings, AccountSettings, AuthSettings, CoreSettings, SettingsBase
):
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    REDIS_HOST: str | None = None
    REDIS_PORT: str | None = None
    REDIS_PASSWORD: str | None = None

    INVALID_JWT_EXPIRE: int | None = 3600
    EMAIL_TEMPLATES_DIR: str = "./app/email-templates/build"
    PASSWORD_RESET_PATH: str = "/password-reset"

    # File storage
    STORAGE_METHOD: str | None = "file"
    STORAGE_PATH: str | None = "./uploads"

    # S3 / Cloudflare R2 Object Storage
    STORAGE_BUCKET_NAME: str | None = None
    AWS_ENDPOINT_URL_S3: str | None = None

    # SQLite database default
    SQLITE_DATABASE_URI: str = "sqlite:///./test.db"

    # Server-Sent Event Stream settings.
    STREAM_RETRY_TIMEOUT: int = 15000  # millisecond
    STREAM_DELAY: int = 1  # second


settings = AppSettings()
