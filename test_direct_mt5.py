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
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_direct_mt5.log', encoding='utf-8')
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

# 環境変数の表示（パスワードは表示しない）
logger.info("環境変数の設定:")
logger.info(f"MT5_PATH: {os.getenv('MT5_PATH', 'Not set')}")
logger.info(f"MT5_LOGIN: {os.getenv('MT5_LOGIN', 'Not set')}")
logger.info(f"MT5_SERVER: {os.getenv('MT5_SERVER', 'Not set')}")

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

# MT5の設定値
MT5_PATH = os.getenv("MT5_PORTABLE_PATH", r"C:\MetaTrader5-Portable\terminal64.exe")

# ログイン情報の安全な変換
try:
    MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
except ValueError:
    logger.error(f"MT5_LOGIN を整数に変換できません: {os.getenv('MT5_LOGIN', 'Not set')}")
    MT5_LOGIN = 0

MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")

# サーバー名はそのまま使用（スペースなども保持）
MT5_SERVER = os.getenv("MT5_SERVER", "")

# 環境変数が適切に設定されているか確認
if not MT5_PATH or not os.path.exists(MT5_PATH):
    logger.error(f"MT5実行ファイルが見つかりません: {MT5_PATH}")
    logger.info("正しいMT5_PORTABLE_PATHを.envファイルに設定してください")
    sys.exit(1)

if MT5_LOGIN == 0:
    logger.error("有効なMT5_LOGINが設定されていません")
    sys.exit(1)
    
if not MT5_PASSWORD:
    logger.error("MT5_PASSWORDが設定されていません")
    sys.exit(1)
    
if not MT5_SERVER:
    logger.error("MT5_SERVERが設定されていません")
    sys.exit(1)

def create_mt5_session():
    """MT5セッションディレクトリを作成し設定する"""
    # セッションディレクトリを作成
    session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt5_test_session")
    os.makedirs(session_dir, exist_ok=True)
    logger.info(f"テスト用セッションディレクトリ: {session_dir}")
    
    # Config ディレクトリを作成
    config_dir = os.path.join(session_dir, "Config")
    os.makedirs(config_dir, exist_ok=True)
    
    # 1. portable_mode ファイルの作成
    portable_path = os.path.join(session_dir, "portable_mode")
    with open(portable_path, "w") as f:
        f.write("portable")
    
    # 2. terminal.iniファイルを作成 - GUIを非表示にする設定
    terminal_ini_path = os.path.join(config_dir, "terminal.ini")
    with open(terminal_ini_path, "w", encoding="utf-8") as f:
        f.write("[Window]\n")
        f.write("Maximized=0\n")
        f.write("Width=1\n")
        f.write("Height=1\n")
        f.write("Left=-10000\n")  # 画面外に配置
        f.write("Top=-10000\n")   # 画面外に配置
        f.write("[Common]\n")
        f.write("Login=0\n")
        f.write("ProxyEnable=0\n")
        f.write("NewsEnable=0\n")
        f.write("AutoUpdate=0\n")
        f.write("StartupMode=2\n")  # サイレントモード
    logger.info(f"terminal.iniファイルを作成しました: {terminal_ini_path}")
    
    # 重要: MT5実行ファイルをセッションディレクトリにコピー
    try:
        mt5_exe_dest = os.path.join(session_dir, "terminal64.exe")
        # 既にファイルが存在する場合は上書きしない
        if not os.path.exists(mt5_exe_dest):
            import shutil
            logger.info(f"MT5実行ファイルをコピーします: {MT5_PATH} -> {mt5_exe_dest}")
            shutil.copy2(MT5_PATH, mt5_exe_dest)
        else:
            logger.info(f"MT5実行ファイルは既に存在します: {mt5_exe_dest}")
    except Exception as e:
        logger.error(f"MT5実行ファイルのコピーに失敗しました: {e}")
    
    return session_dir

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
    
    # 既存のMT5 Pythonモジュール接続をクリア
    try:
        # MT5モジュールを後で初期化するためにここでインポート
        import MetaTrader5 as mt5
        logger.info(f"MT5ライブラリのバージョン: {mt5.__version__}")
        
        # 既存の接続をシャットダウン
        if mt5.initialize():
            logger.info("既存のMT5接続をシャットダウンします")
            mt5.shutdown()
            time.sleep(3)
    except Exception as e:
        logger.warning(f"MT5モジュール操作中にエラーが発生しました: {e}")
    
    # MT5プロセスを確実に終了
    if os.name == 'nt':
        try:
            logger.info("既存のMT5プロセスを確認・終了します...")
            subprocess.run(["taskkill", "/F", "/IM", "terminal64.exe"], 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(2)
        except Exception as e:
            logger.warning(f"既存プロセス終了中にエラー: {e}")
    
    # セッションディレクトリの準備
    session_dir = create_mt5_session()
    mt5_session_path = os.path.join(session_dir, "terminal64.exe")
    
    if not os.path.exists(mt5_session_path):
        logger.error(f"MT5実行ファイルがセッションディレクトリに存在しません: {mt5_session_path}")
        return False
    
    logger.info("セッションディレクトリの準備が完了しました")
    
    # 直接APIを使った初期化
    try:
        logger.info("MT5 APIを使用して直接初期化を開始します...")
        start_time = time.time()
        
        # 初期化パラメータを設定
        logger.info(f"初期化パラメータ:")
        logger.info(f"  - パス: {mt5_session_path}")
        logger.info(f"  - ログイン: {MT5_LOGIN}")
        logger.info(f"  - サーバー: {MT5_SERVER}")
        
        # 初期化を実行 - 実行ファイルのパスとポータブルモードだけを指定
        success = mt5.initialize(
            path=mt5_session_path,
            portable=True,
            timeout=60000  # 60秒
        )
        
        # 初期化が成功したか確認
        if not success:
            error = mt5.last_error()
            logger.error(f"MT5基本初期化エラー: {error}")
            logger.error(get_detailed_error(error[0], error[1]))
            return False
        
        logger.info("基本初期化成功。ログイン試行...")
        
        # ログイン試行
        login_success = mt5.login(
            login=MT5_LOGIN,
            password=MT5_PASSWORD, 
            server=MT5_SERVER
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"初期化・ログイン処理時間: {elapsed_time:.2f}秒")
        
        if not login_success:
            error = mt5.last_error()
            logger.error(f"MT5ログインエラー: {error}")
            logger.error(get_detailed_error(error[0], error[1]))
            return False
        
        logger.info("MT5ログイン成功!")
        
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
        
        # シンボル情報を表示
        try:
            symbols_total = mt5.symbols_total()
            logger.info(f"利用可能なシンボル: {symbols_total}個")
            
            if symbols_total > 0:
                symbols = mt5.symbols_get()[:5]
                logger.info("シンボル一覧 (最初の5つ):")
                for symbol in symbols:
                    logger.info(f"  - {symbol.name}")
        except Exception as e:
            logger.warning(f"シンボル情報取得エラー: {e}")
        
        return login_success
                
    except Exception as e:
        logger.exception(f"テスト実行中に例外が発生しました: {e}")
        logger.error(f"スタックトレース: {traceback.format_exc()}")
        return False
        
    finally:
        # MT5のPythonモジュール接続をクリーンアップ
        try:
            logger.info("MT5接続をクリーンアップします")
            mt5.shutdown()
        except:
            pass

def cleanup():
    """リソースのクリーンアップ"""
    try:
        # MT5モジュールをここで取得
        import MetaTrader5 as mt5
        if hasattr(mt5, 'shutdown'):
            logger.info("MT5をシャットダウンします")
            mt5.shutdown()
    except:
        pass
    
    # Windowsの場合、MT5プロセスを確実に終了
    if os.name == 'nt':
        try:
            logger.info("MT5プロセスをクリーンアップします")
            subprocess.run(["taskkill", "/F", "/IM", "terminal64.exe"], 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    
    except Exception as e:
        logger.exception(f"予期しないエラーが発生しました: {e}")
    
    finally:
        # クリーンアップ
        cleanup()
        logger.info("テスト完了")

if __name__ == "__main__":
    main() 