#!/usr/bin/env python
"""
セッションマネージャーのテストモジュール
"""
import os
import sys
import time
import unittest
from datetime import datetime, timedelta
from app.session_manager import SessionManager, MT5Session

class TestSessionManager(unittest.TestCase):
    def setUp(self):
        """テストの前準備"""
        from app.session_manager import init_session_manager
        init_session_manager()  # セッションマネージャーを初期化
        self.manager = SessionManager()
        self.test_login = 12345
        self.test_password = "test_password"
        self.test_server = "test_server"
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.manager.cleanup()
    
    def test_session_manager_initialization(self):
        """セッションマネージャーの初期化をテストする"""
        self.assertIsNotNone(self.manager)
        self.assertIsInstance(self.manager, SessionManager)
    
    def test_create_session(self):
        """新しいセッションの作成をテストする"""
        session_id = self.manager.create_session(
            self.test_login, self.test_password, self.test_server
        )
        self.assertIsNotNone(session_id)
        session = self.manager.get_session(session_id)
        self.assertIsInstance(session, MT5Session)
        self.assertEqual(session.login, self.test_login)
        self.assertEqual(session.server, self.test_server)
    
    def test_get_session(self):
        """セッションの取得をテストする"""
        session_id = self.manager.create_session(
            self.test_login, self.test_password, self.test_server
        )
        session = self.manager.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.session_id, session_id)
    
    def test_list_sessions(self):
        """セッション一覧の取得をテストする"""
        session_id = self.manager.create_session(
            self.test_login, self.test_password, self.test_server
        )
        sessions = self.manager.list_sessions()
        self.assertIn(session_id, sessions)
        session_info = sessions[session_id]
        self.assertEqual(session_info["login"], self.test_login)
        self.assertEqual(session_info["server"], self.test_server)
    
    def test_cleanup_old_sessions(self):
        """古いセッションのクリーンアップをテストする"""
        session_id = self.manager.create_session(
            self.test_login, self.test_password, self.test_server
        )
        session = self.manager.get_session(session_id)
        session.last_access = datetime.now() - timedelta(hours=2)
        cleaned_sessions = self.manager.cleanup_old_sessions()
        self.assertIn(session_id, cleaned_sessions)
        self.assertIsNone(self.manager.get_session(session_id))
    
    def test_execute_command(self):
        """セッションでのコマンド実行をテストする"""
        session_id = self.manager.create_session(
            self.test_login, self.test_password, self.test_server
        )
        result = self.manager.execute_command(session_id, "symbols_get", {})
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertIn("name", result[0])
        self.assertIn("digits", result[0])

if __name__ == '__main__':
    unittest.main() 