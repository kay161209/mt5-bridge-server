# main.py
import os
import logging
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from app.routes import router as api_router
from app.config import settings
from app.session_manager import init_session_manager, get_session_manager
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Logger configuration
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
    logger.info("Server starting up...")
    
    # Initialize session manager
    logger.info(f"Initializing session manager: {settings.sessions_base_path}, {settings.mt5_portable_path}")
    init_session_manager(settings.sessions_base_path, settings.mt5_portable_path)
    
    # Set up periodic session cleanup
    logger.info(f"Setting up cleanup scheduler: {settings.cleanup_interval} seconds interval")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        cleanup_old_sessions,
        'interval', 
        seconds=settings.cleanup_interval,
        id='session_cleanup'
    )
    scheduler.start()
    
    logger.info("Server startup complete")

@app.on_event("shutdown")
async def _shutdown():
    logger.info("Server shutting down...")
    
    # Clean up all sessions
    try:
        session_manager = get_session_manager()
        count = session_manager.close_all_sessions()
        logger.info(f"Cleaned up {count} sessions")
    except Exception as e:
        logger.error(f"Session cleanup error: {e}")
    
    logger.info("Server shutdown complete")

async def cleanup_old_sessions():
    """Background task to clean up expired sessions"""
    try:
        session_manager = get_session_manager()
        count = session_manager.cleanup_old_sessions(max_age_seconds=settings.session_inactive_timeout)
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
    except Exception as e:
        logger.error(f"Session cleanup error: {e}")

# The following endpoints have been removed and replaced with session-based ones in app/routes.py
# @app.post("/v5/private/order/create")
# def place_order(req: dict, x_api_token: str | None = Header(None)):
#     check_token(x_api_token)
#     # req → MT5 format conversion and order placement
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
        
        # WebSocket session needs to be changed to session-based
        # This is a simple implementation that just responds to pings
        while True:
            data = await ws.receive_text()
            await ws.send_text("pong:"+data)
    except WebSocketDisconnect:
        pass
