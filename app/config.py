from pydantic import BaseSettings, Field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    bridge_token: str = Field(..., env="BRIDGE_TOKEN")
    mt5_path: str = Field(r"C:\MetaTrader5\terminal64.exe", env="MT5_PATH")
    ws_broadcast_interval: float = Field(1.0, env="WS_BROADCAST_INTERVAL")

    class Config:
        env_file = BASE_DIR / ".env"
        case_sensitive = False

settings = Settings() 