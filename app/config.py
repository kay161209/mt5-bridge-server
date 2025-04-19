from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict   # ← 変更

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    bridge_token: str
    mt5_path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    ws_broadcast_interval: float = 1.0

    # 新しい構文: model_config
    model_config = SettingsConfigDict(
        env_file = BASE_DIR / ".env",
        case_sensitive = False,
    )

settings = Settings()
