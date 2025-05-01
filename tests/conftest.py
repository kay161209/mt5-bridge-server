import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.session_manager import init_session_manager, get_session_manager
import os
import logging

# テスト用のロガー設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# テスト用の設定
TEST_BRIDGE_TOKEN = "test_token"
TEST_MT5_PATH = os.getenv("TEST_MT5_PATH", "path/to/test/mt5")

@pytest.fixture
def test_app():
    """
    テスト用のFastAPIアプリケーションを提供
    """
    # テスト用の設定を適用
    settings.bridge_token = TEST_BRIDGE_TOKEN
    return app

@pytest.fixture
def client(test_app):
    """
    テスト用のHTTPクライアント
    """
    return TestClient(test_app)

@pytest.fixture
def auth_headers():
    """
    認証用ヘッダー
    """
    return {"x-api-token": TEST_BRIDGE_TOKEN}

@pytest.fixture
def session_manager():
    """
    テスト用のセッションマネージャー
    """
    init_session_manager(base_path="./test_data", portable_mt5_path=TEST_MT5_PATH)
    manager = get_session_manager()
    yield manager
    # テスト後のクリーンアップ
    manager.cleanup()

@pytest.fixture
def test_session(session_manager):
    """
    テスト用のMT5セッション
    """
    session_id = session_manager.create_session()
    yield session_id
    # テスト後のクリーンアップ
    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            session.cleanup() 