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
import socket
import random
import tempfile
import platform
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
    from app.session_manager import SessionManager, configure_logger, get_detailed_error
    logger.info("SessionManagerモジュールをインポートしました")
except ImportError as e:
    logger.error(f"SessionManagerモジュールのインポートに失敗しました: {e}")
    sys.exit(1)

# MT5の設定値
MT5_PORTABLE_PATH = os.getenv("MT5_PORTABLE_PATH", r"C:\MetaTrader5-Portable\terminal64.exe")
SESSIONS_BASE_PATH = os.getenv("TEST_SESSIONS_BASE_PATH", r"C:\mt5-sessions-test")
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

logger.info("使用する環境変数:")
logger.info(f"MT5_PORTABLE_PATH: {MT5_PORTABLE_PATH}")
logger.info(f"SESSIONS_BASE_PATH: {SESSIONS_BASE_PATH}")
logger.info(f"MT5_LOGIN: {MT5_LOGIN}")
logger.info(f"MT5_SERVER: {MT5_SERVER}")

# MetaTrader5をインポート
try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5モジュールがインストールされていません")
    mt5 = None

# get_detailed_errorが正しくインポートできない場合のバックアップ
MT5_ERROR_CODES = {
    0: "操作は正常に完了しました",
    1: "予期せぬエラー",
    2: "共通エラー",
    3: "無効なパラメータ",
    4: "実行できないサーバー",
    5: "古いバージョン",
    6: "接続がサーバーに確立されていません",
    7: "サーバーがリクエストを拒否しました",
    8: "取引サーバーへの接続が強い暗号化を使用していません",
    9: "アカウントのコードが無効です",
    64: "アカウントが無効です",
    65: "アカウントが無効です",
    128: "取引タイムアウト",
    129: "無効な価格",
    130: "無効なSL/TP",
    131: "無効な取引量",
    132: "市場は閉まっています",
    133: "取引は無効です",
    134: "空き容量がありません",
    135: "価格が変わりました",
    136: "価格がありません",
    137: "ブローカーはビジーです",
    138: "新しい価格",
    139: "注文がロックされています",
    140: "買いのみ可能",
    141: "リクエストが多すぎます",
    142: "注文とポジションの変更はブローカーによって無効にされています",
    143: "ブローカーはビジーです",
    144: "注文の変更はブローカーによって無効にされています",
    145: "ロックの期限切れ",
    146: "注文のアクティブ化の実行がブローカーによってブロックされました",
    147: "デモ口座の注文数は使用可能な投資資産を超えることはできません",
    148: "注文数または注文量が制限を超えています",
    149: "証拠金要件を確認してください",
    150: "過剰な量",
    10004: "リクエストタイムアウト",
    10007: "スレッド起動エラー",
    10013: "ソケットの許可が拒否されました",
    10014: "ソケットが閉じられました",
    10022: "無効な引数",
    10024: "開いているファイルが多すぎます",
    10035: "リソースが一時的に利用できません",
    10036: "操作は進行中です",
    10038: "無効なソケット",
    10048: "アドレスは既に使用されています",
    10050: "ネットワークがダウンしています",
    10052: "ネットワークがリセットされました",
    10053: "ソケット接続が中断されました",
    10054: "ピアによって接続がリセットされました",
    10055: "バッファ領域がありません",
    10057: "ソケットは接続されていません",
    10058: "ソケットがシャットダウンしました",
    10060: "接続がタイムアウトしました",
    10061: "接続が拒否されました",
    10064: "ホストがダウンしています",
    10065: "ルートが見つかりません",
}

def local_get_detailed_error(error_code):
    """
    MT5エラーコードの詳細な説明を取得
    """
    if error_code in MT5_ERROR_CODES:
        return MT5_ERROR_CODES[error_code]
    return f"未知のエラー（コード: {error_code}）"

# 利用可能なポートを見つける関数
def find_available_port(start_port=15000, end_port=16000):
    """
    指定された範囲内で利用可能なポートを見つける
    
    Args:
        start_port: 検索を開始するポート番号
        end_port: 検索を終了するポート番号
        
    Returns:
        利用可能なポート番号、見つからない場合は0
    """
    # ランダムポートの範囲から選択
    ports = list(range(start_port, end_port))
    random.shuffle(ports)
    
    for port in ports:
        try:
            # ソケットを作成してポートをテスト
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            # ポートが利用可能な場合
            if result != 0:
                return port
        except:
            continue
    
    # 利用可能なポートが見つからない場合
    return 0

def custom_run_mt5_process(session_dir, port=None):
    """
    MT5プロセスをカスタム起動します
    """
    logger = logging.getLogger("test_session")
    
    try:
        # 利用可能なポートを見つける
        if port is None:
            port = find_available_port()
            logger.info(f"利用可能なポートを見つけました: {port}")
        
        # terminal.iniファイルを更新
        config_dir = os.path.join(session_dir, "Config")
        os.makedirs(config_dir, exist_ok=True)
        
        terminal_ini_path = os.path.join(config_dir, "terminal.ini")
        
        # terminal.iniの基本内容
        terminal_ini_content = f"""[Common]
Login=0
ProxyEnable=0
CertInstall=0
NewsEnable=0
AutoUpdate=0
FirstStart=0
Community=0
EnableAPI=1
WebRequests=1
[Window]
Maximized=0
Width=800
Height=600
Left=100
Top=100
StartupMode=0
[Charts]
MaxBars=10000
PrintColor=1
SaveDeleted=0
[Network]
CommunityServer=MetaQuotes-Demo
CommunityPassword=
CommunityLastLogin=
NewsServer=news.metaquotes.net
NewsUpdate=0
ProxyServer=
ProxyType=0
ProxyPort=0
ProxyLogin=
SocketsPort={port if port else 0}
"""
        # terminal.iniファイルを保存
        with open(terminal_ini_path, "w") as f:
            f.write(terminal_ini_content)
        logger.info(f"terminal.iniファイルを作成/更新しました（ポート: {port if port else 0}）")
        
        # access.iniファイルも更新
        access_ini_path = os.path.join(config_dir, "access.ini")
        access_ini_content = f"""[Environment]
MQL5Login=0
ProxyEnable=0
ProxyServer=
ProxyLogin=
WebRequests=1
EnableAPI=1
SocketsPort={port if port else 0}
"""
        with open(access_ini_path, "w") as f:
            f.write(access_ini_content)
        
        # portable_modeファイルを作成
        with open(os.path.join(session_dir, "portable_mode"), "w") as f:
            f.write("portable")
            
        # MT5実行ファイルパス
        mt5_exe = os.path.join(session_dir, "terminal64.exe")
        
        # 環境変数をセット
        env = os.environ.copy()
        env['MT5_CONNECTOR_DEBUG'] = '1'
        env['MT5_TIMEOUT'] = '120000'  # 120秒に拡張
        
        # コマンド構築
        if platform.system() == 'Windows':
            cmd = f'"{mt5_exe}" /portable /offline /skipupdate'
            if port:
                cmd += f" /port:{port}"
        else:
            cmd = [mt5_exe, "/portable", "/offline", "/skipupdate"]
            if port:
                cmd.append(f"/port:{port}")
        
        logger.info(f"MT5起動コマンド: {cmd}")
        
        # プロセス起動
        if isinstance(cmd, list):
            proc = subprocess.Popen(
                cmd, 
                cwd=session_dir,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8',
                bufsize=1,
                env=env
            )
        else:
            proc = subprocess.Popen(
                cmd, 
                cwd=session_dir,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8',
                bufsize=1,
                shell=True,
                env=env
            )
        
        logger.info(f"MT5プロセスが起動しました (PID: {proc.pid})")
        
        # 初期化を安定させるために待機
        time.sleep(5)
        
        return proc
    except Exception as e:
        logger.error(f"MT5プロセスの起動中にエラーが発生しました: {e}")
        return None

def test_session_manager():
    """セッションマネージャのテスト"""
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("test_session")
    
    # テスト用の一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        # 元のMT5インストールディレクトリパス
        # 実際の環境に合わせて変更してください
        mt5_install_dir = r"C:\Program Files\MetaTrader 5"
        
        if not os.path.exists(mt5_install_dir):
            logger.error(f"MT5インストールディレクトリが見つかりません: {mt5_install_dir}")
            return
        
        # テスト用のセッションディレクトリ
        session_dir = os.path.join(temp_dir, "mt5_session")
        os.makedirs(session_dir, exist_ok=True)
        
        logger.info(f"テスト用セッションディレクトリを作成しました: {session_dir}")
        
        # 必要なファイルをコピー
        try:
            # Windows環境の場合
            if platform.system() == 'Windows':
                # terminal64.exeをコピー
                terminal_exe = os.path.join(mt5_install_dir, "terminal64.exe")
                if os.path.exists(terminal_exe):
                    import shutil
                    shutil.copy2(terminal_exe, os.path.join(session_dir, "terminal64.exe"))
                    logger.info(f"terminal64.exeをコピーしました")
                else:
                    logger.error(f"terminal64.exeが見つかりません: {terminal_exe}")
                    return
                
                # MT5プロセスを起動
                proc = custom_run_mt5_process(session_dir)
                if not proc:
                    logger.error("MT5プロセスの起動に失敗しました")
                    return
                
                # MT5の初期化
                logger.info("MT5の初期化を試みます...")
                
                # MT5をPythonモジュールとして初期化
                if mt5:
                    # 初期化結果を確認
                    initialize_result = mt5.initialize()
                    
                    if initialize_result:
                        logger.info("MT5の初期化に成功しました")
                        terminal_info = mt5.terminal_info()
                        logger.info(f"MT5ターミナル情報: {terminal_info}")
                        
                        # セッションテスト
                        logger.info("セッション作成テスト")
                        
                        # ここでセッション操作をテスト
                        
                        # 終了処理
                        logger.info("MT5をシャットダウンします")
                        mt5.shutdown()
                    else:
                        error_code = mt5.last_error()
                        try:
                            error_description = get_detailed_error(error_code)
                        except:
                            error_description = local_get_detailed_error(error_code)
                        logger.error(f"MT5の初期化に失敗しました。エラー: {error_code} ({error_description})")
                
                # プロセスを終了
                logger.info("MT5プロセスを終了します")
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
                    logger.info("MT5プロセスを終了しました")
            else:
                logger.info("Windowsプラットフォーム以外ではテストをスキップします")
        
        except Exception as e:
            logger.error(f"テスト実行中にエラーが発生しました: {e}")
            import traceback
            logger.error(traceback.format_exc())

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