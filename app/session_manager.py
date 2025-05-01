import uuid
import subprocess
import time
import os
import shutil
from typing import NamedTuple, Dict, Optional, Any, Tuple, List
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import logging
import glob
import zipfile
import io
import sys
import traceback
import json
import platform
import atexit
import psutil
from pathlib import Path
import select
from multiprocessing import Process, Pipe
import signal
from app.config import settings
from app.mt5_session_process import start_session_process

# 安全なストリームラッパー
def safe_wrap_stream(stream, encoding='utf-8'):
    """標準ストリームを安全にラップする"""
    if stream is None:
        return None
        
    try:
        # すでにラップされていないか確認
        if hasattr(stream, 'buffer'):
            return io.TextIOWrapper(stream.buffer, encoding=encoding, errors='replace')
        return stream
    except (ValueError, AttributeError):
        return stream

# プログラム終了時にIOエラーを防止するため標準ストリームを復元
def reset_streams():
    """プログラム終了時に標準ストリームを復元"""
    try:
        # 標準出力と標準エラー出力を元に戻す
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    except:
        pass

# ロガー設定を改善
def configure_logger(name="session_manager", level=logging.DEBUG):
    """より堅牢なロガー設定"""
    lgr = logging.getLogger(name)
    lgr.setLevel(level)
    
    # ハンドラを追加する前に既存のハンドラを確認
    if lgr.handlers:
        lgr.debug(f"既存のロガーハンドラが存在するため新しいハンドラは追加しません: {len(lgr.handlers)}個")
        return lgr
        
    try:
        # ファイルハンドラ
        os.makedirs('logs', exist_ok=True)
        file_handler = logging.FileHandler(
            os.path.join('logs', f'{name}.log'), 
            encoding='utf-8', 
            mode='a'
        )
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        lgr.addHandler(file_handler)
        
        # コンソールハンドラ - エラー処理強化
        try:
            # シンプルなハンドラを使用
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            lgr.addHandler(console_handler)
        except (ValueError, AttributeError) as e:
            lgr.warning(f"コンソールハンドラの追加に失敗しました: {e}")
    except Exception as e:
        # ロガー設定時のエラーを処理
        print(f"Logger configuration error: {e}")
    
    return lgr

# プロセス終了時のクリーンアップ関数
def cleanup_resources():
    """プログラム終了時にリソースをクリーンアップする"""
    try:
        # MT5接続をシャットダウン
        mt5.shutdown()
    except:
        pass
    
    # ロガーハンドラをクリーンアップ
    try:
        for handler in logger.handlers[:]:
            try:
                handler.close()
                logger.removeHandler(handler)
            except:
                pass
    except:
        pass
    
    # 標準ストリームを復元
    reset_streams()

# 標準出力と標準エラー出力を安全にラップ
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = safe_wrap_stream(sys.stdout)
sys.stderr = safe_wrap_stream(sys.stderr)

# プログラム終了時に実行
atexit.register(reset_streams)
atexit.register(cleanup_resources)

# ロガーの設定を安全に行う
logger = configure_logger("session_manager")

class Session(NamedTuple):
    id: str
    login: int
    server: str
    proc: subprocess.Popen
    port: int
    mt5_path: str  # MT5 path specific to this session
    created_at: datetime
    last_accessed: datetime

# MT5 APIエラーコードとメッセージの対応
MT5_ERROR_CODES = {
    -10005: "IPC Timeout - プロセス間通信がタイムアウトしました。MT5との接続確立に失敗しました。",
    -10004: "IPC Initialization Error - プロセス間通信の初期化に失敗しました。",
    -10003: "IPC Test Socket Creation Error - テストソケットの作成に失敗しました。",
    -10002: "IPC Data Socket Creation Error - データ通信ソケットの作成に失敗しました。",
    -10001: "IPC Event Socket Creation Error - イベント通知ソケット作成または通信送信に失敗しました。",
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

def get_system_info() -> Dict[str, Any]:
    """システムの情報を収集する"""
    info = {}
    
    # OS情報
    info['os'] = platform.system()
    info['os_release'] = platform.release()
    info['os_version'] = platform.version()
    
    # メモリ情報
    memory = psutil.virtual_memory()
    info['memory_total'] = round(memory.total / (1024 * 1024))  # MB単位
    info['memory_used'] = round(memory.used / (1024 * 1024))    # MB単位
    info['memory_percent'] = memory.percent
    
    # CPU情報
    info['cpu_count'] = psutil.cpu_count(logical=True)
    info['cpu_percent'] = psutil.cpu_percent(interval=0.1)
    
    # ディスク情報
    disk = psutil.disk_usage('/')
    info['disk_total'] = round(disk.total / (1024 * 1024 * 1024), 2)  # GB単位
    info['disk_used'] = round(disk.used / (1024 * 1024 * 1024), 2)    # GB単位
    info['disk_percent'] = disk.percent
    
    # 環境変数情報
    env_vars = {}
    for key in ['DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'WINEPREFIX', 'WINEDEBUG', 
                'HOME', 'TERM', 'SHELL', 'USER', 'LANG', 'MT5_HEADLESS']:
        if key in os.environ:
            env_vars[key] = os.environ[key]
    info['env_vars'] = env_vars
    
    # ウィンドウシステム情報（macOSの場合）
    if platform.system() == 'Darwin':
        try:
            # macOSでアクティブなウィンドウ確認コマンド
            window_check = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of processes whose visible is true'],
                capture_output=True, text=True, timeout=2
            )
            info['visible_apps'] = window_check.stdout.strip().split(", ")
        except Exception as e:
            info['visible_apps_error'] = str(e)
    
    # Wine情報（macOSの場合）
    if platform.system() == 'Darwin':
        try:
            # Wine/CrossOverのバージョン確認
            wine_check = subprocess.run(
                ["wine", "--version"], capture_output=True, text=True, timeout=2
            )
            info['wine_version'] = wine_check.stdout.strip()
            
            # Wine設定の確認
            wine_cfg = subprocess.run(
                ["wine", "cmd", "/c", "echo %USERPROFILE%"], 
                capture_output=True, text=True, timeout=2
            )
            info['wine_userprofile'] = wine_cfg.stdout.strip()
        except Exception as e:
            info['wine_info_error'] = str(e)
    
    # 実行中のプロセス情報
    try:
        gui_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username']):
            # GUIプロセスと考えられるもの
            if any(x in proc.info['name'].lower() for x in ['terminal', 'mt5', 'metatrader', 'wine']):
                proc_info = {
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'username': proc.info['username'],
                }
                try:
                    # 追加情報の取得
                    with proc.oneshot():
                        proc_info['cpu_percent'] = proc.cpu_percent(interval=0.1)
                        proc_info['memory_percent'] = proc.memory_percent()
                        proc_info['status'] = proc.status()
                        proc_info['create_time'] = datetime.fromtimestamp(proc.create_time()).strftime('%Y-%m-%d %H:%M:%S')
                        proc_info['cmdline'] = proc.cmdline()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                gui_processes.append(proc_info)
        info['gui_processes'] = gui_processes
    except Exception as e:
        info['processes_error'] = str(e)
    
    return info

def check_gui_status(pid: int) -> Dict[str, Any]:
    """
    MT5プロセスのGUIウィンドウのステータスを確認します
    
    Args:
        pid: MT5プロセスのPID
        
    Returns:
        GUIステータス情報を含む辞書
    """
    result = {
        "gui_detected": False,
        "platform": platform.system(),
        "window_info": {},
        "details": {}
    }
    
    try:
        system = platform.system()
        
        # macOS
        if system == 'Darwin':
            try:
                # アプリケーションのウィンドウを確認
                cmd = [
                    "osascript", 
                    "-e", 
                    f'tell application "System Events" to get name of windows of processes whose unix id is {pid}'
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                result["window_info"]["raw_output"] = proc.stdout.strip()
                
                if proc.stdout.strip() and "MetaTrader" in proc.stdout:
                    result["gui_detected"] = True
                    result["window_info"]["window_titles"] = proc.stdout.strip().split(", ")
            except Exception as e:
                result["details"]["osascript_error"] = str(e)
        
        # Windows
        elif system == 'Windows':
            try:
                # PowerShellを使用してウィンドウを検索
                cmd = [
                    "powershell", 
                    "-Command", 
                    f"Get-Process -Id {pid} | Where-Object {{$_.MainWindowTitle}} | Select-Object -ExpandProperty MainWindowTitle"
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                result["window_info"]["raw_output"] = proc.stdout.strip()
                
                if proc.stdout.strip() and "MetaTrader" in proc.stdout:
                    result["gui_detected"] = True
                    result["window_info"]["window_titles"] = [proc.stdout.strip()]
            except Exception as e:
                result["details"]["powershell_error"] = str(e)
        
        # Linux
        elif system == 'Linux':
            try:
                # xdotoolを使用
                try:
                    # xdotoolでプロセスIDに関連するウィンドウIDを取得
                    cmd = ["xdotool", "search", "--pid", str(pid)]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                    window_ids = proc.stdout.strip().split('\n')
                    result["window_info"]["window_ids"] = window_ids
                    
                    # ウィンドウタイトルを取得
                    window_titles = []
                    for wid in window_ids:
                        if wid:
                            title_cmd = ["xdotool", "getwindowname", wid]
                            title_proc = subprocess.run(title_cmd, capture_output=True, text=True, timeout=1)
                            title = title_proc.stdout.strip()
                            window_titles.append(title)
                            if "MetaTrader" in title:
                                result["gui_detected"] = True
                    
                    result["window_info"]["window_titles"] = window_titles
                except FileNotFoundError:
                    result["details"]["xdotool_missing"] = True
                    
                    # 代替として、プロセスが X サーバーに接続されているか確認
                    try:
                        cmd = ["lsof", "-p", str(pid), "-a", "-d", "DEL"]
                        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                        if "X11" in proc.stdout:
                            result["details"]["x11_connections"] = True
                            # X11接続があれば、GUIプロセスである可能性が高い
                            result["gui_detected"] = True
                    except (FileNotFoundError, subprocess.SubprocessError) as e:
                        result["details"]["lsof_error"] = str(e)
                except Exception as e:
                    result["details"]["xdotool_error"] = str(e)
            except Exception as e:
                result["details"]["linux_detection_error"] = str(e)
                
        # プロセスの追加情報を取得
        try:
            p = psutil.Process(pid)
            with p.oneshot():
                result["process_info"] = {
                    "name": p.name(),
                    "exe": p.exe(),
                    "cmdline": p.cmdline(),
                    "cpu_percent": p.cpu_percent(interval=0.1),
                    "memory_percent": p.memory_percent(),
                    "status": p.status(),
                    "num_threads": p.num_threads(),
                    "connections": len(p.connections()),
                    "open_files": len(p.open_files()),
                    "children": len(p.children()),
                    "nice": p.nice(),
                    "io_counters": p.io_counters()._asdict() if hasattr(p, "io_counters") else None
                }
        except Exception as e:
            result["process_info_error"] = str(e)
        
    except Exception as e:
        result["error"] = str(e)
    
    return result

def create_session_directory(session_id: str) -> str:
    """セッション用のディレクトリを作成し、MT5のファイルをコピーする"""
    try:
        # セッション用のベースディレクトリを作成
        base_dir = os.path.join(settings.sessions_base_path, session_id)
        os.makedirs(base_dir, exist_ok=True)
        
        # MT5のポータブルインストールをコピー
        mt5_dir = os.path.join(base_dir, "mt5")
        if os.path.exists(mt5_dir):
            logger.info(f"既存のMT5ディレクトリを削除: {mt5_dir}")
            shutil.rmtree(mt5_dir)
            
        # MT5のポータブルインストールディレクトリをコピー
        logger.info(f"MT5ポータブルをコピー: {settings.mt5_portable_path} -> {mt5_dir}")
        shutil.copytree(
            settings.mt5_portable_path,
            mt5_dir,
            symlinks=True,  # シンボリックリンクを保持
            ignore=None,    # 全てのファイルをコピー
            dirs_exist_ok=True  # 既存のディレクトリがあっても続行
        )
        
        # 重要なディレクトリの存在確認
        required_dirs = [
            os.path.join(mt5_dir, "Config"),
            os.path.join(mt5_dir, "MQL5"),
            os.path.join(mt5_dir, "MQL5", "Data"),
            os.path.join(mt5_dir, "MQL5", "Logs"),
            os.path.join(mt5_dir, "MQL5", "Files"),
            os.path.join(mt5_dir, "MQL5", "Profiles"),
        ]
        
        # 必要なディレクトリが存在するか確認（作成はしない）
        missing_dirs = []
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                missing_dirs.append(dir_path)
                logger.warning(f"必要なディレクトリが見つかりません: {dir_path}")
        
        if missing_dirs:
            logger.error("MT5ポータブルのコピーが不完全です。以下のディレクトリが不足しています:")
            for dir_path in missing_dirs:
                logger.error(f" - {dir_path}")
            raise Exception("MT5ポータブルのコピーが不完全です")
            
        # 重要なファイルの存在確認
        required_files = [
            os.path.join(mt5_dir, "terminal64.exe"),
            os.path.join(mt5_dir, "Config", "accounts.dat"),
            os.path.join(mt5_dir, "Config", "config.ini"),
        ]
        
        missing_files = []
        for file_path in required_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
                logger.warning(f"重要なファイルが見つかりません: {file_path}")
        
        if missing_files:
            logger.error("MT5ポータブルのコピーが不完全です。以下のファイルが不足しています:")
            for file_path in missing_files:
                logger.error(f" - {file_path}")
            raise Exception("MT5ポータブルのコピーが不完全です")
        
        # terminal.exe のパスを返す
        if platform.system() == "Windows":
            terminal_exe = "terminal64.exe"
        else:
            terminal_exe = "terminal64"
        
        terminal_path = os.path.join(mt5_dir, terminal_exe)
        logger.info(f"MT5セッションディレクトリの作成が完了: {terminal_path}")
        return terminal_path
        
    except Exception as e:
        logger.error(f"セッションディレクトリの作成に失敗: {e}")
        # クリーンアップを試みる
        try:
            if os.path.exists(base_dir):
                shutil.rmtree(base_dir)
        except Exception as cleanup_error:
            logger.error(f"クリーンアップ中にエラー: {cleanup_error}")
        raise

class MT5Session:
    def __init__(self, session_id: str, login: int, password: str, server: str):
        self.session_id = session_id
        self.login = login
        self.password = password
        self.server = server
        self.last_access = datetime.now()
        self.initialized = False
        self.process = None
        self.parent_conn = None
        self.child_conn = None
        self.session_path = None
        self.initialize()

    def initialize(self) -> bool:
        """MT5の初期化とログイン（別プロセスで実行）"""
        try:
            # セッション用のディレクトリを作成
            self.session_path = create_session_directory(self.session_id)
            
            # プロセス間通信用のパイプを作成
            self.parent_conn, self.child_conn = Pipe()
            
            # 新しいプロセスでMT5を起動
            self.process = Process(
                target=start_session_process,
                args=(self.session_id, self.session_path, self.child_conn)
            )
            self.process.start()
            
            # 初期化コマンドを送信
            init_command = {
                "type": "initialize",
                "params": {
                    "login": self.login,
                    "password": self.password,
                    "server": self.server
                }
            }
            self.parent_conn.send(init_command)
            
            # 結果を待機
            if self.parent_conn.poll(timeout=30):  # 30秒でタイムアウト
                result = self.parent_conn.recv()
                if result.get("success"):
                    self.initialized = True
                    logger.info(f"MT5初期化とログイン成功 - セッション: {self.session_id}")
                    return True
                else:
                    error_msg = result.get("error", "不明なエラー")
                    logger.error(f"MT5初期化エラー: {error_msg}")
                    self.cleanup()
                    return False
            else:
                logger.error("MT5初期化がタイムアウトしました")
                self.cleanup()
                return False
                
        except Exception as e:
            logger.error(f"MT5初期化中の例外: {e}")
            self.cleanup()
            return False

    def cleanup(self):
        """セッションのクリーンアップ処理"""
        try:
            if self.parent_conn:
                # 終了コマンドを送信
                try:
                    self.parent_conn.send({"type": "terminate"})
                except:
                    pass
                self.parent_conn.close()
                
            if self.child_conn:
                self.child_conn.close()
                
            if self.process and self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
                if self.process.is_alive():
                    self.process.kill()
                    
            # セッションディレクトリの削除
            if self.session_path:
                session_dir = os.path.dirname(os.path.dirname(self.session_path))
                try:
                    shutil.rmtree(session_dir)
                except Exception as e:
                    logger.error(f"セッションディレクトリの削除に失敗: {e}")
                    
        except Exception as e:
            logger.error(f"セッションクリーンアップ中のエラー: {e}")
        finally:
            self.initialized = False
            self.process = None
            self.parent_conn = None
            self.child_conn = None
            self.session_path = None

    def send_command(self, command: Dict[str, Any]) -> Any:
        """コマンドを子プロセスに送信"""
        if not self.initialized or not self.parent_conn:
            raise Exception("セッションが初期化されていないか、すでに終了しています")
            
        try:
            self.parent_conn.send(command)
            if self.parent_conn.poll(timeout=30):  # 30秒でタイムアウト
                return self.parent_conn.recv()
            else:
                raise Exception("コマンド実行がタイムアウトしました")
        except Exception as e:
            logger.error(f"コマンド送信中のエラー: {e}")
            raise

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, MT5Session] = {}

    def get_session(self, session_id: str) -> Optional[MT5Session]:
        """セッションを取得する"""
        return self.sessions.get(session_id)

    def create_session(self, login: int, password: str, server: str) -> str:
        """新しいセッションを作成する"""
        session_id = f"session_{len(self.sessions) + 1}"
        session = MT5Session(session_id, login, password, server)
        
        if not session.initialized:
            raise Exception("MT5の初期化に失敗しました")
            
        self.sessions[session_id] = session
        return session_id

    def cleanup_session(self, session_id: str) -> None:
        """指定されたセッションをクリーンアップする"""
        session = self.sessions.get(session_id)
        if session:
            session.cleanup()
            del self.sessions[session_id]

    def cleanup_old_sessions(self) -> List[str]:
        """古いセッションをクリーンアップする"""
        now = datetime.now()
        old_sessions = [
            session_id for session_id, session in self.sessions.items()
            if (now - session.last_access).total_seconds() > 3600
        ]
        for session_id in old_sessions:
            self.cleanup_session(session_id)
        return old_sessions

    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """全セッションの情報を取得する"""
        return {
            session_id: {
                "login": session.login,
                "server": session.server,
                "last_access": session.last_access.isoformat()
            }
            for session_id, session in self.sessions.items()
        }

    def execute_command(self, session_id: str, command: str, params: Dict[str, Any]) -> Any:
        """セッションでコマンドを実行する"""
        session = self.get_session(session_id)
        if not session:
            raise Exception(f"セッション {session_id} が見つかりません")
            
        session.last_access = datetime.now()
        return session.send_command({
            "type": command,
            "params": params
        })

    def cleanup(self) -> None:
        """全セッションをクリーンアップする"""
        for session_id in list(self.sessions.keys()):
            self.cleanup_session(session_id)

_session_manager: Optional[SessionManager] = None

def init_session_manager(base_path: str = "", portable_mt5_path: str = "") -> None:
    """セッションマネージャーを初期化する"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()

def get_session_manager() -> SessionManager:
    """セッションマネージャーのインスタンスを取得する"""
    if _session_manager is None:
        init_session_manager()
    return _session_manager 