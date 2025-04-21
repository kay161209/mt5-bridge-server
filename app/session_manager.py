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

# Enhanced logger configuration
logging.basicConfig(
    level=logging.DEBUG,  # More detailed log level
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('mt5_session.log', encoding='utf-8')  # Also output logs to file
    ]
)
logger = logging.getLogger("session_manager")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class Session(NamedTuple):
    id: str
    login: int
    server: str
    proc: subprocess.Popen
    port: int
    mt5_path: str  # MT5 path specific to this session
    created_at: datetime
    last_accessed: datetime

# Detailed MT5 API error messages and codes
MT5_ERROR_CODES = {
    -10005: "IPC Timeout - Process communication timed out. Failed to establish connection with MT5.",
    -10004: "IPC Initialization Error - Failed to initialize inter-process communication.",
    -10003: "IPC Test Socket Creation Error - Failed to create a test socket.",
    -10002: "IPC Data Socket Creation Error - Failed to create a data communication socket.",
    -10001: "IPC Event Socket Creation Error - Failed to create an event notification socket.",
    -10000: "IPC Error - General error in inter-process communication.",
    -9999: "Startup Path Not Found - MetaTrader 5 execution path was not found.",
    -8: "Insufficient Buffer - Buffer for receiving data is insufficient.",
    -7: "Structure Too Small - Data structure size is insufficient.",
    -6: "No Data - Requested data is not available.",
    -5: "Internal Error - Internal error in MetaTrader 5 terminal.",
    -4: "Insufficient Memory - Insufficient memory to execute the function.",
    -3: "Invalid Parameter - Invalid parameter was passed to the function.",
    -2: "Communication with terminal not established.",
    -1: "Unknown Error - Cause unknown.",
    0: "No Error - Operation completed successfully.",
}

def get_detailed_error(error_code: int, error_message: str) -> str:
    """Get detailed explanation for MT5 error code"""
    detailed_explanation = MT5_ERROR_CODES.get(error_code, "Unknown error code")
    return f"Error code: {error_code}, Message: {error_message}\nDetailed explanation: {detailed_explanation}"

def get_system_info() -> Dict[str, Any]:
    """Collect system information"""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "architecture": platform.architecture(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "memory": None,  # Memory info can be obtained with psutil if needed
    }

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
    
    def _run_mt5_process(self, mt5_exec_path: str, session_dir: str, port: int) -> Tuple[subprocess.Popen, Any]:
        """Start MT5 process and record output"""
        # Start MT5 process (with port specification)
        cmd = [mt5_exec_path, f"/port:{port}"]
        logger.info(f"Execution command: {' '.join(cmd)}")
        
        # Set up pipes to capture output
        proc = subprocess.Popen(
            cmd,
            cwd=session_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='replace'
        )
        
        logger.info(f"MT5 process started: PID={proc.pid}")
        
        # Non-blocking attempt to read output
        stdout_data = ""
        stderr_data = ""
        
        # Read output while process is starting
        try:
            # Wait a certain amount of time
            time.sleep(5)
            
            # Read standard output and error (non-blocking)
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
            logger.warning(f"Error while reading process output: {e}")
        
        # Check process status
        returncode = proc.poll()
        if returncode is not None:
            logger.error(f"MT5 process unexpectedly terminated. Return code: {returncode}")
            output = "== STDOUT ==\n" + stdout_data + "\n== STDERR ==\n" + stderr_data
            logger.error(f"MT5 process output:\n{output}")
            raise RuntimeError(f"MT5 process failed to start. Return code: {returncode}")
        
        return proc, {"stdout": stdout_data, "stderr": stderr_data}
    
    def _initialize_mt5(self, mt5_exec_path: str, login: int, password: str, server: str) -> Dict[str, Any]:
        """Initialize MT5 and return detailed results"""
        logger.info("Starting MT5 initialization...")
        logger.info(f"MT5 path: {mt5_exec_path}")
        logger.info(f"Login: {login}, Server: {server}")
        
        # Check MT5 module state before initialization
        try:
            mt5_initialized = mt5.initialize() if not mt5.initialize.__self__.terminal_info() else True
            if mt5_initialized:
                logger.info("MT5 is already initialized. Shutting down.")
                mt5.shutdown()
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Error during MT5 initial state check: {e}")
        
        # Attempt initialization
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
                timeout=60000  # Set timeout to 60 seconds
            )
            
            if not success:
                error = mt5.last_error()
                error_code = error[0]
                error_message = error[1]
                logger.error(f"MT5 initialization error: {error}")
                logger.error(f"Details: {get_detailed_error(error_code, error_message)}")
            else:
                # If successful, get connection information
                logger.info("MT5 initialization successful")
                try:
                    terminal_info = mt5.terminal_info()
                    account_info = mt5.account_info()
                    
                    logger.info(f"Terminal info: connected={terminal_info.connected}, trade_allowed={terminal_info.trade_allowed}")
                    if account_info:
                        logger.info(f"Account info: login ID={account_info.login}, server={account_info.server}")
                except Exception as e:
                    logger.warning(f"Error while retrieving MT5 information: {e}")
        except Exception as e:
            logger.exception(f"Exception occurred during MT5 initialization: {e}")
            error_message = str(e)
            error_code = -99999
            success = False
        
        elapsed_time = time.time() - start_time
        logger.info(f"MT5 initialization process time: {elapsed_time:.2f} seconds")
        
        return {
            "success": success,
            "error_code": error_code,
            "error_message": error_message,
            "elapsed_time": elapsed_time
        }
    
    def create_session(self, login: int, password: str, server: str) -> str:
        """
        Create a new MT5 session
        
        Args:
            login: MT5 login ID
            password: MT5 password
            server: MT5 server
            
        Returns:
            Session ID
        """
        # Generate session ID
        sid = uuid.uuid4().hex
        
        # Create directory for the session
        session_dir = os.path.join(self.base_path, sid)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
        os.makedirs(session_dir, exist_ok=True)
        
        # Assign a port for this session
        port = self._next_port
        self._next_port += 1
        
        logger.info(f"Creating new session: id={sid}, login={login}, server={server}, port={port}")
        logger.info(f"Session directory: {session_dir}")
        
        try:
            # Check if template directory exists
            if not os.path.exists(self.template_dir) or not os.path.isfile(os.path.join(self.template_dir, "terminal64.exe")):
                logger.warning("Template directory not found or incomplete. Recreating.")
                self._prepare_template_directory()
            
            # Copy files from template directory (fast)
            start_time = time.time()
            logger.info("Copying MT5 files from template to session directory...")
            
            for item in os.listdir(self.template_dir):
                src_path = os.path.join(self.template_dir, item)
                dst_path = os.path.join(session_dir, item)
                
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)
                elif os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path, symlinks=True)
            
            # Overwrite session-specific configuration files
            config_dir = os.path.join(session_dir, "Config")
            os.makedirs(config_dir, exist_ok=True)
            
            # Create login.ini (session-specific login information)
            login_ini_content = f"""[Login]
Server={server}
Login={login}
Password={password}
ProxyEnable=0
"""
            with open(os.path.join(config_dir, "login.ini"), "w") as f:
                f.write(login_ini_content)
            
            copy_time = time.time() - start_time
            logger.info(f"MT5 file copying completed (time taken: {copy_time:.2f} seconds)")
            
            # Session-specific MT5 executable path
            mt5_exec_path = os.path.join(session_dir, "terminal64.exe")
            
            if not os.path.exists(mt5_exec_path):
                raise FileNotFoundError(f"MT5 executable not found: {mt5_exec_path}")
            
            logger.info(f"MT5 executable exists: {mt5_exec_path}")
            
            # Start MT5 process and get output
            proc, process_output = self._run_mt5_process(mt5_exec_path, session_dir, port)
            
            # Wait for process to start up
            logger.info("Waiting for MT5 process to start... (60 seconds)")
            time.sleep(60)  # Longer wait time
            
            # Connect to MT5
            init_result = self._initialize_mt5(mt5_exec_path, login, password, server)
            
            if not init_result["success"]:
                # If there's an error, terminate the process and clean up
                error_code = init_result["error_code"]
                error_message = init_result["error_message"]
                
                # Create more detailed error information
                error_detail = {
                    "error_code": error_code,
                    "error_message": error_message,
                    "detailed_error": get_detailed_error(error_code, error_message),
                    "process_output": process_output,
                    "session_dir": session_dir,
                    "mt5_path": mt5_exec_path,
                    "elapsed_time": init_result["elapsed_time"]
                }
                
                logger.error(f"MT5 initialization error details: {json.dumps(error_detail, indent=2)}")
                
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                
                try:
                    # Save error information
                    with open(os.path.join(session_dir, "error_log.json"), "w") as f:
                        json.dump(error_detail, f, indent=2)
                    
                    # Don't delete the directory, keep it for error diagnosis
                    # shutil.rmtree(session_dir)
                    logger.info(f"Keeping session directory for error diagnosis: {session_dir}")
                except Exception as e:
                    logger.error(f"Exception occurred while saving error log: {e}")
                    
                detailed_error = get_detailed_error(error_code, error_message)
                raise RuntimeError(f"MT5 initialization error: {error_code} - {error_message}\n{detailed_error}")
            
            logger.info("MT5 initialization successful")
            
            # Save session information
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
            logger.exception(f"Exception occurred during session creation: {e}")
            
            # Log stack trace
            trace = traceback.format_exc()
            logger.error(f"Stack trace: {trace}")
            
            # Cleanup
            try:
                if 'proc' in locals() and proc:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            except:
                pass
                
            # Keep directory for error diagnosis
            # try:
            #     shutil.rmtree(session_dir)
            # except:
            #     pass
                
            raise
    
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
        
        # Shut down MT5 connection
        try:
            mt5.shutdown()
            logger.info("MT5 shutdown complete")
        except Exception as e:
            logger.error(f"MT5 shutdown error: {e}")
        
        # Terminate process
        try:
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
        
        # Delete session directory
        try:
            session_dir = os.path.join(self.base_path, sid)
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