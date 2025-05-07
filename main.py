# main.py
import os
import logging
import sys
import io
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from app.routes import router as api_router
from app.config import settings
from app.session_manager import init_session_manager, get_session_manager, cleanup_resources, SessionManager
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import codecs
import json
import time
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
import signal
import atexit
import traceback

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

# ロガー設定の改善
def configure_main_logger():
    """メインロガー設定 - グローバルロガーを設定"""
    logger = logging.getLogger("main")
    
    # 既存のハンドラがある場合は追加しない
    if logger.handlers:
        logger.debug(f"既存ハンドラ ({len(logger.handlers)}個) が存在するため新規ハンドラは追加しません")
        return logger
        
    logger.setLevel(logging.DEBUG)
    
    # ログディレクトリ作成
    os.makedirs('logs', exist_ok=True)
    
    # ファイルハンドラ
    file_handler = logging.FileHandler(os.path.join('logs', 'server.log'), encoding='utf-8', mode='a')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # コンソールハンドラ
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# グローバルロガー初期化
logger = configure_main_logger()

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
    version="1.2.0",
    description="MT5 Bridge API - 注意: /private/および/publicエンドポイントは非推奨です。代わりに/session/{session_id}/...形式のエンドポイントを使用してください。",
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
async def startup_event():
    """サーバー起動時の処理 - エラーハンドリング強化"""
    try:
        logger.info("サーバーを起動中...")
        
        # セッションマネージャー初期化
        try:
            # グローバル変数にも設定できるようにinit_session_managerを使用
            init_session_manager(
                base_path=settings.sessions_base_path, 
                portable_mt5_path=settings.mt5_portable_path
            )
            
            # app.stateにもセッションマネージャーを設定
            app.state.session_manager = get_session_manager()
            logger.info("セッションマネージャーを初期化しました")
        except Exception as e:
            logger.error(f"セッションマネージャーの初期化に失敗しました: {e}", exc_info=True)
            raise
        
        # 古いセッションのクリーンアップスケジューラーを設定
        try:
            app.state.cleanup_task = asyncio.create_task(cleanup_old_sessions())
            logger.info("クリーンアップスケジューラーを設定しました")
        except Exception as e:
            logger.error(f"クリーンアップスケジューラーの設定に失敗しました: {e}", exc_info=True)
            raise
            
        logger.info("サーバーの起動が完了しました")
    except Exception as e:
        logger.critical(f"サーバー起動中に致命的なエラーが発生しました: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """サーバーシャットダウン時の処理 - エラーハンドリング強化"""
    try:
        logger.info("サーバーをシャットダウン中...")
        
        # クリーンアップタスクをキャンセル
        if hasattr(app.state, 'cleanup_task') and app.state.cleanup_task:
            try:
                app.state.cleanup_task.cancel()
                logger.info("クリーンアップタスクをキャンセルしました")
            except Exception as e:
                logger.error(f"クリーンアップタスクのキャンセルに失敗しました: {e}")
        
        # セッションマネージャーのクリーンアップ
        if hasattr(app.state, 'session_manager'):
            try:
                await app.state.session_manager.cleanup()
                logger.info("セッションマネージャーをクリーンアップしました")
            except Exception as e:
                logger.error(f"セッションマネージャーのクリーンアップに失敗しました: {e}")
        
        # ロガーハンドラのクリーンアップ
        handlers = logger.handlers[:]
        for handler in handlers:
            try:
                handler.close()
                logger.removeHandler(handler)
            except Exception as e:
                # このエラーはログできないので標準出力に出力
                print(f"ロガーハンドラのクリーンアップ中にエラーが発生しました: {e}")
                
        logger.info("サーバーのシャットダウンが完了しました")
    except Exception as e:
        logger.error(f"サーバーシャットダウン中にエラーが発生しました: {e}", exc_info=True)

async def cleanup_old_sessions():
    """Background task to clean up expired sessions"""
    try:
        session_manager = get_session_manager()
        expired_sessions = session_manager.cleanup_old_sessions(max_age_seconds=settings.session_inactive_timeout)
        if expired_sessions and len(expired_sessions) > 0:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    except Exception as e:
        logger.error(f"Session cleanup error: {e}")

# The following endpoints have been removed and replaced with session-based ones in app/routes.py
# 
# @app.post("/v5/private/order/create")
# def place_order(req: dict, x_api_token: str | None = Header(None)):
#     check_token(x_api_token)
#     # req → MT5 format conversion and order placement
#     result = order_send({...})
#     return {"retCode":0,"result":result}

@app.websocket("/ws/{session_id}")
async def ws_endpoint(ws: WebSocket, session_id: str):
    """WebSocketエンドポイント - セッションベースの実装"""
    try:
        token = ws.query_params.get("token")
        if token != settings.bridge_token:
            await ws.close(code=4001)
            return
        
        await ws.accept()
        
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            logger.error(f"セッションが見つかりません: {session_id}")
            await ws.close(code=4004)
            return
        
        # WebSocketループ
        while True:
            try:
                command = await ws.receive_json()
                
                result = session.send_command(command)
                
                await ws.send_json(result)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket接続が切断されました: session_id={session_id}")
                break
            except Exception as e:
                logger.error(f"WebSocketエラー: {e}")
                await ws.send_json({
                    "success": False,
                    "error": str(e)
                })
    except Exception as e:
        logger.error(f"WebSocket処理エラー: {e}")
        try:
            await ws.close(code=1011)
        except:
            pass
