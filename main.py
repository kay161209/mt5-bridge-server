# main.py
import os
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from MetaTrader5 import initialize, shutdown, order_send
from app.routes import router as api_router
from app.mt5 import init_mt5, shutdown_mt5
from app.config import settings
from app.session_manager import init_session_manager
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.session_manager import get_session_manager

TOKEN = os.getenv("BRIDGE_TOKEN")
MT5_PATH = r"C:\MetaTrader5\terminal64.exe"    # インストール先に合わせる

app = FastAPI(
    title="MT5 Bridge API",
    version="1.0.0",
    docs_url="/docs", redoc_url="/redoc",
)

app.include_router(api_router, prefix="/v5")

def check_token(x_api_token: str | None):
    if x_api_token != TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.on_event("startup")
async def _startup():
    # グローバルなMT5初期化は不要
    # init_mt5() <- この行を削除
    
    # セッションマネージャーの初期化のみ行う
    init_session_manager(settings.sessions_base_path, settings.mt5_portable_path)
    
    # 定期的なセッションクリーンアップの設定
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        cleanup_old_sessions,
        'interval', 
        seconds=settings.cleanup_interval,
        id='session_cleanup'
    )
    scheduler.start()

@app.on_event("shutdown")
async def _shutdown():
    # グローバルなMT5シャットダウンも不要
    # shutdown_mt5() <- この行を削除
    
    # すべてのセッションをクリーンアップ
    try:
        session_manager = get_session_manager()
        session_manager.close_all_sessions()
    except Exception as e:
        print(f"セッションクリーンアップエラー: {e}")

async def cleanup_old_sessions():
    """期限切れセッションのクリーンアップを行うバックグラウンドタスク"""
    try:
        session_manager = get_session_manager()
        count = session_manager.cleanup_old_sessions(max_age_seconds=settings.session_inactive_timeout)
        if count > 0:
            print(f"{count}個の期限切れセッションをクリーンアップしました")
    except Exception as e:
        print(f"セッションクリーンアップエラー: {e}")

@app.post("/v5/private/order/create")
def place_order(req: dict, x_api_token: str | None = Header(None)):
    check_token(x_api_token)
    # req → MT5 フォーマットへ変換して発注
    result = order_send({...})
    return {"retCode":0,"result":result}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        token = ws.query_params.get("token")
        if token != TOKEN:
            await ws.close(code=4001)
            return
        while True:
            data = await ws.receive_text()
            # ここで MT5 の最新価格や発注結果を Push
            await ws.send_text("pong:"+data)
    except WebSocketDisconnect:
        pass
