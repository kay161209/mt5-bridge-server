import os
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import find_dotenv, load_dotenv

# ロガー設定
logger = logging.getLogger("config")

# .envファイルの検索とロード
dotenv_path = find_dotenv()
if dotenv_path:
    logger.info(f".envファイルを読み込みました: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    logger.warning(".envファイルが見つかりません。環境変数から設定を読み込みます。")

def check_env_var(env_var, default=None, var_type=str):
    """環境変数を安全に取得し、指定された型に変換する"""
    value = os.environ.get(env_var)
    if value is None:
        if default is not None:
            logger.warning(f"環境変数 {env_var} が設定されていません。デフォルト値 {default} を使用します。")
            return default
        logger.warning(f"環境変数 {env_var} が設定されておらず、デフォルト値もありません。")
        return None
    
    try:
        if var_type == bool:
            return value.lower() in ('true', 'yes', 'y', '1')
        return var_type(value)
    except ValueError:
        logger.warning(f"環境変数 {env_var} の値 '{value}' を {var_type.__name__} に変換できません。")
        if default is not None:
            logger.warning(f"デフォルト値 {default} を使用します。")
            return default
        return None

class Settings(BaseSettings):
    # API認証設定
    bridge_token: str = "development_token"
    
    # MT5設定
    mt5_portable_path: str = r"C:\MetaTrader5-Portable"  # ポータブルモードのMT5がインストールされているディレクトリ
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    
    # セッション管理設定
    sessions_base_path: str = r"C:\mt5-sessions"  # 各セッション用のMT5コピーが作成されるディレクトリ
    session_inactive_timeout: int = 3600
    cleanup_interval: int = 60
    max_session_age_hours: int = 24
    session_cleanup_interval_minutes: int = 30
    
    # WebSocket設定
    ws_broadcast_interval: float = 1.0
    
    # ログレベル設定
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = ""
        extra = "ignore"  # 追加のフィールドを許可する設定

# 設定のグローバルインスタンス
settings = Settings()

# 設定値のログ出力（デバッグ用）
logger.debug(f"設定を読み込みました:")
logger.debug(f"  - bridge_token: {settings.bridge_token}")
logger.debug(f"  - mt5_portable_path: {settings.mt5_portable_path}")
logger.debug(f"  - sessions_base_path: {settings.sessions_base_path}")
logger.debug(f"  - log_level: {settings.log_level}")
