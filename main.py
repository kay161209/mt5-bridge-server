# main.py
import os
import logging
import sys
import io
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from app.routes import router as api_router
from app.config import settings
from app.session_manager import init_session_manager, get_session_manager, cleanup_resources
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import codecs
import json
import time
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
import signal
import atexit

# キーボード割り込みとシグナル処理
def signal_handler(sig, frame):
    """シグナル処理"""
    logger.info(f"シグナル {sig} を受信しました。クリーンアップを実行します...")
    cleanup_resources()
    sys.exit(0)

# SIGINTシグナル（Ctrl+C）の処理
signal.signal(signal.SIGINT, signal_handler)
if hasattr(signal, 'SIGBREAK'):  # Windowsの場合
    signal.signal(signal.SIGBREAK, signal_handler)

# 安全なストリームラッパー
def safe_wrap_stream(stream, encoding='utf-8'):
    if stream is None:
        return None
    try:
        if hasattr(stream, 'buffer'):
            return io.TextIOWrapper(stream.buffer, encoding=encoding, errors='replace')
        return stream
    except (ValueError, AttributeError):
        return stream

# プログラム終了時に標準ストリームを復元
def reset_streams():
    try:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    except:
        pass

# 標準出力と標準エラー出力を安全にラップ
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = safe_wrap_stream(sys.stdout)
sys.stderr = safe_wrap_stream(sys.stderr)

# プログラム終了時に実行
atexit.register(reset_streams)

# Configure logging first
os.makedirs('logs', exist_ok=True)
log_file = os.path.join('logs', 'server.log')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configure console handler with UTF-8 encoding
try:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
except (ValueError, AttributeError):
    pass

# Configure file handler with UTF-8 encoding
try:
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10485760, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
except (ValueError, AttributeError, PermissionError) as e:
    print(f"ファイルログハンドラの設定エラー: {e}")

# メインアプリケーションのクリーンアップ関数
def cleanup_app_resources():
    """アプリケーション終了時のクリーンアップ"""
    try:
        logger.info("アプリケーションリソースをクリーンアップしています...")
        # ロガーハンドラのクリーンアップ
        for handler in logger.handlers[:]:
            try:
                handler.close()
                logger.removeHandler(handler)
            except:
                pass
    except:
        pass

# 終了時にクリーンアップを実行
atexit.register(cleanup_app_resources)

# Verify encoding settings
logger.info(f"システムのデフォルトエンコーディング: {sys.getdefaultencoding()}")
logger.info(f"ファイルシステムエンコーディング: {sys.getfilesystemencoding()}")
logger.info(f"標準出力エンコーディング: {sys.stdout.encoding if hasattr(sys.stdout, 'encoding') else 'unknown'}")

app = FastAPI(
    title="MT5 Bridge API",
    version="1.0.0",
    docs_url="/docs", redoc_url="/redoc",
)

app.include_router(api_router, prefix="/v5")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session manager to handle MT5 sessions
session_manager = None

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
