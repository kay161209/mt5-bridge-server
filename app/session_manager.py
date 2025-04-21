import uuid
import subprocess
import time
import os
import shutil
from typing import NamedTuple, Dict, Optional
import MetaTrader5 as mt5
from datetime import datetime
import logging
import glob

# ロガー設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
        
        # 基本ディレクトリがなければ作成
        os.makedirs(base_path, exist_ok=True)
        
        # MT5ポータブル版のパスが存在するか確認
        if not os.path.exists(portable_mt5_path):
            logger.error(f"MT5ポータブル版が見つかりません: {portable_mt5_path}")
        else:
            logger.info(f"MT5ポータブル版が見つかりました: {portable_mt5_path}")
        
        # MT5のインストールディレクトリを取得
        self.mt5_install_dir = os.path.dirname(self.portable_mt5_path)
        if not os.path.exists(self.mt5_install_dir):
            logger.error(f"MT5インストールディレクトリが見つかりません: {self.mt5_install_dir}")
        else:
            logger.info(f"MT5インストールディレクトリが見つかりました: {self.mt5_install_dir}")
            # ディレクトリ内のファイル一覧を表示
            files = os.listdir(self.mt5_install_dir)
            logger.info(f"MT5インストールディレクトリのファイル一覧: {files}")
        
        logger.info(f"SessionManager initialized: base_path={base_path}, mt5_path={portable_mt5_path}")
    
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
        os.makedirs(session_dir, exist_ok=True)
        
        # このセッション用のポートを割り当て
        port = self._next_port
        self._next_port += 1
        
        logger.info(f"新規セッション作成: id={sid}, login={login}, server={server}, port={port}")
        logger.info(f"MT5インストールディレクトリ: {self.mt5_install_dir}")
        logger.info(f"セッションディレクトリ: {session_dir}")
        
        try:
            # MT5ポータブル版のファイルをセッションディレクトリにコピー
            logger.info("MT5ファイルをセッションディレクトリにコピー中...")
            
            # 必要なファイルとディレクトリだけをコピー
            required_items = [
                "terminal64.exe",
                "Config",
                "MQL5",
                "Sounds",
                "symbols.dat",
                "startup.dat",
                "MetaQuotes.dat",
                "history",
                "logs",
                "*.dll"
            ]
            
            # 必要なファイル・ディレクトリをコピー
            for pattern in required_items:
                items = glob.glob(os.path.join(self.mt5_install_dir, pattern))
                for item_path in items:
                    item_name = os.path.basename(item_path)
                    target_path = os.path.join(session_dir, item_name)
                    
                    if os.path.isfile(item_path):
                        logger.info(f"ファイルコピー: {item_path} -> {target_path}")
                        shutil.copy2(item_path, target_path)
                    elif os.path.isdir(item_path):
                        logger.info(f"ディレクトリコピー: {item_path} -> {target_path}")
                        if os.path.exists(target_path):
                            shutil.rmtree(target_path)
                        shutil.copytree(item_path, target_path)
            
            # セッション固有のMT5実行ファイルパス
            mt5_exec_path = os.path.join(session_dir, "terminal64.exe")
            
            if not os.path.exists(mt5_exec_path):
                raise FileNotFoundError(f"MT5実行ファイルが見つかりません: {mt5_exec_path}")
            
            logger.info(f"MT5実行ファイルが存在します: {mt5_exec_path}")
            
            # MT5プロセスを起動 (ポータブルモードとポート指定)
            cmd = [mt5_exec_path, f"/portable", f"/port:{port}"]
            logger.info(f"実行コマンド: {' '.join(cmd)}")
            
            proc = subprocess.Popen(
                cmd,
                cwd=session_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info(f"MT5プロセス起動: PID={proc.pid}")
            
            # プロセスが起動するまで待機 (20秒に延長)
            logger.info("MT5プロセス起動待機中...")
            time.sleep(20)
            
            # MT5に接続
            logger.info("MT5初期化開始...")
            if not mt5.initialize(path=mt5_exec_path, login=login, password=password, server=server):
                # エラーがあればプロセスを終了し、ディレクトリを削除
                error = mt5.last_error()
                logger.error(f"MT5初期化エラー: {error}")
                
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                
                try:
                    shutil.rmtree(session_dir)
                except Exception as e:
                    logger.error(f"セッションディレクトリ削除エラー: {e}")
                    
                raise RuntimeError(f"MT5 初期化エラー: {error[0]} - {error[1]}")
            
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
                
            try:
                shutil.rmtree(session_dir)
            except:
                pass
                
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