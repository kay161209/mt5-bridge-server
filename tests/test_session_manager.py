#!/usr/bin/env python
"""
セッションマネージャーのテストモジュール
"""
import os
import sys
import time
import unittest
from datetime import datetime, timedelta
from app.session_manager import SessionManager, init_session_manager

class TestSessionManager(unittest.TestCase):
    def setUp(self):
        """テストの前準備"""
        self.test_config = {
            "mt5_login": 12345,
            "mt5_password": "test_password",
            "mt5_server": "test_server"
        }
        init_session_manager(base_path="./test_data", portable_mt5_path="path/to/test/mt5")
        self.session_manager = SessionManager()
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.session_manager.cleanup()
    
    def test_session_manager_initialization(self):
        """セッションマネージャーの初期化をテストする"""
        self.assertIsNotNone(self.session_manager)
        self.assertIsInstance(self.session_manager, SessionManager)
    
    def test_create_new_session(self):
        """新しいセッションの作成をテストする"""
        session_id = self.session_manager.create_session(
            login=self.test_config["mt5_login"],
            password=self.test_config["mt5_password"],
            server=self.test_config["mt5_server"]
        )
        
        self.assertIsNotNone(session_id)
        self.assertIsNotNone(self.session_manager.get_session(session_id))
        return session_id
    
    def test_get_session(self):
        """セッションの取得をテストする"""
        session_id = self.test_create_new_session()
        
        session = self.session_manager.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.login, self.test_config["mt5_login"])
        self.assertEqual(session.server, self.test_config["mt5_server"])
    
    def test_list_sessions(self):
        """セッション一覧の取得をテストする"""
        session_id = self.test_create_new_session()
        
        sessions = self.session_manager.list_sessions()
        self.assertIsInstance(sessions, dict)
        self.assertIn(session_id, sessions)
        
        session = sessions[session_id]
        self.assertEqual(session["login"], self.test_config["mt5_login"])
        self.assertEqual(session["server"], self.test_config["mt5_server"])
    
    def test_cleanup_old_sessions(self):
        """古いセッションのクリーンアップをテストする"""
        session_id = self.test_create_new_session()
        
        session = self.session_manager.get_session(session_id)
        session.last_access = datetime.now() - timedelta(hours=2)
        
        cleaned_sessions = self.session_manager.cleanup_old_sessions()
        self.assertIn(session_id, cleaned_sessions)
        self.assertIsNone(self.session_manager.get_session(session_id))
    
    def test_session_command_execution(self):
        """セッションでのコマンド実行をテストする"""
        session_id = self.test_create_new_session()
        
        result = self.session_manager.execute_command(
            session_id=session_id,
            command="symbols_get",
            params={}
        )
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

if __name__ == '__main__':
    unittest.main() 