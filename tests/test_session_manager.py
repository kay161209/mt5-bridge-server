#!/usr/bin/env python
"""
セッションマネージャーのテストモジュール
"""
import os
import sys
import time
import pytest
import logging
from pathlib import Path
from datetime import datetime, timedelta

from app.session_manager import SessionManager

# テスト用のロギング設定
logger = logging.getLogger(__name__)

def test_session_manager_initialization(session_manager):
    """セッションマネージャーの初期化をテストする"""
    assert session_manager is not None, "セッションマネージャーが初期化されていません"
    assert isinstance(session_manager, SessionManager), "セッションマネージャーのインスタンスタイプが正しくありません"

def test_create_new_session(session_manager, test_config):
    """新しいセッションの作成をテストする"""
    session_id = session_manager.create_session(
        login=test_config["mt5_login"],
        password=test_config["mt5_password"],
        server=test_config["mt5_server"]
    )
    
    assert session_id is not None, "セッションIDが生成されませんでした"
    assert session_manager.get_session(session_id) is not None, "作成したセッションが取得できません"
    
    return session_id

def test_get_session(session_manager, test_config):
    """セッションの取得をテストする"""
    # セッションを作成
    session_id = test_create_new_session(session_manager, test_config)
    
    # セッションを取得
    session = session_manager.get_session(session_id)
    assert session is not None, "セッションが見つかりません"
    assert session.login == test_config["mt5_login"], "ログインIDが一致しません"
    assert session.server == test_config["mt5_server"], "サーバーが一致しません"

def test_list_sessions(session_manager, test_config):
    """セッション一覧の取得をテストする"""
    # セッションを作成
    session_id = test_create_new_session(session_manager, test_config)
    
    # セッション一覧を取得
    sessions = session_manager.list_sessions()
    assert isinstance(sessions, dict), "セッション一覧が辞書形式ではありません"
    assert session_id in sessions, "作成したセッションが一覧に含まれていません"
    
    session = sessions[session_id]
    assert session["login"] == test_config["mt5_login"], "ログインIDが一致しません"
    assert session["server"] == test_config["mt5_server"], "サーバーが一致しません"

def test_cleanup_old_sessions(session_manager, test_config):
    """古いセッションのクリーンアップをテストする"""
    # セッションを作成
    session_id = test_create_new_session(session_manager, test_config)
    
    # セッションの最終アクセス時間を更新
    session = session_manager.get_session(session_id)
    session.last_access = datetime.now() - timedelta(hours=2)
    
    # クリーンアップを実行
    cleaned_sessions = session_manager.cleanup_old_sessions()
    assert session_id in cleaned_sessions, "古いセッションがクリーンアップされていません"
    assert session_manager.get_session(session_id) is None, "クリーンアップ後もセッションが残っています"

def test_session_command_execution(session_manager, test_config):
    """セッションでのコマンド実行をテストする"""
    # セッションを作成
    session_id = test_create_new_session(session_manager, test_config)
    
    # シンボル情報取得コマンドを実行
    result = session_manager.execute_command(
        session_id=session_id,
        command="symbols_get",
        params={}
    )
    
    assert result is not None, "コマンド実行結果がありません"
    assert isinstance(result, list), "シンボル情報がリスト形式ではありません"
    assert len(result) > 0, "シンボル情報が空です"

@pytest.mark.integration
def test_session_manager_workflow(session_manager, test_config):
    """セッションマネージャーの一連の操作をテストする"""
    # セッションマネージャーの初期化確認
    test_session_manager_initialization(session_manager)
    
    # セッション作成
    session_id = test_create_new_session(session_manager, test_config)
    
    try:
        # セッション取得
        test_get_session(session_manager, test_config)
        
        # セッション一覧
        test_list_sessions(session_manager, test_config)
        
        # コマンド実行
        test_session_command_execution(session_manager, test_config)
    
    finally:
        # セッションのクリーンアップ
        session_manager.cleanup_session(session_id) 