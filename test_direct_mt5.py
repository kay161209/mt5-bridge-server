#!/usr/bin/env python
"""
MT5の直接初期化をテストするスクリプト

このスクリプトはMetaTrader5 Pythonライブラリを使用してMT5を直接初期化し、
APIサーバーを経由せずに問題を切り分けるために使用します。
"""
import os
import sys
import time
import logging
import traceback
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_direct_mt5")

# 環境変数の読み込み
env_file = Path(__file__).resolve().parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    logger.info(f"環境変数を読み込みました: {env_file}")
else:
    logger.warning(f".envファイルが見つかりません: {env_file}")

try:
    # MT5ライブラリのインポートを試行
    import MetaTrader5 as mt5
    logger.info(f"MT5ライブラリのバージョン: {mt5.__version__}")
except ImportError:
    logger.error("MetaTrader5ライブラリがインストールされていません")
    logger.info("インストール方法: pip install MetaTrader5")
    sys.exit(1)
except Exception as e:
    logger.exception(f"MT5ライブラリのインポート中にエラーが発生しました: {e}")
    sys.exit(1)

# MT5の設定値
MT5_PATH = os.getenv("MT5_PORTABLE_PATH", r"C:\MetaTrader5-Portable\terminal64.exe")
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

# MT5 APIエラーコードとメッセージの対応
MT5_ERROR_CODES = {
    -10005: "IPC Timeout - プロセス間通信がタイムアウトしました。MT5との接続確立に失敗しました。",
    -10004: "IPC Initialization Error - プロセス間通信の初期化に失敗しました。",
    -10003: "IPC Test Socket Creation Error - テストソケットの作成に失敗しました。",
    -10002: "IPC Data Socket Creation Error - データ通信ソケットの作成に失敗しました。",
    -10001: "IPC Event Socket Creation Error - イベント通知ソケットの作成に失敗しました。",
    -10000: "IPC Error - プロセス間通信の一般的なエラーです。",
    -9999: "Startup Path Not Found - MetaTrader 5の実行パスが見つかりませんでした。",
    -8: "Insufficient Buffer - データ受信バッファが不足しています。",
    -7: "Structure Too Small - データ構造のサイズが不足しています。",
    -6: "No Data - リクエストされたデータが利用できません。",
    -5: "Internal Error - MetaTrader 5ターミナルの内部エラー。",
    -4: "Insufficient Memory - 関数を実行するためのメモリが不足しています。",
    -3: "Invalid Parameter - 関数に無効なパラメータが渡されました。",
    -2: "Communication with terminal not established - ターミナルとの通信が確立されていません。",
    -1: "Unknown Error - 原因不明のエラーです。",
    0: "No Error - 操作は正常に完了しました。",
}

def get_detailed_error(error_code, error_message):
    """MT5エラーコードの詳細な説明を取得する"""
    detailed_explanation = MT5_ERROR_CODES.get(error_code, "不明なエラーコード")
    return f"エラーコード: {error_code}, メッセージ: {error_message}\n詳細な説明: {detailed_explanation}"

def test_direct_initialize():
    """MT5を直接初期化するテスト"""
    logger.info("=== MT5直接初期化テスト ===")
    
    # MT5実行ファイルの確認
    logger.info(f"MT5パス: {MT5_PATH}")
    if not os.path.exists(MT5_PATH):
        logger.error(f"MT5実行ファイルが見つかりません: {MT5_PATH}")
        return False
    
    logger.info(f"MT5実行ファイルが存在します")
    logger.info(f"ログイン情報: login={MT5_LOGIN}, server={MT5_SERVER}")
    
    # 既存のMT5インスタンスをシャットダウン
    try:
        if mt5.initialize():
            logger.info("既存のMT5接続をシャットダウンします")
            mt5.shutdown()
            time.sleep(2)
    except Exception as e:
        logger.warning(f"既存のMT5シャットダウン中にエラーが発生しました: {e}")
    
    # MT5初期化を試行
    logger.info("MT5の初期化を開始します...")
    start_time = time.time()
    success = False
    
    try:
        # タイムアウト時間を指定して初期化（デフォルトは60秒）
        # portable=Trueでポータブルモードを指定
        success = mt5.initialize(
            path=MT5_PATH,
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
            timeout=120000,  # 120秒
            portable=True
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"初期化処理時間: {elapsed_time:.2f}秒")
        
        if success:
            logger.info("MT5初期化成功!")
            
            # 接続情報を表示
            terminal_info = mt5.terminal_info()
            logger.info(f"ターミナル情報:")
            logger.info(f"  - 接続状態: {terminal_info.connected}")
            logger.info(f"  - 取引許可: {terminal_info.trade_allowed}")
            logger.info(f"  - メール有効: {terminal_info.email_enabled}")
            logger.info(f"  - FTP有効: {terminal_info.ftp_enabled}")
            logger.info(f"  - DLL許可: {terminal_info.dlls_allowed}")
            
            # アカウント情報を表示
            account_info = mt5.account_info()
            if account_info:
                logger.info(f"アカウント情報:")
                logger.info(f"  - ログインID: {account_info.login}")
                logger.info(f"  - サーバー: {account_info.server}")
                logger.info(f"  - 通貨: {account_info.currency}")
                logger.info(f"  - レバレッジ: {account_info.leverage}")
            else:
                logger.warning("アカウント情報を取得できませんでした")
            
            # 利用可能なシンボル数を表示
            symbols_total = mt5.symbols_total()
            logger.info(f"利用可能なシンボル: {symbols_total}個")
            
            # 最初の5つのシンボルを表示
            symbols = mt5.symbols_get()[:5]
            logger.info("シンボル一覧 (最初の5つ):")
            for symbol in symbols:
                logger.info(f"  - {symbol.name}")
        else:
            # エラー情報を表示
            error = mt5.last_error()
            error_code = error[0]
            error_message = error[1]
            
            logger.error(f"MT5初期化エラー: {error}")
            logger.error(get_detailed_error(error_code, error_message))
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception(f"MT5初期化中に例外が発生しました: {e}")
        logger.error(f"処理時間: {elapsed_time:.2f}秒")
        
        # 例外のスタックトレースを表示
        logger.error(f"スタックトレース: {traceback.format_exc()}")
    
    return success

def cleanup():
    """リソースのクリーンアップ"""
    try:
        if mt5.initialize().__self__.terminal_info():
            logger.info("MT5をシャットダウンします")
            mt5.shutdown()
    except:
        pass

def main():
    """メイン関数"""
    try:
        # システム情報を表示
        logger.info(f"Python バージョン: {sys.version}")
        logger.info(f"OS: {os.name} {sys.platform}")
        logger.info(f"現在の時刻: {datetime.now().isoformat()}")
        
        # MT5の初期化テスト
        success = test_direct_initialize()
        
        if success:
            logger.info("テスト成功: MT5を正常に初期化できました")
        else:
            logger.error("テスト失敗: MT5の初期化に失敗しました")
    
    finally:
        # クリーンアップ
        cleanup()
        logger.info("テスト完了")

if __name__ == "__main__":
    main() 