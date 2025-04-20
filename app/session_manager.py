import uuid
import subprocess
import time
import os
import shutil
from typing import NamedTuple, Dict, Optional
import MetaTrader5 as mt5
from datetime import datetime

class Session(NamedTuple):
    id: str
    login: int
    server: str
    proc: subprocess.Popen
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
        
        # 基本ディレクトリがなければ作成
        os.makedirs(base_path, exist_ok=True)
    
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
        
        # ポータブル版MT5をセッションディレクトリにコピー
        mt5_exec_path = os.path.join(session_dir, "terminal64.exe")
        shutil.copy2(self.portable_mt5_path, mt5_exec_path)
        
        # MT5プロセスを起動
        proc = subprocess.Popen([mt5_exec_path], cwd=session_dir)
        
        # プロセスが起動するまで少し待機
        time.sleep(5)
        
        # MT5に接続
        if not mt5.initialize(path=mt5_exec_path, login=login, password=password, server=server):
            # エラーがあればプロセスを終了し、ディレクトリを削除
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            
            try:
                shutil.rmtree(session_dir)
            except:
                pass
                
            error = mt5.last_error()
            raise RuntimeError(f"MT5 初期化エラー: {error[0]} - {error[1]}")
        
        # セッション情報を保存
        now = datetime.now()
        session = Session(
            id=sid,
            login=login,
            server=server,
            proc=proc,
            created_at=now,
            last_accessed=now
        )
        self._sessions[sid] = session
        
        return sid
    
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
        
        # MT5接続をシャットダウン
        mt5.shutdown()
        
        # プロセスを終了
        try:
            session.proc.terminate()
            try:
                session.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                session.proc.kill()
        except:
            pass
        
        # セッションディレクトリを削除
        try:
            session_dir = os.path.join(self.base_path, sid)
            shutil.rmtree(session_dir)
        except:
            pass
        
        return True
    
    def get_all_sessions(self) -> Dict[str, Dict]:
        """すべてのセッション情報を取得"""
        return {
            sid: {
                "id": s.id,
                "login": s.login,
                "server": s.server,
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