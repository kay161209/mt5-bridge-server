import uuid
import subprocess
import time
import os
import shutil
from typing import NamedTuple, Dict, Optional, Any, Tuple
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

class SessionManager:
    def __init__(self, base_path: str, portable_mt5_path: str):
        """
        Initialize the session manager
        
        Args:
            base_path: Base path to create session folders
            portable_mt5_path: Path to the portable MT5 executable
        """
        self._sessions: Dict[str, Session] = {}
        self.base_path = base_path
        self.portable_mt5_path = portable_mt5_path
        self._next_port = 8000
        # ロガーを設定
        self.logger = logger
        # セッション管理の設定
        self.config = type('Config', (), {'clean_sessions': False})()
        
        # Template directory - a place to store a minimal MT5 configuration to copy from
        self.template_dir = os.path.join(base_path, "_template")
        
        # Log system information
        sys_info = get_system_info()
        logger.info(f"System information: {json.dumps(sys_info, indent=2)}")
        
        # Create base directory if it doesn't exist
        os.makedirs(base_path, exist_ok=True)
        
        # Check if the MT5 portable path exists
        if not os.path.exists(portable_mt5_path):
            logger.error(f"MT5 portable version not found: {portable_mt5_path}")
        else:
            logger.info(f"MT5 portable version found: {portable_mt5_path}")
            # File details
            file_size = os.path.getsize(portable_mt5_path)
            logger.info(f"  - File size: {file_size} bytes")
            file_permissions = oct(os.stat(portable_mt5_path).st_mode & 0o777)
            logger.info(f"  - File permissions: {file_permissions}")
        
        # Get the MT5 installation directory
        self.mt5_install_dir = os.path.dirname(self.portable_mt5_path)
        if not os.path.exists(self.mt5_install_dir):
            logger.error(f"MT5 installation directory not found: {self.mt5_install_dir}")
        else:
            logger.info(f"MT5 installation directory found: {self.mt5_install_dir}")
            # List files in the directory
            files = os.listdir(self.mt5_install_dir)
            logger.debug(f"Files in MT5 installation directory: {files}")
        
        # Create template directory if it doesn't exist
        self._prepare_template_directory()
        
        logger.info(f"SessionManager initialized: base_path={base_path}, mt5_path={portable_mt5_path}")
    
    def _prepare_template_directory(self):
        """Prepare the minimal MT5 template directory"""
        if os.path.exists(self.template_dir) and os.path.isfile(os.path.join(self.template_dir, "terminal64.exe")):
            logger.info(f"Template directory already exists: {self.template_dir}")
            return
        
        logger.info(f"Creating template directory: {self.template_dir}")
        if os.path.exists(self.template_dir):
            shutil.rmtree(self.template_dir)
        os.makedirs(self.template_dir, exist_ok=True)
        
        # Copy all necessary files from the MT5 root directory
        try:
            # First copy basic executable and DLLs
            basic_files = ["terminal64.exe", "*.dll"]
            for pattern in basic_files:
                for file_path in glob.glob(os.path.join(self.mt5_install_dir, pattern)):
                    file_name = os.path.basename(file_path)
                    target_path = os.path.join(self.template_dir, file_name)
                    logger.info(f"Copying basic file: {file_path} -> {target_path}")
                    shutil.copy2(file_path, target_path)
            
            # Copy important directory structures
            # Directories required for portable mode
            dirs_to_copy = ["Config", "MQL5", "Sounds", "Logs", "Profiles", "Templates"]
            for dir_name in dirs_to_copy:
                src_dir = os.path.join(self.mt5_install_dir, dir_name)
                dst_dir = os.path.join(self.template_dir, dir_name)
                
                if os.path.exists(src_dir):
                    logger.info(f"Copying entire directory: {src_dir} -> {dst_dir}")
                    if os.path.exists(dst_dir):
                        shutil.rmtree(dst_dir)
                    shutil.copytree(src_dir, dst_dir, symlinks=True)
                else:
                    logger.info(f"Directory doesn't exist, skipping: {src_dir}")
                    # Create empty directory
                    os.makedirs(dst_dir, exist_ok=True)
            
            # Copy other important files
            other_files = ["portable.ini"]
            for file_name in other_files:
                src_path = os.path.join(self.mt5_install_dir, file_name)
                if os.path.exists(src_path):
                    dst_path = os.path.join(self.template_dir, file_name)
                    logger.info(f"Copying other file: {src_path} -> {dst_path}")
                    shutil.copy2(src_path, dst_path)
            
            # Create portable_mode file (to specify portable mode)
            with open(os.path.join(self.template_dir, "portable_mode"), "w") as f:
                f.write("portable")
            
            # Create terminal.ini (settings for portable mode)
            terminal_ini_content = """[Common]
Login=0
ProxyEnable=0
CertInstall=0
NewsEnable=0
AutoUpdate=0
[Window]
Maximized=0
Width=800
Height=600
Left=100
Top=100
StartupMode=0
"""
            config_dir = os.path.join(self.template_dir, "Config")
            os.makedirs(config_dir, exist_ok=True)
            with open(os.path.join(config_dir, "terminal.ini"), "w") as f:
                f.write(terminal_ini_content)
                
            # Create additional directories as needed
            for add_dir in ["MQL5/Files", "MQL5/Libraries", "MQL5/Experts", "MQL5/Scripts", "MQL5/Include"]:
                os.makedirs(os.path.join(self.template_dir, add_dir), exist_ok=True)
            
            logger.info("Template directory preparation completed")
        except Exception as e:
            logger.exception(f"Error occurred while creating template directory: {e}")
            # Don't re-raise the exception to allow session creation to continue
    
    def _run_mt5_process(self, session_dir: str, port: int) -> bool:
        """
        MT5プロセスを起動します
        
        Args:
            session_dir: セッションディレクトリ
            port: 使用するポート番号
            
        Returns:
            プロセスが正常に起動したかどうか
        """
        try:
            self.logger.info(f"MT5プロセスを起動します: session_dir={session_dir}, port={port}")
            
            # MT5コマンド
            mt5_exe = os.path.join(session_dir, "terminal64.exe")
            if not os.path.exists(mt5_exe):
                self.logger.error(f"MT5実行ファイルが見つかりません: {mt5_exe}")
                return False
                
            # システム情報をログに記録
            sys_info = get_system_info()
            self.logger.info(f"システム情報: {json.dumps(sys_info, indent=2, ensure_ascii=False)}")
            
            # プロセス環境変数を設定
            env = os.environ.copy()
            
            # 重要な環境変数を設定
            env['MT5_CONNECTOR_DEBUG'] = '1'  # デバッグモードを有効化
            env['MT5_TIMEOUT'] = '60000'      # タイムアウトを長めに設定（ミリ秒）
            
            # macOSやLinuxの場合はWine関連の環境変数を設定
            if platform.system() == 'Darwin' or platform.system() == 'Linux':
                env['WINEDEBUG'] = '-all'
                env['DISPLAY'] = os.environ.get('DISPLAY', ':0.0')
                self.logger.info(f"Wine環境変数を設定: WINEDEBUG=-all, DISPLAY={env['DISPLAY']}")
            
            # Windows環境ではUTF-8モードを有効にする
            if platform.system() == 'Windows':
                env['PYTHONIOENCODING'] = 'utf-8'
                
            # accounts.datファイルの存在確認
            accounts_dat_path = os.path.join(session_dir, "accounts.dat")
            has_account_data = os.path.exists(accounts_dat_path)
            if has_account_data:
                self.logger.info(f"アカウントデータファイルが見つかりました: {accounts_dat_path}")
            else:
                self.logger.info(f"アカウントデータファイルが見つかりません。ログイン情報が必要です。")
            
            # コマンド構築
            if platform.system() == 'Windows':
                cmd_str = f'"{mt5_exe}"'
                
                # 基本オプション
                cmd_str += " /portable"
                
                # オフラインモードを追加
                cmd_str += " /offline"
                
                # ポート指定があれば追加
                if port:
                    cmd_str += f" /port:{port}"
                
                # 必要なオプションを追加
                cmd_str += " /skipupdate"  # 更新をスキップ
                
                cmd = cmd_str
            else:
                cmd = [mt5_exe]
                
                # 基本オプション
                cmd.append("/portable")
                
                # オフラインモードを追加
                cmd.append("/offline")
                
                # ポート指定があれば追加
                if port:
                    cmd.append(f"/port:{port}")
                
                # 必要なオプションを追加
                cmd.append("/skipupdate")  # 更新をスキップ
            
            self.logger.info(f"MT5起動コマンド: {cmd}")
            
            # プロセス起動前にメモリをクリア
            if platform.system() == 'Windows':
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
                    self.logger.info("システムメモリをクリアしました")
                except Exception as e:
                    self.logger.warning(f"メモリクリア中にエラーが発生しました: {e}")
            
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
            
            pid = proc.pid
            self.logger.info(f"MT5プロセスが起動しました (PID: {pid})")
            
            # MT5プロセスを安定させるために少し待機
            time.sleep(2)
            
            # プロセス出力を非同期で読み取る
            def read_output(stream, logger_method, max_lines=20):
                lines = []
                for _ in range(max_lines):
                    try:
                        line = stream.readline()
                        if not line:
                            break
                        lines.append(line.strip())
                    except:
                        break
                if lines:
                    logger_method("\n".join(lines))
                return lines
            
            # 標準出力とエラー出力を読み取り
            stdout_lines = read_output(proc.stdout, lambda msg: self.logger.info(f"MT5出力: {msg}"))
            stderr_lines = read_output(proc.stderr, lambda msg: self.logger.error(f"MT5エラー: {msg}"))
            
            # プロセス状態のモニタリングを少し待ってから行う
            time.sleep(5)
            
            # プロセス状態のモニタリング
            try:
                # プロセスが存在するか確認
                if proc.poll() is not None:
                    self.logger.error(f"MT5プロセスが早期に終了しました。終了コード: {proc.poll()}")
                    
                    # 追加のエラー情報を収集
                    if stderr_lines:
                        self.logger.error(f"MT5プロセスのエラー出力: {stderr_lines}")
                    
                    if stdout_lines:
                        self.logger.info(f"MT5プロセスの標準出力: {stdout_lines}")
                    
                    # 詳細なエラーコードの説明を提供
                    error_code = proc.poll()
                    error_description = "不明なエラー"
                    
                    if error_code == 10053:
                        error_description = "ソケット接続が中断されました。ネットワーク接続またはポート競合の問題の可能性があります。"
                    elif error_code == 10054:
                        error_description = "接続が強制的に閉じられました。サーバーまたはファイアウォールによって接続が拒否された可能性があります。"
                    elif error_code == 1:
                        error_description = "一般的なエラー。起動パラメータまたは設定ファイルに問題がある可能性があります。"
                    
                    self.logger.error(f"MT5エラーの詳細: {error_description}")
                    
                    # MT5プロセスのログファイルをチェック
                    try:
                        logs_dir = os.path.join(session_dir, "logs")
                        if os.path.exists(logs_dir):
                            log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
                            for log_file in sorted(log_files)[-2:]:  # 最新の2つのログファイルを確認
                                log_path = os.path.join(logs_dir, log_file)
                                self.logger.info(f"MT5ログファイルを確認: {log_path}")
                                try:
                                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                                        log_content = f.read(5000)  # 最初の5000文字を読み取る
                                        self.logger.info(f"MT5ログファイル内容:\n{log_content}")
                                except Exception as e:
                                    self.logger.error(f"ログファイルの読み取りに失敗: {e}")
                    except Exception as e:
                        self.logger.error(f"MT5ログファイルの確認中にエラー発生: {e}")
                    
                    return False
                
                # プロセスが実行中の場合
                p = psutil.Process(pid)
                
                # プロセスのメモリと CPU 使用率を記録
                with p.oneshot():
                    mem_info = p.memory_info()
                    mem_mb = mem_info.rss / 1024 / 1024
                    cpu_percent = p.cpu_percent(interval=0.5)
                    self.logger.info(f"MT5プロセス情報: メモリ使用量={mem_mb:.2f}MB, CPU使用率={cpu_percent:.1f}%")
                
                # GUIの状態を確認
                gui_status = check_gui_status(pid)
                self.logger.info(f"MT5 GUIステータス: {json.dumps(gui_status, indent=2, ensure_ascii=False)}")
                
                if not gui_status["gui_detected"]:
                    self.logger.warning(f"MT5 GUIウィンドウが検出されませんでした。ヘッドレスモードで実行されている可能性があります。")
                    # Wine関連のデバッグ情報をログに記録
                    if platform.system() == 'Darwin' or platform.system() == 'Linux':
                        wine_env_vars = {k: v for k, v in os.environ.items() if 'WINE' in k.upper()}
                        self.logger.info(f"Wine環境変数: {json.dumps(wine_env_vars, indent=2, ensure_ascii=False)}")
                
                # セッション情報を更新
                self._current_process = proc
                
                # プロセスのクリーンアップ関数
                def cleanup_process():
                    try:
                        if p.is_running():
                            self.logger.info(f"MT5プロセス(PID: {pid})を終了します")
                            p.terminate()
                            try:
                                p.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                self.logger.warning(f"MT5プロセス(PID: {pid})が5秒以内に終了しませんでした。強制終了します")
                                p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                        self.logger.warning(f"プロセスクリーンアップ中にエラーが発生しました: {e}")
                
                # アプリケーション終了時にプロセスをクリーンアップ
                atexit.register(cleanup_process)
                
            except psutil.NoSuchProcess:
                self.logger.error(f"プロセス(PID: {pid})が見つかりません")
                return False
            except Exception as e:
                self.logger.error(f"プロセス情報の取得中にエラーが発生しました: {e}")
                return False
                
            self.logger.info(f"MT5プロセスが正常に起動しています")
            return True
            
        except Exception as e:
            self.logger.error(f"MT5プロセスの起動中にエラーが発生しました: {str(e)}")
            traceback.print_exc()
            return False
    
    def _initialize_mt5(self, server, login, password, timeout=60) -> Tuple[bool, str]:
        """
        MT5を初期化して接続します。二段階で処理を行います:
        1. MT5の初期化（パスとportableフラグのみ指定）
        2. MT5へのログイン（初期化成功後にログイン情報でログイン）
        
        Args:
            server: MT5サーバー名
            login: MT5ログインID
            password: MT5パスワード
            timeout: 初期化のタイムアウト時間（秒）
        
        Returns:
            (成功したかどうか, エラーメッセージ)
        """
        try:
            # セッションIDを安全に取得
            session_id = getattr(self, 'session_id', 'unknown')
            session_dir = os.path.join(self.base_path, session_id)
            
            # プロセスが起動しているか確認
            # MT5を初期化する前に、プロセスが存在していることを確認
            if not os.path.exists(session_dir):
                error_msg = f"セッションディレクトリが存在しません: {session_dir}"
                self.logger.error(error_msg)
                return False, error_msg
            
            # MT5実行ファイルパスの確認
            mt5_exe_path = os.path.join(session_dir, "terminal64.exe")
            if not os.path.exists(mt5_exe_path):
                error_msg = f"MT5実行ファイルが見つかりません: {mt5_exe_path}"
                self.logger.error(error_msg)
                return False, error_msg
            
            # ログイン情報ファイルやアカウントデータの存在確認
            config_dir = os.path.join(session_dir, "Config")
            connection_file = os.path.join(config_dir, "connection_settings.ini")
            accounts_file = os.path.join(config_dir, "accounts_settings.ini")
            login_file = os.path.join(config_dir, "login.ini")
            accounts_dat_file = os.path.join(session_dir, "accounts.dat")
            
            # ログイン情報ファイルと、アカウントデータファイルの存在確認
            has_login_files = (
                os.path.exists(connection_file) and 
                os.path.exists(accounts_file) and
                os.path.exists(login_file)
            )
            
            has_account_data = os.path.exists(accounts_dat_file)
            
            self.logger.info(f"MT5ライブラリの初期化を開始します（セッション: {session_id}）")
            
            # MT5初期化パラメータを記録
            self.logger.info(f"初期化パラメータ:")
            self.logger.info(f"  - MT5パス: {mt5_exe_path}")
            self.logger.info(f"  - ログイン: {login}")
            self.logger.info(f"  - サーバー: {server}")
            self.logger.info(f"  - タイムアウト: {timeout}秒")
            self.logger.info(f"  - ログインファイル存在: {has_login_files}")
            self.logger.info(f"  - アカウントデータ存在: {has_account_data}")
            
            # MT5が既に初期化されている場合はシャットダウン
            try:
                if mt5.terminal_info() is not None:
                    self.logger.info("MT5は既に初期化されています。再初期化のためシャットダウンします。")
                    mt5.shutdown()
                    time.sleep(2)  # シャットダウン後の安定化待機
            except:
                pass
            
            # MT5プロセスに接続するための待機とリトライ
            max_retries = 3
            retry_interval = 5  # 秒
            success = False
            error_message = ""
            
            for attempt in range(1, max_retries + 1):
                self.logger.info(f"MT5の初期化を試行しています（{attempt}/{max_retries}）...")
                
                try:
                    # セッション固有のディレクトリで起動する際は、パスとportableフラグのみ指定
                    self.logger.info(f"MT5の基本初期化を実行します: パスとportableフラグのみ指定")
                    initialize_result = mt5.initialize(
                        path=mt5_exe_path,
                        portable=True,
                        timeout=min(15000, timeout * 1000)
                    )
                    
                    # 初期化に失敗した場合
                    if not initialize_result:
                        error_code = mt5.last_error()
                        error_msg = f"MT5の初期化に失敗しました。"
                        detailed_error = get_detailed_error(error_code, error_msg)
                        self.logger.error(detailed_error)
                        error_message = detailed_error
                        
                        # リトライ前に少し待機
                        time.sleep(retry_interval)
                        continue
                    
                    self.logger.info("MT5の基本初期化に成功しました。ログインを実行します...")
                    
                    # ログイン実行
                    login_result = mt5.login(
                        login=login,
                        password=password,
                        server=server
                    )
                    
                    # ログインに失敗した場合
                    if not login_result:
                        error_code = mt5.last_error()
                        error_msg = f"MT5サーバーへのログインに失敗しました。"
                        detailed_error = get_detailed_error(error_code, error_msg)
                        self.logger.error(detailed_error)
                        error_message = detailed_error
                        
                        # 失敗した場合はMT5を終了して資源を解放
                        mt5.shutdown()
                        time.sleep(retry_interval)
                        continue
                    
                    self.logger.info(f"MT5サーバーへのログインに成功しました: login={login}, server={server}")
                    success = True
                    break
                    
                except Exception as e:
                    error_message = f"MT5の初期化中に例外が発生しました: {str(e)}"
                    self.logger.error(error_message)
                    time.sleep(retry_interval)
                    continue
            
            # 最終的な結果確認
            if success:
                self.logger.info(f"MT5ライブラリの初期化に成功しました（セッション: {session_id}）")
                
                # アカウント情報を取得して検証
                try:
                    account_info = mt5.account_info()
                    if account_info is None:
                        error_code = mt5.last_error()
                        error_msg = f"MT5アカウント情報の取得に失敗しました。"
                        detailed_error = get_detailed_error(error_code, error_msg)
                        self.logger.error(detailed_error)
                        # 失敗した場合はMT5を終了して資源を解放
                        mt5.shutdown()
                        return False, detailed_error
                    
                    # ログイン情報のログ出力
                    self.logger.info(
                        f"MT5サーバーへのログインに成功しました: "
                        f"アカウント名={account_info.name}, "
                        f"サーバー={account_info.server}, "
                        f"残高={account_info.balance}, "
                        f"証拠金レベル={account_info.margin_level}%"
                    )
                    
                    # ターミナル情報も確認
                    try:
                        terminal_info = mt5.terminal_info()
                        self.logger.info(
                            f"ターミナル情報: "
                            f"接続状態={terminal_info.connected}, "
                            f"取引許可={terminal_info.trade_allowed}, "
                            f"メール有効={terminal_info.email_enabled}"
                        )
                        
                        # 追加のシンボル情報確認
                        try:
                            symbols_total = mt5.symbols_total()
                            self.logger.info(f"利用可能なシンボル数: {symbols_total}")
                            
                            if symbols_total > 0 and symbols_total < 100:  # シンボル数が適切な範囲の場合
                                symbols = mt5.symbols_get()[:5]  # 最初の5つだけ取得
                                symbol_names = [symbol.name for symbol in symbols]
                                self.logger.info(f"取得可能なシンボル例: {', '.join(symbol_names)}")
                        except Exception as e:
                            self.logger.warning(f"シンボル情報取得中にエラーが発生しました: {e}")
                        
                    except Exception as e:
                        self.logger.warning(f"ターミナル情報の取得中にエラーが発生しました: {e}")
                except Exception as e:
                    self.logger.warning(f"アカウント情報の取得中にエラーが発生しました: {e}")
                
                return True, ""
            else:
                self.logger.error(f"MT5の初期化に失敗しました（{max_retries}回の試行後）: {error_message}")
                return False, error_message
                
        except Exception as e:
            error_msg = f"MT5の初期化中に予期せぬエラーが発生しました: {str(e)}\n{traceback.format_exc()}"
            self.logger.error(error_msg)
            
            # 例外が発生した場合はMT5を終了して資源を解放
            try:
                mt5.shutdown()
            except:
                pass
            
            return False, error_msg
    
    def create_session(self, login: int, password: str, server: str) -> str:
        """Create a new MT5 session with the given parameters"""
        # Generate a unique session ID
        session_id = str(uuid.uuid4().hex)
        self.session_id = session_id  # インスタンス変数として保存
        self.logger.info(f"新しいセッションを作成しています。セッションID: {session_id}")
        
        # Prepare session directory
        session_dir = os.path.join(self.base_path, session_id)
        os.makedirs(session_dir, exist_ok=True)
        self.logger.info(f"セッションディレクトリを作成しました: {session_dir}")
        
        try:
            # Prepare MT5 directory
            mt5_data_dir = os.path.join(session_dir, 'MQL5')
            os.makedirs(mt5_data_dir, exist_ok=True)
            
            # Create necessary subdirectories
            for subdir in ['Logs', 'Files', 'Experts', 'Include', 'Libraries', 'Images']:
                os.makedirs(os.path.join(mt5_data_dir, subdir), exist_ok=True)
            
            # Copy necessary files if we have a template directory
            if os.path.exists(self.template_dir):
                self.logger.info(f"テンプレートディレクトリから必要なファイルをコピーしています: {self.template_dir}")
                self._copy_template_files(self.template_dir, mt5_data_dir)
            
            # Create configuration file
            self._create_mt5_config(session_dir, login, password, server)
            
            # Get the path to the MT5 executable
            mt5_exec_path = self._get_mt5_exec_path(session_id)
            if not mt5_exec_path or not os.path.exists(mt5_exec_path):
                error_msg = f"MT5実行ファイルが見つかりません: {mt5_exec_path}"
                self.logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "session_id": session_id,
                    "session_dir": session_dir
                }
            
            # Store the path for later use
            self.mt5_exe_path = mt5_exec_path
            
            # Start the MT5 process
            try:
                self._run_mt5_process(session_dir, self._next_port)
            except Exception as e:
                error_msg = f"MT5プロセスの起動に失敗しました: {str(e)}"
                self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
                return {
                    "success": False,
                    "error": error_msg,
                    "session_id": session_id,
                    "session_dir": session_dir,
                    "mt5_path": mt5_exec_path
                }
            
            # Connect to MT5
            init_success, error_message = self._initialize_mt5(server, login, password)
            
            if not init_success:
                # If there's an error, terminate the process and clean up
                self.logger.error(f"MT5の初期化に失敗しました: {error_message}")
                
                # Create more detailed error information
                error_info = error_message
                
                # Terminate the process
                try:
                    self._terminate_mt5_process(session_id)
                except Exception as term_error:
                    self.logger.error(f"MT5プロセスの終了中にエラーが発生しました: {term_error}")
                
                # Keep session directory for diagnostics
                self.logger.info(f"診断のためにセッションディレクトリを保持しています: {session_dir}")
                
                return {
                    "success": False,
                    "error": error_info,
                    "session_id": session_id,
                    "session_dir": session_dir,
                    "mt5_path": mt5_exec_path
                }
            
            # If we got here, we have a successful connection
            self.logger.info(f"MT5セッションが正常に初期化されました。セッションID: {session_id}")
            
            # Store session information
            self._sessions[session_id] = Session(
                id=session_id,
                login=login,
                server=server,
                proc=None,
                port=None,
                mt5_path=mt5_exec_path,
                created_at=datetime.now(),
                last_accessed=datetime.now()
            )
            
            return {
                "success": True,
                "session_id": session_id,
                "session_dir": session_dir,
                "mt5_path": mt5_exec_path
            }
            
        except Exception as e:
            error_msg = f"セッション作成中に予期せぬエラーが発生しました: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            
            # Attempt to terminate the process if it exists
            try:
                if session_id in self._sessions:
                    self._terminate_mt5_process(session_id)
            except:
                pass
            
            return {
                "success": False,
                "error": error_msg,
                "session_id": session_id,
                "session_dir": session_dir
            }
    
    def get_session(self, sid: str) -> Session:
        """
        Get session information from session ID
        
        Args:
            sid: Session ID
            
        Returns:
            Session information
        """
        if sid not in self._sessions:
            raise KeyError(f"Session {sid} not found")
        
        # Update last access time
        session = self._sessions[sid]
        updated_session = session._replace(last_accessed=datetime.now())
        self._sessions[sid] = updated_session
        
        return updated_session
    
    def close_session(self, sid: str) -> bool:
        """
        End session and release resources
        
        Args:
            sid: Session ID
            
        Returns:
            True if successful
        """
        if sid not in self._sessions:
            return False
        
        session = self._sessions.pop(sid)
        logger.info(f"Ending session: {sid}")
        
        # MT5接続をシャットダウン - エラー処理強化
        try:
            mt5.shutdown()
            logger.info("MT5 shutdown complete")
        except Exception as e:
            logger.error(f"MT5 shutdown error: {e}")
        
        # プロセス終了処理を強化
        if session.proc:
            try:
                if session.proc.poll() is None:  # まだ実行中の場合のみ
                    logger.info(f"Terminating process: PID={session.proc.pid}")
                    session.proc.terminate()
                    try:
                        session.proc.wait(timeout=5)
                        logger.info("Process terminated normally")
                    except subprocess.TimeoutExpired:
                        logger.warning("Forcing process termination")
                        session.proc.kill()
            except Exception as e:
                logger.error(f"Process termination error: {e}")
        
        # セッションディレクトリの削除
        try:
            session_dir = os.path.join(self.base_path, sid)
            if os.path.exists(session_dir):
                logger.info(f"Deleting session directory: {session_dir}")
                shutil.rmtree(session_dir)
        except Exception as e:
            logger.error(f"Directory deletion error: {e}")
        
        return True
    
    def get_all_sessions(self) -> Dict[str, Dict]:
        """Get information for all sessions"""
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
        Clean up sessions that haven't been accessed for a while
        
        Args:
            max_age_seconds: Maximum session valid period (seconds)
            
        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now()
        sessions_to_close = [
            sid for sid, session in self._sessions.items()
            if (now - session.last_accessed).total_seconds() > max_age_seconds
        ]
        
        logger.info(f"Cleaning up {len(sessions_to_close)} expired sessions")
        
        for sid in sessions_to_close:
            self.close_session(sid)
        
        return len(sessions_to_close)
    
    def close_all_sessions(self) -> int:
        """
        End all sessions
        
        Returns:
            Number of sessions ended
        """
        session_ids = list(self._sessions.keys())
        logger.info(f"Ending all {len(session_ids)} sessions")
        
        for sid in session_ids:
            self.close_session(sid)
        
        return len(session_ids)

    def _terminate_mt5_process(self, session_id: str):
        """MT5プロセスを終了する"""
        if session_id not in self._sessions:
            self.logger.warning(f"セッション {session_id} のプロセスが見つかりません")
            return False
        
        session = self._sessions[session_id]
        if session.proc.poll() is None:  # プロセスがまだ実行中
            self.logger.info(f"MT5プロセス（セッションID: {session_id}）を終了します")
            try:
                # まずは通常終了を試みる
                session.proc.terminate()
                try:
                    session.proc.wait(timeout=5)
                    self.logger.info(f"MT5プロセスが正常に終了しました（セッションID: {session_id}）")
                    self._sessions.pop(session_id)
                    return True
                except subprocess.TimeoutExpired:
                    # 5秒待っても終了しない場合は強制終了
                    self.logger.warning(f"MT5プロセスが応答しないため強制終了します（セッションID: {session_id}）")
                    session.proc.kill()
                    session.proc.wait(timeout=5)
                    self.logger.info(f"MT5プロセスを強制終了しました（セッションID: {session_id}）")
                    self._sessions.pop(session_id)
                    return True
            except Exception as e:
                self.logger.error(f"MT5プロセス終了中にエラーが発生しました: {str(e)}")
                return False
        else:
            # プロセスはすでに終了している
            self.logger.info(f"MT5プロセスはすでに終了しています（セッションID: {session_id}）")
            self._sessions.pop(session_id)
            return True

    def destroy_session(self, session_id: str) -> bool:
        """指定されたセッションIDのMT5セッションを終了します
        
        Args:
            session_id: 終了するセッションのID
            
        Returns:
            bool: セッションが正常に終了したかどうか
        """
        self.logger.info(f"セッション {session_id} を終了します")
        
        if session_id not in self._sessions:
            self.logger.warning(f"セッション {session_id} が見つかりません")
            return False
        
        # MT5プロセスを終了する
        terminated = self._terminate_mt5_process(session_id)
        
        # セッションディレクトリの削除（オプション）
        try:
            session_dir = os.path.join(self.base_path, session_id)
            if os.path.exists(session_dir) and self.config.clean_sessions:
                shutil.rmtree(session_dir)
                self.logger.info(f"セッションディレクトリを削除しました: {session_dir}")
        except Exception as e:
            self.logger.error(f"セッションディレクトリの削除中にエラーが発生しました: {str(e)}")
            # ディレクトリの削除に失敗してもセッション終了は成功とみなす
        
        return terminated

    # 足りないメソッドの追加
    def _copy_template_files(self, template_dir, target_dir):
        """テンプレートディレクトリからファイルをコピーする"""
        try:
            self.logger.info(f"テンプレートファイルをコピーします: {template_dir} -> {target_dir}")
            # MQL5ディレクトリをコピー
            mql5_src = os.path.join(template_dir, "MQL5")
            mql5_dst = os.path.join(os.path.dirname(target_dir))
            
            if os.path.exists(mql5_src):
                self.logger.info(f"MQL5ディレクトリをコピーします: {mql5_src} -> {mql5_dst}")
                if os.path.exists(mql5_dst):
                    self.logger.info(f"既存のMQL5ディレクトリを削除します: {mql5_dst}")
                    shutil.rmtree(mql5_dst)
                shutil.copytree(mql5_src, mql5_dst)
            
            # その他の必要なファイルもコピー
            for file_name in ["terminal64.exe", "portable.ini", "portable_mode"]:
                src_path = os.path.join(template_dir, file_name)
                if os.path.exists(src_path):
                    dst_path = os.path.join(os.path.dirname(target_dir), file_name)
                    self.logger.info(f"ファイルをコピーします: {src_path} -> {dst_path}")
                    shutil.copy2(src_path, dst_path)
            
            # テンプレートディレクトリのConfig/accounts.datをコピー
            template_config_dir = os.path.join(template_dir, "Config")
            template_accounts_dat = os.path.join(template_config_dir, "accounts.dat")
            session_base_dir = os.path.dirname(target_dir)
            
            if os.path.exists(template_accounts_dat):
                dst_accounts_dat = os.path.join(session_base_dir, "accounts.dat")
                self.logger.info(f"テンプレートからaccounts.datをコピーします: {template_accounts_dat} -> {dst_accounts_dat}")
                shutil.copy2(template_accounts_dat, dst_accounts_dat)
                self.logger.info("テンプレートのアカウントデータをコピーしました")
            else:
                self.logger.info(f"テンプレートにaccounts.datが見つかりません: {template_accounts_dat}")
            
            # MT5のインストールディレクトリからログイン情報をコピー
            config_files_to_copy = [
                "connection_settings.ini",  # サーバー接続設定
                "accounts_settings.ini",    # アカウント設定
                "last_profile.ini",         # 最後に使用したプロファイル
                "startup.ini",              # 起動時設定
                "login.ini",                # ログイン情報
                "mt5.ini"                   # MT5全般設定
            ]
            
            # インストールディレクトリのConfigフォルダパス
            src_config_dir = os.path.join(self.mt5_install_dir, "Config")
            # ターゲットディレクトリのConfigフォルダパス
            target_config_dir = os.path.join(os.path.dirname(target_dir), "Config")
            
            # Configディレクトリがない場合は作成
            os.makedirs(target_config_dir, exist_ok=True)
            
            # ログイン関連ファイルをコピー
            for file_name in config_files_to_copy:
                src_path = os.path.join(src_config_dir, file_name)
                if os.path.exists(src_path):
                    dst_path = os.path.join(target_config_dir, file_name)
                    self.logger.info(f"ログイン情報ファイルをコピーします: {src_path} -> {dst_path}")
                    shutil.copy2(src_path, dst_path)
                else:
                    self.logger.info(f"ログイン情報ファイルが見つかりません: {src_path}")
            
            # MT5のルートディレクトリからアカウントデータファイルをコピー
            account_files_to_copy = [
                "accounts.dat",       # アカウントデータファイル
                "bases",             # データベースディレクトリ
                "logs",              # ログディレクトリ
                "cache",             # キャッシュディレクトリ
                "tester",            # テスターディレクトリ
                "profiles.dat",      # プロファイルデータ
                "symbols.dat",       # シンボルデータ
                "symbols.sel",       # 選択したシンボル
                "experts.dat",       # EAデータ
                "watchlist.dat",     # ウォッチリスト
                "metatester.ini",    # テスター設定
                "metaeditor.ini"     # エディタ設定
            ]
            
            # データファイルをコピー
            # テンプレートからコピー済みのaccounts.datの有無を確認
            has_accounts_dat = os.path.exists(os.path.join(session_base_dir, "accounts.dat"))
            
            for file_name in account_files_to_copy:
                # テンプレートからaccounts.datがコピー済みならスキップ
                if file_name == "accounts.dat" and has_accounts_dat:
                    self.logger.info(f"accounts.datはテンプレートからコピー済みのためスキップします")
                    continue
                    
                src_path = os.path.join(self.mt5_install_dir, file_name)
                if os.path.exists(src_path):
                    dst_path = os.path.join(session_base_dir, file_name)
                    
                    if os.path.isdir(src_path):
                        # ディレクトリの場合
                        if os.path.exists(dst_path):
                            self.logger.info(f"既存のディレクトリを削除します: {dst_path}")
                            shutil.rmtree(dst_path)
                        self.logger.info(f"データディレクトリをコピーします: {src_path} -> {dst_path}")
                        shutil.copytree(src_path, dst_path)
                    else:
                        # ファイルの場合
                        self.logger.info(f"データファイルをコピーします: {src_path} -> {dst_path}")
                        shutil.copy2(src_path, dst_path)
                else:
                    self.logger.info(f"データファイルが見つかりません (問題ありません): {src_path}")
                    
        except Exception as e:
            self.logger.error(f"テンプレートファイルのコピー中にエラーが発生しました: {e}")
            self.logger.exception("詳細なエラー情報:")
    
    def _create_mt5_config(self, session_dir, login, password, server):
        """MT5の設定ファイルを作成する"""
        try:
            self.logger.info(f"MT5設定ファイルを作成します: {session_dir}")
            
            # Configディレクトリを作成
            config_dir = os.path.join(session_dir, "Config")
            os.makedirs(config_dir, exist_ok=True)
            
            # ログイン情報ファイルがあるか確認
            connection_file = os.path.join(config_dir, "connection_settings.ini")
            accounts_file = os.path.join(config_dir, "accounts_settings.ini")
            login_file = os.path.join(config_dir, "login.ini")
            
            # ログイン情報ファイルが揃っているかチェック
            has_login_files = (
                os.path.exists(connection_file) and 
                os.path.exists(accounts_file) and
                os.path.exists(login_file)
            )
            
            if has_login_files:
                self.logger.info(f"既存のログイン情報ファイルが見つかりました。terminal.iniファイルのみ更新します。")
                
                # terminal.iniファイルの作成
                terminal_ini_path = os.path.join(config_dir, "terminal.ini")
                terminal_ini_content = """[Common]
Login=0
ProxyEnable=0
CertInstall=0
NewsEnable=0
AutoUpdate=0
FirstStart=0
Community=0
EnableAPI=1
WebRequests=1
SocketsPort=0
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
SocketsPort=0
"""
                with open(terminal_ini_path, "w") as f:
                    f.write(terminal_ini_content)
                self.logger.info(f"terminal.iniファイルを作成しました: {terminal_ini_path}")
            else:
                # コピーされたログイン情報ファイルがない場合は、新規に作成
                self.logger.info(f"ログイン情報ファイルが見つからないため、新しく作成します。")
                
                # terminal.iniファイルを作成
                terminal_ini_path = os.path.join(config_dir, "terminal.ini")
                terminal_ini_content = f"""[Common]
Login={login}
Server={server}
ProxyEnable=0
CertInstall=0
NewsEnable=0
AutoUpdate=0
FirstStart=0
Community=0
EnableAPI=1
WebRequests=1
SocketsPort=0
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
SocketsPort=0
"""
                with open(terminal_ini_path, "w") as f:
                    f.write(terminal_ini_content)
                self.logger.info(f"terminal.iniファイルを作成しました: {terminal_ini_path}")
                
                # ログイン情報ファイルも作成
                with open(connection_file, "w") as f:
                    f.write(f"[connection]\nserver={server}\n")
                
                with open(login_file, "w") as f:
                    f.write(f"[login]\nlogin={login}\n")
            
            # portable_modeファイルを作成
            with open(os.path.join(session_dir, "portable_mode"), "w") as f:
                f.write("portable")
            
            # access.iniファイルを作成
            access_ini_path = os.path.join(config_dir, "access.ini")
            access_ini_content = """[Environment]
MQL5Login=0
ProxyEnable=0
ProxyServer=
ProxyLogin=
WebRequests=1
EnableAPI=1
SocketsPort=0
"""
            with open(access_ini_path, "w") as f:
                f.write(access_ini_content)
            
            # startup.iniファイルを作成
            startup_ini_path = os.path.join(config_dir, "startup.ini")
            startup_ini_content = """[Startup]
StartExpert=1
StartScript=1
ExpertsEnable=1
ScriptsEnable=1
ExpertsSynchronize=1
ExpertsRestart=1
ExpertsDllImport=1
ExpertsAllowWebRequests=1
WebAPIEnabled=1
"""
            with open(startup_ini_path, "w") as f:
                f.write(startup_ini_content)
            
        except Exception as e:
            self.logger.error(f"MT5設定ファイルの作成中にエラーが発生しました: {e}")
            self.logger.exception("詳細なエラー情報:")
    
    def _get_mt5_exec_path(self, session_id):
        """セッション固有のMT5実行ファイルのパスを取得する"""
        try:
            # セッションディレクトリ内のMT5実行ファイルパス
            session_dir = os.path.join(self.base_path, session_id)
            mt5_exec_path = os.path.join(session_dir, "terminal64.exe")
            
            if not os.path.exists(mt5_exec_path):
                # ファイルが存在しない場合は、元のMT5実行ファイルをコピー
                self.logger.info(f"MT5実行ファイルをコピーします: {self.portable_mt5_path} -> {mt5_exec_path}")
                shutil.copy2(self.portable_mt5_path, mt5_exec_path)
            
            return mt5_exec_path
            
        except Exception as e:
            self.logger.error(f"MT5実行ファイルパスの取得中にエラーが発生しました: {e}")
            self.logger.exception("詳細なエラー情報:")
            return None

# Global SessionManager instance
_session_manager: Optional[SessionManager] = None

def init_session_manager(base_path: str, portable_mt5_path: str):
    """Initialize SessionManager"""
    global _session_manager
    _session_manager = SessionManager(base_path, portable_mt5_path)

def get_session_manager() -> SessionManager:
    """Get SessionManager instance"""
    global _session_manager
    
    # FastAPIの状態からセッションマネージャーを取得を試みる
    try:
        from fastapi import FastAPI
        import inspect
        
        # 実行中のスタックフレームを取得
        stack = inspect.stack()
        
        # スタックを遡ってFastAPIインスタンスを探す
        for frame in stack:
            if 'app' in frame.frame.f_locals:
                app_instance = frame.frame.f_locals['app']
                if hasattr(app_instance, 'state') and hasattr(app_instance.state, 'session_manager'):
                    logger.debug("FastAPIアプリの状態からSessionManagerを取得しました")
                    return app_instance.state.session_manager
    except Exception as e:
        logger.warning(f"FastAPIアプリの状態からSessionManagerを取得できませんでした: {e}")
    
    # グローバルインスタンスを確認
    if _session_manager is None:
        # グローバルインスタンスがなければエラー
        raise RuntimeError("SessionManager is not initialized")
    
    return _session_manager 