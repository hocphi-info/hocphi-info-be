"""Cau hinh ung dung — doc tu bien moi truong / file .env.

`pydantic-settings` la cach FastAPI doc config: khai bao 1 class co kieu, moi
thuoc tinh la 1 bien env. Pydantic tu ep kieu (str -> int, "a,b" -> list...) va
bao loi ngay luc khoi dong neu thieu bien bat buoc.

Tuong duong: Go dung `os.Getenv` + parse thu cong / `envconfig`.
"""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres — driver asyncpg. Format: postgresql+asyncpg://user:pass@host:port/db
    database_url: str = Field(
        default="postgresql+asyncpg://hocphi:hocphi@localhost:5432/hocphi",
    )
    # Danh sach origin FE duoc phep goi cheo, dang CSV tho ("http://a,http://b").
    # Giu la `str` (khong phai list[str]): pydantic-settings tu thu json.loads()
    # gia tri env cho field kieu list/complex TRUOC ca validator -> vo hieu voi
    # CSV thuong. Tach CSV o property cors_origins ben duoi thay vi field nay.
    cors_origins_csv: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )
    # In moi cau SQL ra stdout — bat khi debug, tat o CI/prod.
    sql_echo: bool = Field(default=False)

    # Structured logging (Tuan 5). `json` = 1 dong JSON / ban ghi (prod, platform
    # gom stdout); `console` = mau + can le, de doc khi dev.
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    # Nguong log toi thieu — ten level cua stdlib logging (debug/info/warning/...).
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_csv.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Doc settings 1 lan roi cache — moi lan goi tra ve cung 1 object."""
    return Settings()


settings = get_settings()
