import uuid
import subprocess
import time
import os
import shutil
import json
import sys
from typing import NamedTuple, Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
import logging
import glob
import zipfile
import io
import traceback
import platform
import atexit
import psutil
from pathlib import Path
import select
import signal
from app.config import settings
import hashlib

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

def create_session_directory(session_id: str) -> Tuple[str, str]:
    """セッション用データディレクトリを作成し、Config と accounts.dat のみコピーし、
    MetaTrader5 実行ファイルのパスとセッションディレクトリを返す"""
    session_dir = os.path.join(settings.sessions_base_path, f"session_{session_id}")
    # 既存セッションディレクトリをクリアし、ポータブルインストール全体を複製
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
    # ポータブルインストールをセッションディレクトリへコピー（複数インスタンス起動用）
    shutil.copytree(settings.mt5_portable_path, session_dir)
    # ========== メモリ節約設定 ==========
    # 自動アップデート無効化とログ設定用 common.ini の作成
    cfg_dir = os.path.join(session_dir, 'Config')
    os.makedirs(cfg_dir, exist_ok=True)
    common_ini = os.path.join(cfg_dir, 'common.ini')
    with open(common_ini, 'w', encoding='utf-8') as f:
        f.write('[General]\nSkipUpdate=1\n\n[Logs]\nLevel=error\nMaxLogSizeMB=1\n')
    # チャートを空にして読み込まないように
    charts_dir = os.path.join(session_dir, 'profiles', 'charts', 'Default')
    if os.path.isdir(charts_dir):
        for item in os.listdir(charts_dir):
            path = os.path.join(charts_dir, item)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
    # 不要なインジケータ・EA を削除
    for sub in ('Experts', 'Indicators'):
        mql_dir = os.path.join(session_dir, 'MQL5', sub)
        if os.path.isdir(mql_dir):
            for item in os.listdir(mql_dir):
                fp = os.path.join(mql_dir, item)
                if os.path.isdir(fp):
                    shutil.rmtree(fp)
                else:
                    os.remove(fp)
    # ====================================
    # セッションディレクトリ内の terminal64.exe を実行
    exe_path = os.path.join(session_dir, 'terminal64.exe')
    return exe_path, session_dir

# WorkerSession: 完全独立プロセスで動作する MT5 セッションラッパー
class WorkerSession:
    """サブプロセスで MT5 を初期化・コマンド処理するセッション"""
    def __init__(self, session_id: str, login: int, server: str, proc: subprocess.Popen):
        self.session_id = session_id
        self.login = login
        self.server = server
        self.created_at = datetime.now()
        self.last_access = self.created_at
        self.proc = proc

    def send_command(self, command: dict) -> Any:
        """子プロセスに JSON コマンドを送信し、結果を返す"""
        # 最終アクセス時間更新
        self.last_access = datetime.now()
        # JSON 送信
        self.proc.stdin.write(json.dumps(command) + "\n")
        try:
            self.proc.stdin.flush()
        except OSError:
            # In Windows, flushing a closed pipe may raise Invalid argument; ignore
            pass
        # 応答受信
        line = self.proc.stdout.readline()
        res = json.loads(line)
        if not res.get("success"):
            raise Exception(res.get("error"))
        return res.get("result")

    def cleanup(self):
        """子プロセスの終了処理"""
        try:
            # 終了コマンド送信
            self.proc.stdin.write(json.dumps({"type":"terminate"}) + "\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            pass

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, WorkerSession] = {}

    def get_session(self, session_id: str) -> Optional[WorkerSession]:
        """セッションを取得する"""
        return self.sessions.get(session_id)

    def create_session(self, login: int, password: str, server: str) -> str:
        """新しいセッションを作成する"""
        # セッションIDをSHA256ハッシュで生成
        session_id = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        # MT5実行ファイルパスとセッションデータディレクトリを取得
        exe_path, data_dir = create_session_directory(session_id)
        # worker.py の絶対パスを取得
        root_dir = os.path.dirname(os.path.dirname(__file__))
        worker_path = os.path.join(root_dir, "worker.py")
        if not os.path.isfile(worker_path):
            raise Exception(f"worker.py が見つかりません: {worker_path}")
        # Worker を標準IOで起動
        cmd = [
            sys.executable, worker_path,
            "--id", session_id,
            "--login", str(login),
            "--password", password,
            "--server", server,
            "--exe-path", exe_path,
            "--data-dir", data_dir
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        session = WorkerSession(session_id, login, server, proc)
        self.sessions[session_id] = session
        return session_id

    def cleanup_session(self, session_id: str) -> None:
        """指定されたセッションをクリーンアップする"""
        session = self.sessions.pop(session_id, None)
        if session:
            session.cleanup()
            # MT5 ターミナルプロセスを強制終了
            session_dir = os.path.join(settings.sessions_base_path, f"session_{session_id}")
            exe_path = os.path.join(session_dir, 'terminal64.exe')
            for proc in psutil.process_iter(['exe']):
                try:
                    if proc.info['exe'] and os.path.normcase(proc.info['exe']) == os.path.normcase(exe_path):
                        proc.kill()
                        proc.wait(timeout=5)
                except Exception:
                    pass
            # セッションディレクトリを削除
            if os.path.isdir(session_dir):
                shutil.rmtree(session_dir, ignore_errors=True)

    def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> List[str]:
        """古いセッションをクリーンアップする
        
        Args:
            max_age_seconds (int): セッションの最大有効期間（秒）。デフォルトは1時間（3600秒）
            
        Returns:
            List[str]: クリーンアップされたセッションIDのリスト
        """
        now = datetime.now()
        old_sessions = [
            session_id for session_id, session in self.sessions.items()
            if (now - session.last_access).total_seconds() > max_age_seconds
        ]
        for session_id in old_sessions:
            self.cleanup_session(session_id)
        return old_sessions

    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """全セッションの情報を取得する"""
        now = datetime.now()
        return {
            session_id: {
                "id": session_id,
                "login": session.login,
                "server": session.server,
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_access.isoformat(),
                "age_seconds": (now - session.last_access).total_seconds()
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

    def close_all_sessions(self) -> int:
        """全セッションを終了し、終了したセッション数を返す"""
        count = len(self.sessions)
        self.cleanup()
        return count

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