import pytest
import asyncio
import websockets
import json
import time
from concurrent.futures import ThreadPoolExecutor
from app.config import settings
import requests
import statistics

# 負荷テストの設定
TEST_DURATION = 60  # テスト時間（秒）
CONCURRENT_USERS = 10  # 同時接続ユーザー数
REQUEST_INTERVAL = 0.1  # リクエスト間隔（秒）

class LoadTestMetrics:
    def __init__(self):
        self.response_times = []
        self.error_count = 0
        self.success_count = 0
        self.start_time = None
        self.end_time = None

    def add_response_time(self, response_time):
        self.response_times.append(response_time)

    def add_error(self):
        self.error_count += 1

    def add_success(self):
        self.success_count += 1

    def start(self):
        self.start_time = time.time()

    def stop(self):
        self.end_time = time.time()

    def get_summary(self):
        if not self.response_times:
            return {
                "total_requests": 0,
                "error_rate": 0,
                "avg_response_time": 0,
                "min_response_time": 0,
                "max_response_time": 0,
                "p95_response_time": 0,
                "total_duration": 0
            }

        return {
            "total_requests": self.success_count + self.error_count,
            "error_rate": self.error_count / (self.success_count + self.error_count),
            "avg_response_time": statistics.mean(self.response_times),
            "min_response_time": min(self.response_times),
            "max_response_time": max(self.response_times),
            "p95_response_time": statistics.quantiles(self.response_times, n=20)[18],
            "total_duration": self.end_time - self.start_time
        }

async def websocket_client(session_id: str, metrics: LoadTestMetrics):
    """WebSocketクライアントの処理"""
    uri = f"ws://localhost:8000/v5/ws/{session_id}?token={settings.bridge_token}"
    try:
        async with websockets.connect(uri) as websocket:
            start_time = time.time()
            
            # 初期化コマンドを送信
            await websocket.send(json.dumps({"type": "initialize"}))
            response = await websocket.recv()
            
            end_time = time.time()
            metrics.add_response_time(end_time - start_time)
            metrics.add_success()
            
            # テスト期間中、定期的にコマンドを送信
            while time.time() - start_time < TEST_DURATION:
                await asyncio.sleep(REQUEST_INTERVAL)
                
                start_time = time.time()
                await websocket.send(json.dumps({"type": "ping"}))
                await websocket.recv()
                end_time = time.time()
                
                metrics.add_response_time(end_time - start_time)
                metrics.add_success()
                
    except Exception as e:
        metrics.add_error()
        print(f"WebSocket error: {e}")

def http_client(session_id: str, metrics: LoadTestMetrics):
    """HTTPクライアントの処理"""
    headers = {"x-api-token": settings.bridge_token}
    base_url = "http://localhost:8000/v5"
    
    start_time = time.time()
    while time.time() - start_time < TEST_DURATION:
        try:
            req_start = time.time()
            response = requests.post(
                f"{base_url}/session/{session_id}/command",
                headers=headers,
                json={"type": "ping"}
            )
            req_end = time.time()
            
            if response.status_code == 200:
                metrics.add_success()
            else:
                metrics.add_error()
            
            metrics.add_response_time(req_end - req_start)
            time.sleep(REQUEST_INTERVAL)
            
        except Exception as e:
            metrics.add_error()
            print(f"HTTP error: {e}")

@pytest.mark.load
def test_websocket_load(session_manager):
    """WebSocket負荷テスト"""
    metrics = LoadTestMetrics()
    metrics.start()
    
    # テストセッションの作成
    sessions = [session_manager.create_session() for _ in range(CONCURRENT_USERS)]
    
    # 非同期タスクの作成
    loop = asyncio.get_event_loop()
    tasks = [
        websocket_client(session_id, metrics)
        for session_id in sessions
    ]
    
    # テストの実行
    loop.run_until_complete(asyncio.gather(*tasks))
    
    metrics.stop()
    summary = metrics.get_summary()
    
    # クリーンアップ
    for session_id in sessions:
        session = session_manager.get_session(session_id)
        if session:
            session.cleanup()
    
    # 結果の検証
    assert summary["error_rate"] < 0.1  # エラー率10%未満
    assert summary["p95_response_time"] < 1.0  # 95パーセンタイルのレスポンス時間が1秒未満

@pytest.mark.load
def test_http_load(session_manager):
    """HTTP負荷テスト"""
    metrics = LoadTestMetrics()
    metrics.start()
    
    # テストセッションの作成
    sessions = [session_manager.create_session() for _ in range(CONCURRENT_USERS)]
    
    # スレッドプールの作成
    with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        futures = [
            executor.submit(http_client, session_id, metrics)
            for session_id in sessions
        ]
        
        # すべてのタスクの完了を待機
        for future in futures:
            future.result()
    
    metrics.stop()
    summary = metrics.get_summary()
    
    # クリーンアップ
    for session_id in sessions:
        session = session_manager.get_session(session_id)
        if session:
            session.cleanup()
    
    # 結果の検証
    assert summary["error_rate"] < 0.1  # エラー率10%未満
    assert summary["p95_response_time"] < 1.0  # 95パーセンタイルのレスポンス時間が1秒未満 