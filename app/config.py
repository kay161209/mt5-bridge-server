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
    bridge_token: str = check_env_var("BRIDGE_TOKEN", "default_token")
    
    # MT5設定
    mt5_path: str = check_env_var("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
    mt5_login: int = check_env_var("MT5_LOGIN", 0, int)
    mt5_password: str = check_env_var("MT5_PASSWORD", "")
    mt5_server: str = check_env_var("MT5_SERVER", "")
    mt5_portable_path: str = check_env_var("MT5_PORTABLE_PATH", r"C:\MT5_portable\terminal64.exe")
    
    # WebSocket設定
    ws_broadcast_interval: int = check_env_var("WS_BROADCAST_INTERVAL", 1, int)
    
    # セッション管理設定
    sessions_base_path: str = check_env_var("SESSIONS_BASE_PATH", r"C:\mt5-sessions")
    # テスト用セッションパス - コンフィグで使用する場合はここで定義
    # test_sessions_base_path: str = check_env_var("TEST_SESSIONS_BASE_PATH", r"C:\mt5-test-sessions")
    
    # セッションタイムアウト設定
    session_inactive_timeout: int = check_env_var("SESSION_INACTIVE_TIMEOUT", 3600, int)
    cleanup_interval: int = check_env_var("CLEANUP_INTERVAL", 60, int)
    max_session_age_hours: int = check_env_var("MAX_SESSION_AGE_HOURS", 24, int)
    session_cleanup_interval_minutes: int = check_env_var("SESSION_CLEANUP_INTERVAL_MINUTES", 30, int)
    
    # ログレベル設定
    log_level: str = check_env_var("LOG_LEVEL", "INFO")

    class Config:
        # 追加フィールドを許可しない設定に変更
        extra = "forbid"
        env_file = ".env"
        case_sensitive = True

# 設定のグローバルインスタンス
settings = Settings()
