# main.py
import os
import logging
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from app.routes import router as api_router
from app.config import settings
from app.session_manager import init_session_manager, get_session_manager
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ロガー設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

app = FastAPI(
    title="MT5 Bridge API",
    version="1.0.0",
    docs_url="/docs", redoc_url="/redoc",
)

app.include_router(api_router, prefix="/v5")

def check_token(x_api_token: str | None):
    if x_api_token != settings.bridge_token:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.on_event("startup")
async def _startup():
    logger.info("サーバー起動中...")
    
    # セッションマネージャーの初期化
    logger.info(f"セッションマネージャー初期化: {settings.sessions_base_path}, {settings.mt5_portable_path}")
    init_session_manager(settings.sessions_base_path, settings.mt5_portable_path)
    
    # 定期的なセッションクリーンアップの設定
    logger.info(f"クリーンアップスケジューラ設定: {settings.cleanup_interval}秒間隔")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        cleanup_old_sessions,
        'interval', 
        seconds=settings.cleanup_interval,
        id='session_cleanup'
    )
    scheduler.start()
    
    logger.info("サーバー起動完了")

@app.on_event("shutdown")
async def _shutdown():
    logger.info("サーバーシャットダウン中...")
    
    # すべてのセッションをクリーンアップ
    try:
        session_manager = get_session_manager()
        count = session_manager.close_all_sessions()
        logger.info(f"{count}個のセッションをクリーンアップしました")
    except Exception as e:
        logger.error(f"セッションクリーンアップエラー: {e}")
    
    logger.info("サーバーシャットダウン完了")

async def cleanup_old_sessions():
    """期限切れセッションのクリーンアップを行うバックグラウンドタスク"""
    try:
        session_manager = get_session_manager()
        count = session_manager.cleanup_old_sessions(max_age_seconds=settings.session_inactive_timeout)
        if count > 0:
            logger.info(f"{count}個の期限切れセッションをクリーンアップしました")
    except Exception as e:
        logger.error(f"セッションクリーンアップエラー: {e}")

# 以下のエンドポイントは削除し、app/routes.pyのセッションベースのものに置き換える
# @app.post("/v5/private/order/create")
# def place_order(req: dict, x_api_token: str | None = Header(None)):
#     check_token(x_api_token)
#     # req → MT5 フォーマットへ変換して発注
#     result = order_send({...})
#     return {"retCode":0,"result":result}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        token = ws.query_params.get("token")
        if token != settings.bridge_token:
            await ws.close(code=4001)
            return
        
        # WebSocketセッションはセッションベースに変更する必要がある
        # ここでは単純なpingに応答するだけの実装に変更
        while True:
            data = await ws.receive_text()
            await ws.send_text("pong:"+data)
    except WebSocketDisconnect:
        pass
