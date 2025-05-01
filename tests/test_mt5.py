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
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.session_manager import init_session_manager, get_session_manager

class TestMT5:
    @pytest.fixture(autouse=True)
    def setup(self):
        """テストの前準備"""
        self.app = app
        self.client = TestClient(self.app)
        
        # 環境変数から設定を読み取る
        self.test_login = int(os.getenv("MT5_LOGIN", "12345"))
        self.test_password = os.getenv("MT5_PASSWORD", "test_password")
        self.test_server = os.getenv("MT5_SERVER", "test_server")
        settings.bridge_token = os.getenv("BRIDGE_TOKEN", "test_token")
        
        self.headers = {"x-api-token": settings.bridge_token}
        
        # セッションマネージャーの初期化
        init_session_manager()
        self.manager = get_session_manager()
        
        yield
        
        # テスト後のクリーンアップ
        self.manager.cleanup()
    
    def test_unauthorized_access(self):
        """認証なしのアクセスをテストする"""
        response = self.client.post(
            "/v5/session/create",
            json={
                "login": self.test_login,
                "password": self.test_password,
                "server": self.test_server
            }
        )
        assert response.status_code == 401
    
    def test_invalid_token(self):
        """無効なトークンでのアクセスをテストする"""
        response = self.client.post(
            "/v5/session/create",
            json={
                "login": self.test_login,
                "password": self.test_password,
                "server": self.test_server
            },
            headers={"x-api-token": "invalid_token"}
        )
        assert response.status_code == 401
    
    def test_create_session_invalid_data(self):
        """無効なデータでのセッション作成をテストする"""
        response = self.client.post(
            "/v5/session/create",
            json={
                "login": "invalid",  # loginは整数である必要がある
                "password": self.test_password,
                "server": self.test_server
            },
            headers=self.headers
        )
        assert response.status_code == 422  # バリデーションエラー
    
    def test_create_session(self):
        """セッション作成をテストする"""
        response = self.client.post(
            "/v5/session/create",
            json={
                "login": self.test_login,
                "password": self.test_password,
                "server": self.test_server
            },
            headers=self.headers
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "session_id" in result
        
        # セッションが実際に作成されたことを確認
        session = self.manager.get_session(result["session_id"])
        assert session is not None
        assert session.login == self.test_login
        assert session.server == self.test_server
        
        return result["session_id"]
    
    def test_session_list(self):
        """セッション一覧の取得をテストする"""
        # まずセッションを作成
        session_id = self.test_create_session()
        
        response = self.client.get(
            "/v5/session/list",
            headers=self.headers
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "sessions" in result
        sessions = result["sessions"]
        assert isinstance(sessions, dict)
        assert session_id in sessions
        assert sessions[session_id]["login"] == self.test_login
        assert sessions[session_id]["server"] == self.test_server
    
    def test_session_not_found(self):
        """存在しないセッションへのアクセスをテストする"""
        response = self.client.post(
            "/v5/session/nonexistent/command",
            json={
                "command": "symbols_get",
                "params": {}
            },
            headers=self.headers
        )
        assert response.status_code == 404
    
    def test_session_workflow(self):
        """セッションの一連の操作をテストする"""
        # セッション作成
        session_id = self.test_create_session()
        
        try:
            # セッション一覧の確認
            self.test_session_list()
            
            # コマンド実行
            response = self.client.post(
                f"/v5/session/{session_id}/command",
                json={
                    "command": "symbols_get",
                    "params": {}
                },
                headers=self.headers
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert "result" in result
            assert isinstance(result["result"], list)
            
        finally:
            # クリーンアップ
            response = self.client.delete(
                f"/v5/session/{session_id}",
                headers=self.headers
            )
            assert response.status_code == 200
            
            # セッションが実際に削除されたことを確認
            assert self.manager.get_session(session_id) is None

if __name__ == '__main__':
    pytest.main(["-v", __file__]) 