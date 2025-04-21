import uuid
import subprocess
import time
import os
import shutil
from typing import NamedTuple, Dict, Optional, Any, Tuple
import MetaTrader5 as mt5
from datetime import datetime
import logging
import glob
import zipfile
import io
import sys
import traceback
import json
import platform

# ロガー設定をより詳細に
logging.basicConfig(
    level=logging.DEBUG,  # より詳細なログレベル
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('mt5_session.log', encoding='utf-8')  # ファイルにもログを出力
    ]
)
logger = logging.getLogger("session_manager")

class Session(NamedTuple):
    id: str
    login: int
    server: str
    proc: subprocess.Popen
    port: int
    mt5_path: str  # セッション固有のMT5パス
    created_at: datetime
    last_accessed: datetime

# MT5 APIの詳細なエラーメッセージとコード
MT5_ERROR_CODES = {
    -10005: "IPC タイムアウト - プロセス間通信がタイムアウトしました。MT5との接続確立に失敗しました。",
    -10004: "IPC 初期化エラー - プロセス間通信の初期化に失敗しました。",
    -10003: "IPC テストソケット作成エラー - テスト用ソケットの作成に失敗しました。",
    -10002: "IPC データソケット作成エラー - データ通信用ソケットの作成に失敗しました。",
    -10001: "IPC イベントソケット作成エラー - イベント通知用ソケットの作成に失敗しました。",
    -10000: "IPC エラー - プロセス間通信の一般的なエラーです。",
    -9999: "起動パスが見つかりません - MetaTrader 5の実行パスが見つかりませんでした。",
    -8: "バッファ不足 - データを受信するためのバッファが不足しています。",
    -7: "構造が小さすぎる - データ構造のサイズが不足しています。",
    -6: "データなし - 要求されたデータがありません。",
    -5: "内部エラー - MetaTrader 5 ターミナル内部のエラーです。",
    -4: "メモリ不足 - 関数を実行するためのメモリが不足しています。",
    -3: "無効なパラメータ - 関数に無効なパラメータが渡されました。",
    -2: "ターミナルとの通信が確立されていません。",
    -1: "不明なエラー - 原因不明のエラーが発生しました。",
    0: "エラーなし - 操作は正常に完了しました。",
}

def get_detailed_error(error_code: int, error_message: str) -> str:
    """MT5エラーコードの詳細な説明を取得"""
    detailed_explanation = MT5_ERROR_CODES.get(error_code, "不明なエラーコードです")
    return f"エラーコード: {error_code}, メッセージ: {error_message}\n詳細説明: {detailed_explanation}"

def get_system_info() -> Dict[str, Any]:
    """システム情報を収集"""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "architecture": platform.architecture(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "memory": None,  # 必要に応じてpsutilでメモリ情報を取得可能
    }

class SessionManager:
    def __init__(self, base_path: str, portable_mt5_path: str):
        """
        セッションマネージャーの初期化
        
        Args:
            base_path: セッションフォルダを作成する基本パス
            portable_mt5_path: ポータブル版MT5の実行ファイルパス
        """
        self._sessions: Dict[str, Session] = {}
        self.base_path = base_path
        self.portable_mt5_path = portable_mt5_path
        self._next_port = 8000
        
        # テンプレートディレクトリ - MT5の最小構成をあらかじめコピーしておく場所
        self.template_dir = os.path.join(base_path, "_template")
        
        # システム情報をログに出力
        sys_info = get_system_info()
        logger.info(f"システム情報: {json.dumps(sys_info, indent=2)}")
        
        # 基本ディレクトリがなければ作成
        os.makedirs(base_path, exist_ok=True)
        
        # MT5ポータブル版のパスが存在するか確認
        if not os.path.exists(portable_mt5_path):
            logger.error(f"MT5ポータブル版が見つかりません: {portable_mt5_path}")
        else:
            logger.info(f"MT5ポータブル版が見つかりました: {portable_mt5_path}")
            # ファイルの詳細情報
            file_size = os.path.getsize(portable_mt5_path)
            logger.info(f"  - ファイルサイズ: {file_size} バイト")
            file_permissions = oct(os.stat(portable_mt5_path).st_mode & 0o777)
            logger.info(f"  - ファイル権限: {file_permissions}")
        
        # MT5のインストールディレクトリを取得
        self.mt5_install_dir = os.path.dirname(self.portable_mt5_path)
        if not os.path.exists(self.mt5_install_dir):
            logger.error(f"MT5インストールディレクトリが見つかりません: {self.mt5_install_dir}")
        else:
            logger.info(f"MT5インストールディレクトリが見つかりました: {self.mt5_install_dir}")
            # ディレクトリ内のファイル一覧を表示
            files = os.listdir(self.mt5_install_dir)
            logger.debug(f"MT5インストールディレクトリのファイル一覧: {files}")
        
        # テンプレートディレクトリが存在しなければ作成
        self._prepare_template_directory()
        
        logger.info(f"SessionManager initialized: base_path={base_path}, mt5_path={portable_mt5_path}")
    
    def _prepare_template_directory(self):
        """MT5の最小テンプレートディレクトリを準備"""
        if os.path.exists(self.template_dir) and os.path.isfile(os.path.join(self.template_dir, "terminal64.exe")):
            logger.info(f"テンプレートディレクトリが既に存在します: {self.template_dir}")
            return
        
        logger.info(f"テンプレートディレクトリを作成します: {self.template_dir}")
        if os.path.exists(self.template_dir):
            shutil.rmtree(self.template_dir)
        os.makedirs(self.template_dir, exist_ok=True)
        
        # MT5のルートディレクトリからすべての必要なファイルをコピー
        try:
            # まず基本的な実行ファイルとDLLをコピー
            basic_files = ["terminal64.exe", "*.dll"]
            for pattern in basic_files:
                for file_path in glob.glob(os.path.join(self.mt5_install_dir, pattern)):
                    file_name = os.path.basename(file_path)
                    target_path = os.path.join(self.template_dir, file_name)
                    logger.info(f"基本ファイルコピー: {file_path} -> {target_path}")
                    shutil.copy2(file_path, target_path)
            
            # 重要なディレクトリ構造をコピー
            # ポータブルモードで必須のディレクトリ
            dirs_to_copy = ["Config", "MQL5", "Sounds", "Logs", "Profiles", "Templates"]
            for dir_name in dirs_to_copy:
                src_dir = os.path.join(self.mt5_install_dir, dir_name)
                dst_dir = os.path.join(self.template_dir, dir_name)
                
                if os.path.exists(src_dir):
                    logger.info(f"ディレクトリ全体をコピー: {src_dir} -> {dst_dir}")
                    if os.path.exists(dst_dir):
                        shutil.rmtree(dst_dir)
                    shutil.copytree(src_dir, dst_dir, symlinks=True)
                else:
                    logger.info(f"ディレクトリが存在しないためスキップ: {src_dir}")
                    # 空のディレクトリを作成
                    os.makedirs(dst_dir, exist_ok=True)
            
            # その他の重要なファイルをコピー
            other_files = ["portable.ini"]
            for file_name in other_files:
                src_path = os.path.join(self.mt5_install_dir, file_name)
                if os.path.exists(src_path):
                    dst_path = os.path.join(self.template_dir, file_name)
                    logger.info(f"その他のファイルコピー: {src_path} -> {dst_path}")
                    shutil.copy2(src_path, dst_path)
            
            # portable_modeファイルを作成（ポータブルモードの指定）
            with open(os.path.join(self.template_dir, "portable_mode"), "w") as f:
                f.write("portable")
            
            # terminal.ini の作成 (ポータブルモード用設定)
            terminal_ini_content = """[Common]
Login=0
ProxyEnable=0
CertInstall=0
NewsEnable=0
AutoUpdate=0
"""
            config_dir = os.path.join(self.template_dir, "Config")
            os.makedirs(config_dir, exist_ok=True)
            with open(os.path.join(config_dir, "terminal.ini"), "w") as f:
                f.write(terminal_ini_content)
                
            # 必要に応じて追加のディレクトリを作成
            for add_dir in ["MQL5/Files", "MQL5/Libraries", "MQL5/Experts", "MQL5/Scripts", "MQL5/Include"]:
                os.makedirs(os.path.join(self.template_dir, add_dir), exist_ok=True)
            
            logger.info("テンプレートディレクトリの準備が完了しました")
        except Exception as e:
            logger.exception(f"テンプレートディレクトリの作成中にエラーが発生しました: {e}")
            # エラー時でもセッション作成は続行できるよう、例外は再送出しない
    
    def _run_mt5_process(self, mt5_exec_path: str, session_dir: str, port: int) -> Tuple[subprocess.Popen, Any]:
        """MT5プロセスを起動して出力を記録する"""
        # MT5プロセスを起動 (ポート指定)
        cmd = [mt5_exec_path, f"/port:{port}"]
        logger.info(f"実行コマンド: {' '.join(cmd)}")
        
        # 出力を取得するためのパイプを設定
        proc = subprocess.Popen(
            cmd,
            cwd=session_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='replace'
        )
        
        logger.info(f"MT5プロセス起動: PID={proc.pid}")
        
        # 非ブロッキングで出力を読み取る試み
        stdout_data = ""
        stderr_data = ""
        
        # プロセス起動中に出力を読み取る
        try:
            # 一定時間待機
            time.sleep(5)
            
            # 標準出力・標準エラー出力を読み取り（非ブロッキング）
            if proc.stdout:
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    stdout_data += line
                    logger.debug(f"MT5 STDOUT: {line.strip()}")
            
            if proc.stderr:
                while True:
                    line = proc.stderr.readline()
                    if not line:
                        break
                    stderr_data += line
                    logger.debug(f"MT5 STDERR: {line.strip()}")
        except Exception as e:
            logger.warning(f"プロセス出力の読み取り中にエラー: {e}")
        
        # プロセスの状態を確認
        returncode = proc.poll()
        if returncode is not None:
            logger.error(f"MT5プロセスが予期せず終了しました。リターンコード: {returncode}")
            output = "== STDOUT ==\n" + stdout_data + "\n== STDERR ==\n" + stderr_data
            logger.error(f"MT5プロセス出力:\n{output}")
            raise RuntimeError(f"MT5プロセスが起動に失敗しました。リターンコード: {returncode}")
        
        return proc, {"stdout": stdout_data, "stderr": stderr_data}
    
    def _initialize_mt5(self, mt5_exec_path: str, login: int, password: str, server: str) -> Dict[str, Any]:
        """MT5を初期化し、詳細な結果を返す"""
        logger.info("MT5初期化開始...")
        logger.info(f"MT5パス: {mt5_exec_path}")
        logger.info(f"ログイン: {login}, サーバー: {server}")
        
        # MT5の初期化前にmt5モジュールの状態をチェック
        try:
            mt5_initialized = mt5.initialize() if not mt5.initialize.__self__.terminal_info() else True
            if mt5_initialized:
                logger.info("MT5は既に初期化されています。シャットダウンします。")
                mt5.shutdown()
                time.sleep(2)
        except Exception as e:
            logger.warning(f"MT5初期状態チェック中にエラー: {e}")
        
        # 初期化を試行
        start_time = time.time()
        success = False
        error_code = None
        error_message = None
        
        try:
            success = mt5.initialize(
                path=mt5_exec_path,
                login=login,
                password=password,
                server=server,
                timeout=60000  # タイムアウトを60秒に設定
            )
            
            if not success:
                error = mt5.last_error()
                error_code = error[0]
                error_message = error[1]
                logger.error(f"MT5初期化エラー: {error}")
                logger.error(f"詳細: {get_detailed_error(error_code, error_message)}")
            else:
                # 成功した場合、接続情報を取得
                logger.info("MT5初期化成功")
                try:
                    terminal_info = mt5.terminal_info()
                    account_info = mt5.account_info()
                    
                    logger.info(f"ターミナル情報: 接続={terminal_info.connected}, 取引許可={terminal_info.trade_allowed}")
                    if account_info:
                        logger.info(f"口座情報: ログインID={account_info.login}, サーバー={account_info.server}")
                except Exception as e:
                    logger.warning(f"MT5情報取得中にエラー: {e}")
        except Exception as e:
            logger.exception(f"MT5初期化中に例外が発生: {e}")
            error_message = str(e)
            error_code = -99999
            success = False
        
        elapsed_time = time.time() - start_time
        logger.info(f"MT5初期化処理時間: {elapsed_time:.2f}秒")
        
        return {
            "success": success,
            "error_code": error_code,
            "error_message": error_message,
            "elapsed_time": elapsed_time
        }
    
    def create_session(self, login: int, password: str, server: str) -> str:
        """
        新しいMT5セッションを作成
        
        Args:
            login: MT5ログインID
            password: MT5パスワード
            server: MT5サーバー
            
        Returns:
            セッションID
        """
        # セッションIDを生成
        sid = uuid.uuid4().hex
        
        # セッション用のディレクトリを作成
        session_dir = os.path.join(self.base_path, sid)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
        os.makedirs(session_dir, exist_ok=True)
        
        # このセッション用のポートを割り当て
        port = self._next_port
        self._next_port += 1
        
        logger.info(f"新規セッション作成: id={sid}, login={login}, server={server}, port={port}")
        logger.info(f"セッションディレクトリ: {session_dir}")
        
        try:
            # テンプレートディレクトリが存在するかチェック
            if not os.path.exists(self.template_dir) or not os.path.isfile(os.path.join(self.template_dir, "terminal64.exe")):
                logger.warning("テンプレートディレクトリが見つからないか不完全です。再作成します。")
                self._prepare_template_directory()
            
            # テンプレートディレクトリからファイルをコピー (高速)
            start_time = time.time()
            logger.info("テンプレートからMT5ファイルをセッションディレクトリにコピー中...")
            
            for item in os.listdir(self.template_dir):
                src_path = os.path.join(self.template_dir, item)
                dst_path = os.path.join(session_dir, item)
                
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)
                elif os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path, symlinks=True)
            
            # セッション固有の設定ファイルを上書き
            config_dir = os.path.join(session_dir, "Config")
            os.makedirs(config_dir, exist_ok=True)
            
            # login.ini の作成 (セッション固有のログイン情報)
            login_ini_content = f"""[Login]
Server={server}
Login={login}
Password={password}
ProxyEnable=0
"""
            with open(os.path.join(config_dir, "login.ini"), "w") as f:
                f.write(login_ini_content)
            
            copy_time = time.time() - start_time
            logger.info(f"MT5ファイルのコピーが完了しました (所要時間: {copy_time:.2f}秒)")
            
            # セッション固有のMT5実行ファイルパス
            mt5_exec_path = os.path.join(session_dir, "terminal64.exe")
            
            if not os.path.exists(mt5_exec_path):
                raise FileNotFoundError(f"MT5実行ファイルが見つかりません: {mt5_exec_path}")
            
            logger.info(f"MT5実行ファイルが存在します: {mt5_exec_path}")
            
            # MT5プロセスを起動して出力を取得
            proc, process_output = self._run_mt5_process(mt5_exec_path, session_dir, port)
            
            # プロセスが起動するまで待機
            logger.info("MT5プロセス起動待機中... (60秒)")
            time.sleep(60)  # より長い待機時間
            
            # MT5に接続
            init_result = self._initialize_mt5(mt5_exec_path, login, password, server)
            
            if not init_result["success"]:
                # エラーがあればプロセスを終了し、ディレクトリを削除
                error_code = init_result["error_code"]
                error_message = init_result["error_message"]
                
                # より詳細なエラー情報を作成
                error_detail = {
                    "error_code": error_code,
                    "error_message": error_message,
                    "detailed_error": get_detailed_error(error_code, error_message),
                    "process_output": process_output,
                    "session_dir": session_dir,
                    "mt5_path": mt5_exec_path,
                    "elapsed_time": init_result["elapsed_time"]
                }
                
                logger.error(f"MT5初期化エラーの詳細: {json.dumps(error_detail, indent=2)}")
                
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                
                try:
                    # エラー情報を保存
                    with open(os.path.join(session_dir, "error_log.json"), "w") as f:
                        json.dump(error_detail, f, indent=2)
                    
                    # ディレクトリは削除せず、エラー診断のために残す
                    # shutil.rmtree(session_dir)
                    logger.info(f"エラー診断用にセッションディレクトリを保持: {session_dir}")
                except Exception as e:
                    logger.error(f"エラーログ保存中に例外発生: {e}")
                    
                detailed_error = get_detailed_error(error_code, error_message)
                raise RuntimeError(f"MT5 初期化エラー: {error_code} - {error_message}\n{detailed_error}")
            
            logger.info("MT5初期化成功")
            
            # セッション情報を保存
            now = datetime.now()
            session = Session(
                id=sid,
                login=login,
                server=server,
                proc=proc,
                port=port,
                mt5_path=mt5_exec_path,
                created_at=now,
                last_accessed=now
            )
            self._sessions[sid] = session
            
            return sid
            
        except Exception as e:
            logger.exception(f"セッション作成中に例外発生: {e}")
            
            # スタックトレースをログに記録
            trace = traceback.format_exc()
            logger.error(f"スタックトレース: {trace}")
            
            # クリーンアップ
            try:
                if 'proc' in locals() and proc:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            except:
                pass
                
            # エラー診断用にディレクトリを残す
            # try:
            #     shutil.rmtree(session_dir)
            # except:
            #     pass
                
            raise
    
    def get_session(self, sid: str) -> Session:
        """
        セッションIDからセッション情報を取得
        
        Args:
            sid: セッションID
            
        Returns:
            セッション情報
        """
        if sid not in self._sessions:
            raise KeyError(f"セッション {sid} が見つかりません")
        
        # 最終アクセス時間を更新
        session = self._sessions[sid]
        updated_session = session._replace(last_accessed=datetime.now())
        self._sessions[sid] = updated_session
        
        return updated_session
    
    def close_session(self, sid: str) -> bool:
        """
        セッションを終了し、リソースを解放
        
        Args:
            sid: セッションID
            
        Returns:
            成功したらTrue
        """
        if sid not in self._sessions:
            return False
        
        session = self._sessions.pop(sid)
        logger.info(f"セッション終了: {sid}")
        
        # MT5接続をシャットダウン
        try:
            mt5.shutdown()
            logger.info("MT5シャットダウン完了")
        except Exception as e:
            logger.error(f"MT5シャットダウンエラー: {e}")
        
        # プロセスを終了
        try:
            logger.info(f"プロセス終了: PID={session.proc.pid}")
            session.proc.terminate()
            try:
                session.proc.wait(timeout=5)
                logger.info("プロセス正常終了")
            except subprocess.TimeoutExpired:
                logger.warning("プロセス強制終了")
                session.proc.kill()
        except Exception as e:
            logger.error(f"プロセス終了エラー: {e}")
        
        # セッションディレクトリを削除
        try:
            session_dir = os.path.join(self.base_path, sid)
            logger.info(f"セッションディレクトリ削除: {session_dir}")
            shutil.rmtree(session_dir)
        except Exception as e:
            logger.error(f"ディレクトリ削除エラー: {e}")
        
        return True
    
    def get_all_sessions(self) -> Dict[str, Dict]:
        """すべてのセッション情報を取得"""
        return {
            sid: {
                "id": s.id,
                "login": s.login,
                "server": s.server,
                "port": s.port,
                "mt5_path": s.mt5_path,
                "created_at": s.created_at.isoformat(),
                "last_accessed": s.last_accessed.isoformat(),
                "age_seconds": (datetime.now() - s.created_at).total_seconds()
            } for sid, s in self._sessions.items()
        }
    
    def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> int:
        """
        一定時間アクセスのないセッションをクリーンアップ
        
        Args:
            max_age_seconds: 最大セッション有効期間（秒）
            
        Returns:
            クリーンアップしたセッション数
        """
        now = datetime.now()
        sessions_to_close = [
            sid for sid, session in self._sessions.items()
            if (now - session.last_accessed).total_seconds() > max_age_seconds
        ]
        
        logger.info(f"{len(sessions_to_close)}個の期限切れセッションをクリーンアップします")
        
        for sid in sessions_to_close:
            self.close_session(sid)
        
        return len(sessions_to_close)
    
    def close_all_sessions(self) -> int:
        """
        すべてのセッションを終了
        
        Returns:
            終了したセッション数
        """
        session_ids = list(self._sessions.keys())
        logger.info(f"{len(session_ids)}個のセッションをすべて終了します")
        
        for sid in session_ids:
            self.close_session(sid)
        
        return len(session_ids)

# グローバルなSessionManagerインスタンス
_session_manager: Optional[SessionManager] = None

def init_session_manager(base_path: str, portable_mt5_path: str):
    """SessionManagerの初期化"""
    global _session_manager
    _session_manager = SessionManager(base_path, portable_mt5_path)

def get_session_manager() -> SessionManager:
    """SessionManagerインスタンスの取得"""
    if _session_manager is None:
        raise RuntimeError("SessionManagerが初期化されていません")
    return _session_manager 