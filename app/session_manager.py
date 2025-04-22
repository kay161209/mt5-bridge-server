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
    
    # ハンドラがない場合のみ追加
    if not lgr.handlers:
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
                # 通常はstdout.bufferを使用するが、閉じられている場合はシンプルなハンドラを使用
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                lgr.addHandler(console_handler)
            except (ValueError, AttributeError):
                pass
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

def check_gui_status(process_pid):
    """MT5プロセスがGUIウィンドウを表示しているかを確認する"""
    result = {
        'has_window': False,
        'window_info': None,
        'error': None,
        'os': platform.system()
    }
    
    try:
        if platform.system() == 'Windows':
            # Windowsの場合
            import win32gui
            import win32process
            
            def callback(hwnd, result):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == process_pid and win32gui.IsWindowVisible(hwnd):
                        text = win32gui.GetWindowText(hwnd)
                        if text and ('MetaTrader' in text or 'MT5' in text):
                            rect = win32gui.GetWindowRect(hwnd)
                            result['windows'].append({
                                'handle': hwnd,
                                'title': text,
                                'rect': rect,
                                'visible': win32gui.IsWindowVisible(hwnd),
                                'enabled': win32gui.IsWindowEnabled(hwnd)
                            })
                            result['has_window'] = True
                except Exception as e:
                    result['errors'].append(str(e))
                return True
            
            windows_result = {'windows': [], 'has_window': False, 'errors': []}
            win32gui.EnumWindows(callback, windows_result)
            result['has_window'] = windows_result['has_window']
            result['window_info'] = windows_result['windows']
            result['error'] = windows_result['errors'] if windows_result['errors'] else None
            
        elif platform.system() == 'Darwin':
            # macOSの場合
            try:
                # AppleScriptを使用してウィンドウを確認
                script = '''
                tell application "System Events"
                    set windowList to {}
                    set allProcesses to processes whose unix id is %d
                    repeat with proc in allProcesses
                        set procName to name of proc
                        set procWindows to windows of proc
                        repeat with win in procWindows
                            set winName to name of win
                            set winPos to position of win
                            set winSize to size of win
                            set end of windowList to {name:procName, window:winName, position:winPos, size:winSize}
                        end repeat
                    end repeat
                    return windowList
                end tell
                ''' % process_pid
                
                proc = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, text=True, timeout=3
                )
                
                if proc.stdout.strip():
                    result['has_window'] = True
                    result['window_info'] = proc.stdout.strip()
                
                # Wineのウィンドウもチェック
                wine_script = '''
                tell application "System Events"
                    set wineWindows to {}
                    set wineProcs to processes whose name contains "wine"
                    repeat with proc in wineProcs
                        set procName to name of proc
                        set procWindows to windows of proc
                        repeat with win in procWindows
                            set winName to name of win
                            if winName contains "MetaTrader" or winName contains "MT5" then
                                set winPos to position of win
                                set winSize to size of win
                                set end of wineWindows to {name:procName, window:winName, position:winPos, size:winSize}
                            end if
                        end repeat
                    end repeat
                    return wineWindows
                end tell
                '''
                
                wine_proc = subprocess.run(
                    ["osascript", "-e", wine_script],
                    capture_output=True, text=True, timeout=3
                )
                
                if wine_proc.stdout.strip():
                    result['has_wine_window'] = True
                    result['wine_window_info'] = wine_proc.stdout.strip()
                
            except Exception as e:
                result['error'] = str(e)
        
        # プロセスの詳細情報も収集
        try:
            process = psutil.Process(process_pid)
            result['process_info'] = {
                'name': process.name(),
                'status': process.status(),
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_info': {
                    'rss': process.memory_info().rss / (1024 * 1024),  # MB
                    'vms': process.memory_info().vms / (1024 * 1024)   # MB
                },
                'create_time': datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S'),
                'cmdline': process.cmdline(),
                'cwd': process.cwd(),
                'num_threads': process.num_threads(),
                'children': [{'pid': c.pid, 'name': c.name()} for c in process.children()]
            }
        except Exception as e:
            result['process_info_error'] = str(e)
        
    except Exception as e:
        result['error'] = str(e)
    
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
Width=1
Height=1
Left=-10000
Top=-10000
StartupMode=2
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
    
    def _run_mt5_process(self, session_dir: Path, port: int) -> bool:
        """MT5プロセスを起動する"""
        logger.info(f"MT5プロセスを起動しています（ディレクトリ: {session_dir}, ポート: {port}）")
        
        try:
            # 実行コマンドを構築
            executable = os.path.join(session_dir, "terminal64.exe")
            if not os.path.exists(executable):
                logger.error(f"MT5実行ファイルが見つかりません: {executable}")
                return False
            
            command = [executable, "/portable", f"/port:{port}"]
            logger.debug(f"実行コマンド: {' '.join(command)}")
            
            # システム情報をログに記録
            sys_info = get_system_info()
            logger.info(f"MT5起動前のシステム情報: {json.dumps(sys_info, ensure_ascii=False, indent=2)}")
            
            # プロセスを起動
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(session_dir),
                encoding='utf-8',
                errors='replace'
            )
            
            # プロセスIDをログに記録
            pid = process.pid
            logger.info(f"MT5プロセスが起動しました。PID: {pid}")
            
            # プロセスの状態確認を行う
            time.sleep(2)  # プロセスが起動する時間を少し待つ
            
            if process.poll() is not None:
                # プロセスが既に終了している場合
                return_code = process.poll()
                stdout, stderr = process.communicate(timeout=1)
                logger.error(f"MT5プロセスが即座に終了しました。リターンコード: {return_code}")
                logger.error(f"標準出力: {stdout}")
                logger.error(f"標準エラー: {stderr}")
                return False
            
            # プロセス情報のモニタリング
            try:
                p = psutil.Process(pid)
                logger.info(f"プロセス情報: 名前={p.name()}, 状態={p.status()}")
                logger.info(f"メモリ使用量: {p.memory_info().rss / (1024 * 1024):.2f} MB")
                logger.info(f"CPU使用率: {p.cpu_percent(interval=0.1):.2f}%")
                
                # 子プロセスの確認
                children = p.children(recursive=True)
                if children:
                    logger.info(f"子プロセス数: {len(children)}")
                    for child in children:
                        logger.info(f"子プロセス: PID={child.pid}, 名前={child.name()}")
                else:
                    logger.info("子プロセスはありません")
                
                # GUIウィンドウの状態を確認
                gui_status = check_gui_status(pid)
                logger.info(f"GUIウィンドウの状態: {json.dumps(gui_status, ensure_ascii=False, indent=2)}")
                
                # MT5のGUIが表示されない場合のログ
                if not gui_status.get('has_window', False):
                    logger.warning("MT5のGUIウィンドウが検出されませんでした")
                    
                    # 追加のデバッグ情報を収集
                    # 環境変数をログに記録
                    wine_env_vars = {k: v for k, v in os.environ.items() if 'wine' in k.lower() or 'display' in k.lower()}
                    logger.debug(f"Wine関連の環境変数: {wine_env_vars}")
                    
                    # プロセスの標準出力/エラー出力を非ブロッキングで読み取り
                    stdout_data, stderr_data = "", ""
                    try:
                        # 標準出力を確認
                        if process.stdout:
                            stdout_ready, _, _ = select.select([process.stdout], [], [], 0.5)
                            if stdout_ready:
                                stdout_data = process.stdout.read(4096)
                                logger.debug(f"MT5プロセスの標準出力: {stdout_data}")
                        
                        # 標準エラーを確認
                        if process.stderr:
                            stderr_ready, _, _ = select.select([process.stderr], [], [], 0.5)
                            if stderr_ready:
                                stderr_data = process.stderr.read(4096)
                                logger.debug(f"MT5プロセスの標準エラー: {stderr_data}")
                    except Exception as e:
                        logger.error(f"プロセス出力の読み取り中にエラーが発生しました: {e}")
                
                # プロセスクリーンアップ関数を登録
                def cleanup_process():
                    try:
                        if p.is_running():
                            logger.info(f"MT5プロセス(PID: {pid})を終了します")
                            p.terminate()
                            try:
                                p.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                logger.warning(f"MT5プロセス(PID: {pid})が5秒以内に終了しませんでした。強制終了します")
                                p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                        logger.warning(f"プロセスクリーンアップ中にエラーが発生しました: {e}")
                
                # アプリケーション終了時にプロセスをクリーンアップ
                atexit.register(cleanup_process)
                
            except psutil.NoSuchProcess:
                logger.error(f"プロセス(PID: {pid})が見つかりません")
            except Exception as e:
                logger.error(f"プロセス情報の取得中にエラーが発生しました: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"MT5プロセスの起動中にエラーが発生しました: {str(e)}")
            traceback.print_exc()
            return False
    
    def _initialize_mt5(self, server, login, password, timeout=60) -> Tuple[bool, str]:
        """
        MT5を初期化して接続します。二段階で処理を行います:
        1. MT5の初期化
        2. MT5へのログイン
        
        Args:
            server: MT5サーバー名
            login: MT5ログインID
            password: MT5パスワード
            timeout: 初期化のタイムアウト時間（秒）
        
        Returns:
            (成功したかどうか, エラーメッセージ)
        """
        try:
            # まず初期化を実行
            self.logger.info(f"MT5ライブラリの初期化を開始します（セッション: {self.session_id}）")
            initialize_result = mt5.initialize(
                path=self.mt5_exe_path,
                login=login,
                password=password,
                server=server,
                timeout=timeout * 1000
            )
            
            # 初期化に失敗した場合
            if not initialize_result:
                error_code = mt5.last_error()
                error_msg = f"MT5の初期化に失敗しました。"
                detailed_error = get_detailed_error(error_code, error_msg)
                self.logger.error(detailed_error)
                return False, detailed_error
            
            self.logger.info(f"MT5ライブラリの初期化に成功しました（セッション: {self.session_id}）")
            
            # ログイン処理
            self.logger.info(f"MT5サーバーへのログインを開始します（セッション: {self.session_id}）")
            account_info = mt5.account_info()
            if account_info is None:
                error_code = mt5.last_error()
                error_msg = f"MT5サーバーへのログインに失敗しました。"
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
            
            return True, ""
            
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

# Global SessionManager instance
_session_manager: Optional[SessionManager] = None

def init_session_manager(base_path: str, portable_mt5_path: str):
    """Initialize SessionManager"""
    global _session_manager
    _session_manager = SessionManager(base_path, portable_mt5_path)

def get_session_manager() -> SessionManager:
    """Get SessionManager instance"""
    if _session_manager is None:
        raise RuntimeError("SessionManager is not initialized")
    return _session_manager 