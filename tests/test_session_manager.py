import pytest
from app.session_manager import MT5Session
import time

def test_create_session(session_manager):
    """セッション作成のテスト"""
    session_id = session_manager.create_session()
    assert session_id is not None
    assert session_id in session_manager.sessions

def test_get_session(session_manager, test_session):
    """セッション取得のテスト"""
    session = session_manager.get_session(test_session)
    assert session is not None
    assert isinstance(session, MT5Session)
    assert session.session_id == test_session

def test_cleanup_old_sessions(session_manager):
    """古いセッションのクリーンアップテスト"""
    # セッションを作成
    session_id = session_manager.create_session()
    assert session_id in session_manager.sessions
    
    # セッションの最終アクセス時間を更新
    session = session_manager.get_session(session_id)
    session.last_activity = time.time() - 3700  # 1時間以上前
    
    # クリーンアップを実行
    cleaned = session_manager.cleanup_old_sessions(max_age_seconds=3600)
    assert cleaned == 1
    assert session_id not in session_manager.sessions

def test_session_command(session_manager, test_session):
    """セッションコマンド実行のテスト"""
    session = session_manager.get_session(test_session)
    
    # 初期化コマンドのテスト
    result = session.send_command({"type": "initialize"})
    assert result.get("success") is True

def test_invalid_session(session_manager):
    """無効なセッションのテスト"""
    invalid_session_id = "invalid_id"
    session = session_manager.get_session(invalid_session_id)
    assert session is None

def test_session_cleanup(session_manager):
    """セッションクリーンアップのテスト"""
    session_id = session_manager.create_session()
    assert session_id in session_manager.sessions
    
    session = session_manager.get_session(session_id)
    session.cleanup()
    
    # セッションが正しくクリーンアップされたことを確認
    assert not session.initialized
    assert not session.process or not session.process.is_alive() 