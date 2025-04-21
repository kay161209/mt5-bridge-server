#!/usr/bin/env python
"""
MT5セッションマネージャーの直接テスト

このスクリプトはAPIを使わずにsession_managerを直接使用して、
ポータブルモードでMT5の初期化を行うテストを実施します。
"""
import os
import sys
import time
import logging
import traceback
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 現在のファイルからの相対パスでappディレクトリを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('session_manager_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("test_session_manager")

# 環境変数の読み込み
env_file = Path(__file__).resolve().parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    logger.info(f"環境変数を読み込みました: {env_file}")
else:
    logger.warning(f".envファイルが見つかりません: {env_file}")

# session_managerモジュールをインポート
try:
    from app.session_manager import SessionManager, configure_logger
    logger.info("SessionManagerモジュールをインポートしました")
except ImportError as e:
    logger.error(f"SessionManagerモジュールのインポートに失敗しました: {e}")
    sys.exit(1)

# MT5の設定値
MT5_PORTABLE_PATH = os.getenv("MT5_PORTABLE_PATH", r"C:\MetaTrader5-Portable\terminal64.exe")
SESSIONS_BASE_PATH = os.getenv("SESSIONS_BASE_PATH", r"C:\mt5-sessions-test")
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

# MT5プロセスを直接起動するためのオーバーライドメソッド
def custom_run_mt5_process(mt5_exec_path, session_dir, port):
    """MT5プロセスをGUIなしで起動する"""
    logger.info("カスタムMT5プロセス起動を使用")
    
    # バックグラウンドでMT5を起動するコマンド
    cmd = [mt5_exec_path, f"/port:{port}", "/portable", "/skipupdate", "/config:config.ini"]
    logger.info(f"実行コマンド: {' '.join(cmd)}")
    
    try:
        # Windows環境ではDETACHED_PROCESSフラグでGUIなしで実行
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        
        proc = subprocess.Popen(
            cmd,
            cwd=session_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=creation_flags
        )
        
        logger.info(f"MT5プロセスが起動しました: PID={proc.pid}")
        
        # 出力の読み取り
        stdout_data = ""
        stderr_data = ""
        
        # しばらく待機してプロセスの起動を確認
        time.sleep(5)
        
        # プロセスの状態を確認
        returncode = proc.poll()
        if returncode is not None:
            logger.error(f"MT5プロセスが予期せず終了しました。リターンコード: {returncode}")
            output = "== STDOUT ==\n" + stdout_data + "\n== STDERR ==\n" + stderr_data
            logger.error(f"MT5プロセス出力:\n{output}")
            raise RuntimeError(f"MT5プロセスの起動に失敗しました。リターンコード: {returncode}")
        
        return proc, {"stdout": stdout_data, "stderr": stderr_data}
    except Exception as e:
        logger.exception(f"MT5プロセス起動中にエラーが発生しました: {e}")
        raise

def test_session_manager():
    """SessionManagerを使用してMT5セッションを作成・初期化するテスト"""
    logger.info("=" * 50)
    logger.info("SessionManagerテスト開始")
    logger.info("=" * 50)
    
    # 設定値の表示
    logger.info(f"MT5パス: {MT5_PORTABLE_PATH}")
    logger.info(f"セッションベースパス: {SESSIONS_BASE_PATH}")
    logger.info(f"ログイン情報: login={MT5_LOGIN}, server={MT5_SERVER}")
    
    # MT5実行ファイルの確認
    if not os.path.exists(MT5_PORTABLE_PATH):
        logger.error(f"MT5実行ファイルが見つかりません: {MT5_PORTABLE_PATH}")
        return False
    
    logger.info(f"MT5実行ファイルが存在します")
    
    # セッションベースディレクトリの作成
    try:
        os.makedirs(SESSIONS_BASE_PATH, exist_ok=True)
        logger.info(f"セッションディレクトリを作成/確認しました: {SESSIONS_BASE_PATH}")
    except Exception as e:
        logger.error(f"セッションディレクトリの作成に失敗しました: {e}")
        return False
    
    # SessionManagerの初期化
    try:
        logger.info("SessionManagerを初期化します...")
        session_manager = SessionManager(SESSIONS_BASE_PATH, MT5_PORTABLE_PATH)
        
        # MT5プロセス起動メソッドをオーバーライド（モンキーパッチ）
        session_manager._run_mt5_process = custom_run_mt5_process
        logger.info("カスタムMT5起動メソッドを設定しました")
        
        logger.info("SessionManager初期化成功")
    except Exception as e:
        logger.exception(f"SessionManager初期化中にエラーが発生しました: {e}")
        return False
    
    # セッション作成テスト
    try:
        logger.info("=" * 30)
        logger.info("MT5セッション作成を開始します...")
        start_time = time.time()
        
        # セッション作成
        session_id = session_manager.create_session(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"セッション作成完了！ 所要時間: {elapsed_time:.2f}秒")
        logger.info(f"セッションID: {session_id}")
        
        # 作成されたセッションの情報を表示
        try:
            session = session_manager.get_session(session_id)
            logger.info(f"セッション情報:")
            logger.info(f"  - ID: {session.id}")
            logger.info(f"  - ログイン: {session.login}")
            logger.info(f"  - サーバー: {session.server}")
            logger.info(f"  - ポート: {session.port}")
            logger.info(f"  - MT5パス: {session.mt5_path}")
            logger.info(f"  - 作成日時: {session.created_at.isoformat()}")
            
            # セッションディレクトリの内容を表示
            session_dir = os.path.join(SESSIONS_BASE_PATH, session_id)
            logger.info(f"セッションディレクトリ: {session_dir}")
            if os.path.exists(session_dir):
                files = os.listdir(session_dir)
                logger.info(f"セッションディレクトリ内のファイル数: {len(files)}")
                
                # 重要なファイルの存在確認
                important_files = ["terminal64.exe", "portable_mode", "Config/login.ini"]
                for file in important_files:
                    path = os.path.join(session_dir, file)
                    if os.path.exists(path):
                        logger.info(f"  - ファイル存在: {file}")
                    else:
                        logger.warning(f"  - ファイル欠落: {file}")
            
            # MT5プロセスが実行中か確認
            if session.proc.poll() is None:
                logger.info(f"MT5プロセスは実行中です (PID: {session.proc.pid})")
            else:
                logger.warning(f"MT5プロセスは実行されていません (リターンコード: {session.proc.poll()})")
            
            # TODO: その他の検証を追加
            return True
        
        except Exception as e:
            logger.exception(f"セッション情報の取得中にエラーが発生しました: {e}")
            return False
            
    except Exception as e:
        logger.exception(f"MT5セッション作成中にエラーが発生しました: {e}")
        logger.error(f"スタックトレース: {traceback.format_exc()}")
        return False
    
    finally:
        # 全セッションの終了（テスト終了処理）
        try:
            logger.info("テスト終了処理: すべてのセッションを終了します")
            closed_count = session_manager.close_all_sessions()
            logger.info(f"{closed_count}個のセッションを終了しました")
        except Exception as e:
            logger.error(f"セッション終了処理中にエラーが発生しました: {e}")

def main():
    """メイン関数"""
    try:
        # システム情報を表示
        logger.info(f"Python バージョン: {sys.version}")
        logger.info(f"OS: {os.name} {sys.platform}")
        logger.info(f"現在の時刻: {datetime.now().isoformat()}")
        
        # 必須パラメータの確認
        if not MT5_LOGIN or not MT5_PASSWORD or not MT5_SERVER:
            logger.error("MT5ログイン情報が設定されていません。.envファイルを確認してください。")
            logger.info("必要な環境変数: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER")
            return
        
        # セッションマネージャーのテスト
        success = test_session_manager()
        
        if success:
            logger.info("テスト成功: MT5セッションを正常に作成・初期化できました")
        else:
            logger.error("テスト失敗: MT5セッションの作成または初期化に失敗しました")
    
    except Exception as e:
        logger.exception(f"予期しないエラーが発生しました: {e}")
    
    finally:
        logger.info("テスト完了")

if __name__ == "__main__":
    main() 