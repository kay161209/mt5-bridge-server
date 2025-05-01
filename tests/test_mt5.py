#!/usr/bin/env python
"""
MT5関連のテストモジュール
- MT5の直接初期化テスト
- セッション作成テスト
"""
import os
import sys
import time
import json
import pytest
import logging
from pathlib import Path
from datetime import datetime

# テスト用のロギング設定
logger = logging.getLogger(__name__)

def test_mt5_direct_initialize(mt5_instance, test_config):
    """MT5の直接初期化をテストする"""
    assert mt5_instance is not None, "MT5インスタンスが初期化されていません"
    
    # 接続情報を確認
    terminal_info = mt5_instance.terminal_info()
    assert terminal_info.connected, "MT5が接続されていません"
    assert terminal_info.trade_allowed, "取引が許可されていません"
    
    # アカウント情報を確認
    account_info = mt5_instance.account_info()
    assert account_info is not None, "アカウント情報を取得できません"
    assert account_info.login == test_config["mt5_login"], "ログインIDが一致しません"
    assert account_info.server == test_config["mt5_server"], "サーバーが一致しません"

def test_create_session(api_client, test_config):
    """セッション作成をテストする"""
    # セッション作成リクエスト
    response = api_client.post(
        "/v5/session/create",
        json={
            "login": test_config["mt5_login"],
            "password": test_config["mt5_password"],
            "server": test_config["mt5_server"]
        }
    )
    
    assert response.status_code == 200, "セッション作成に失敗しました"
    result = response.json()
    assert result["success"], f"セッション作成エラー: {result.get('message', '不明なエラー')}"
    assert "session_id" in result, "session_idが返されていません"
    
    return result["session_id"]

def test_session_list(api_client, test_config):
    """セッション一覧を取得してテストする"""
    response = api_client.get("/v5/session/list")
    
    assert response.status_code == 200, "セッション一覧の取得に失敗しました"
    result = response.json()
    assert "sessions" in result, "sessionsフィールドがありません"
    
    sessions = result["sessions"]
    assert isinstance(sessions, dict), "sessionsが辞書形式ではありません"
    
    # アクティブなセッションの情報を確認
    for session_id, session in sessions.items():
        assert "login" in session, "セッション情報にloginがありません"
        assert "server" in session, "セッション情報にserverがありません"
        assert isinstance(session["login"], int), "loginが整数ではありません"
        assert isinstance(session["server"], str), "serverが文字列ではありません"

def test_session_command(api_client, test_config, session_id):
    """セッションでコマンドを実行するテスト"""
    # シンボル情報取得コマンドをテスト
    response = api_client.post(
        f"/v5/session/{session_id}/command",
        json={
            "command": "symbols_get",
            "params": {}
        }
    )
    
    assert response.status_code == 200, "コマンド実行に失敗しました"
    result = response.json()
    assert result["success"], f"コマンド実行エラー: {result.get('message', '不明なエラー')}"
    assert "result" in result, "resultフィールドがありません"
    
    symbols = result["result"]
    assert isinstance(symbols, list), "シンボル情報がリスト形式ではありません"
    assert len(symbols) > 0, "シンボル情報が空です"

def test_session_cleanup(api_client, session_id):
    """セッションのクリーンアップをテストする"""
    response = api_client.delete(f"/v5/session/{session_id}")
    
    assert response.status_code == 200, "セッション削除に失敗しました"
    result = response.json()
    assert result["success"], f"セッション削除エラー: {result.get('message', '不明なエラー')}"

@pytest.mark.integration
def test_session_workflow(api_client, test_config):
    """セッションの一連の操作をテストする"""
    # セッション作成
    session_id = test_create_session(api_client, test_config)
    
    try:
        # セッション一覧の確認
        test_session_list(api_client, test_config)
        
        # コマンド実行
        test_session_command(api_client, test_config, session_id)
    
    finally:
        # クリーンアップ
        test_session_cleanup(api_client, session_id) 