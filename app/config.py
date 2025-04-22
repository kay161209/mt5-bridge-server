import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict   # ← 変更

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    bridge_token: str = os.getenv("BRIDGE_TOKEN", "development_token")
    mt5_path: str = os.getenv("MT5_PATH", r"C:\MetaTrader5\terminal64.exe")
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    ws_broadcast_interval: float = 1.0  # WebSocketでの配信間隔（秒）
    
    # セッション管理関連
    mt5_portable_path: str = os.getenv("MT5_PORTABLE_PATH", r"C:\MetaTrader5-Portable\terminal64.exe")
    sessions_base_path: str = os.getenv("SESSIONS_BASE_PATH", r"C:\mt5-sessions")
    test_sessions_base_path: str = os.getenv("TEST_SESSIONS_BASE_PATH", r"C:\mt5-sessions-test")
    session_inactive_timeout: int = int(os.getenv("SESSION_INACTIVE_TIMEOUT", "3600"))  # 1時間
    cleanup_interval: int = int(os.getenv("CLEANUP_INTERVAL", "300"))  # 5分ごとにクリーンアップ

    # 新しい構文: model_config
    model_config = SettingsConfigDict(
        env_file = BASE_DIR / ".env",
        case_sensitive = False,
    )

settings = Settings()
