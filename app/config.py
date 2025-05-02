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

# アプリケーションのルートディレクトリを取得
root_dir = os.path.dirname(os.path.dirname(__file__))

# MT5のポータブルインストールパス（環境変数から取得）
mt5_portable_path = os.getenv('MT5_PORTABLE_PATH', os.path.join(root_dir, "MetaTrader5-Portable"))
if not os.path.exists(mt5_portable_path):
    logger.warning(f"MT5ポータブルインストールパスが見つかりません: {mt5_portable_path}")
    logger.warning("環境変数 MT5_PORTABLE_PATH で正しいパスを設定してください")
    raise FileNotFoundError(f"MT5ポータブルインストールが見つかりません: {mt5_portable_path}")

# セッションのベースパス（環境変数から取得可能）
sessions_base_path = os.getenv('MT5_SESSIONS_PATH', os.path.join(root_dir, "mt5-sessions"))

# ログディレクトリ（環境変数から取得可能）
logs_dir = os.getenv('MT5_LOGS_DIR', os.path.join(root_dir, "logs"))

# 設定をログ出力用の辞書として保持
settings_dict = {
    "mt5_portable_path": mt5_portable_path,
    "sessions_base_path": sessions_base_path,
    "logs_dir": logs_dir
}

# パスの存在確認と作成
logger.info(f"MT5ポータブルインストールパス: {mt5_portable_path}")
logger.info(f"セッションベースパス: {sessions_base_path}")
logger.info(f"ログディレクトリ: {logs_dir}")

# 必要なディレクトリを作成
os.makedirs(sessions_base_path, exist_ok=True)
os.makedirs(logs_dir, exist_ok=True)

class Settings(BaseSettings):
    # API認証設定
    bridge_token: str = "development_token"

    # MT5設定
    mt5_portable_path: str = mt5_portable_path
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""

    # セッション管理設定
    sessions_base_path: str = sessions_base_path
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
logger.info("設定を読み込みました:")
logger.info(f"  - MT5ポータブルインストールパス: {settings.mt5_portable_path}")
logger.info(f"  - セッションベースパス: {settings.sessions_base_path}")
logger.info(f"  - ログレベル: {settings.log_level}")
