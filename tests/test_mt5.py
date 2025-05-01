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
import unittest
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.mark.asyncio
class TestMT5:
    def setup_method(self):
        """テストの前準備"""
        self.app = app
        self.client = TestClient(self.app)
        settings.bridge_token = "test_token"
        self.headers = {"x-api-token": settings.bridge_token}
    
    def teardown_method(self):
        """テスト後のクリーンアップ"""
        pass
    
    async def test_mt5_direct_initialize(self):
        """MT5の直接初期化をテストする"""
        # MT5インスタンスのモックを使用
        pass
    
    async def test_create_session(self):
        """セッション作成をテストする"""
        response = self.client.post(
            "/v5/session/create",
            json={
                "login": 12345,
                "password": "test_password",
                "server": "test_server"
            },
            headers=self.headers
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "session_id" in result
        return result["session_id"]
    
    async def test_session_list(self):
        """セッション一覧を取得してテストする"""
        response = self.client.get(
            "/v5/session/list",
            headers=self.headers
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "sessions" in result
        assert isinstance(result["sessions"], dict)
    
    async def test_session_workflow(self):
        """セッションの一連の操作をテストする"""
        # セッション作成
        session_id = await self.test_create_session()
        
        try:
            # セッション一覧の確認
            await self.test_session_list()
            
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
            
        finally:
            # クリーンアップ
            response = self.client.delete(
                f"/v5/session/{session_id}",
                headers=self.headers
            )
            assert response.status_code == 200

def async_test(coro):
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper

# テストメソッドをデコレータでラップ
TestMT5.test_mt5_direct_initialize = async_test(TestMT5.test_mt5_direct_initialize)
TestMT5.test_create_session = async_test(TestMT5.test_create_session)
TestMT5.test_session_list = async_test(TestMT5.test_session_list)
TestMT5.test_session_workflow = async_test(TestMT5.test_session_workflow)

if __name__ == '__main__':
    unittest.main() 