from fastapi.testclient import TestClient
import pytest
from app.models import OrderCreate

def test_create_session(client, auth_headers):
    """セッション作成APIのテスト"""
    response = client.post("/v5/session/create", headers=auth_headers)
    assert response.status_code == 200
    assert "session_id" in response.json()

def test_session_command(client, auth_headers, test_session):
    """セッションコマンドAPIのテスト"""
    command = {"type": "initialize"}
    response = client.post(
        f"/v5/session/{test_session}/command",
        headers=auth_headers,
        json=command
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_delete_session(client, auth_headers, test_session):
    """セッション削除APIのテスト"""
    response = client.delete(
        f"/v5/session/{test_session}",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_list_sessions(client, auth_headers, test_session):
    """セッション一覧取得APIのテスト"""
    response = client.get("/v5/session/list", headers=auth_headers)
    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert isinstance(sessions, list)
    assert test_session in [s["id"] for s in sessions]

def test_unauthorized_access(client):
    """未認証アクセスのテスト"""
    response = client.post("/v5/session/create")
    assert response.status_code == 401

def test_invalid_session_access(client, auth_headers):
    """無効なセッションへのアクセステスト"""
    response = client.post(
        "/v5/session/invalid_session_id/command",
        headers=auth_headers,
        json={"type": "initialize"}
    )
    assert response.status_code == 404

@pytest.mark.websocket
def test_websocket_connection(client, auth_headers, test_session):
    """WebSocket接続のテスト"""
    with client.websocket_connect(
        f"/v5/ws/{test_session}?token={auth_headers['x-api-token']}"
    ) as websocket:
        # 初期化コマンドを送信
        websocket.send_json({"type": "initialize"})
        response = websocket.receive_json()
        assert response["success"] is True

@pytest.mark.websocket
def test_websocket_unauthorized(client, test_session):
    """未認証WebSocket接続のテスト"""
    with pytest.raises(Exception):
        with client.websocket_connect(f"/v5/ws/{test_session}"):
            pass 