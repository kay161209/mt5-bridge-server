from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect, Depends, BackgroundTasks
from app.config import settings
from app import mt5
from app.models import (
    OrderCreate, OrderResponse, CandleRequest, CandleResponse,
    LoginRequest, VersionResponse, ErrorResponse, AccountInfoResponse,
    TerminalInfoResponse, SymbolsRequest, SymbolInfoRequest, SymbolInfoResponse,
    SymbolTickResponse, SymbolSelectRequest, MarketBookRequest, MarketBookResponse,
    TicksRequest, TicksRangeRequest, TicksResponse, OrderRequest, OrderCheckResponse,
    OrderSendResponse, PositionsRequest, PositionsResponse, HistoryOrdersRequest,
    HistoryOrdersResponse, HistoryDealsRequest, HistoryDealsResponse, CandlesRangeRequest,
    SessionCreateRequest, SessionCreateResponse, SessionsListResponse,
    PositionCloseRequest, PositionClosePartialRequest, PositionModifyRequest,
    OrderCancelRequest, OrderModifyRequest
)
from app.session_manager import get_session_manager
from typing import List, Optional, Dict, Any
import asyncio
import json
from datetime import datetime
import logging
import os, getpass

router = APIRouter()
logger = logging.getLogger(__name__)

def check_token(x_api_token: str | None = Header(None)):
    """トークン認証"""
    if x_api_token != settings.bridge_token:
        raise HTTPException(status_code=401, detail="無効なトークンです")

# ----- セッション管理エンドポイント ----- #

@router.post("/session/create", response_model=SessionCreateResponse)
async def create_session(
    req: SessionCreateRequest,
    x_api_token: str | None = Header(None)
):
    """新しいセッションの作成"""
    check_token(x_api_token)
    
    try:
        session_manager = get_session_manager()
        session_id = session_manager.create_session(
            login=req.login,
            password=req.password,
            server=req.server
        )
        
        return {
            "session_id": session_id,
            "success": True,
            "message": "セッションが正常に作成されました"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"セッションの作成に失敗しました: {str(e)}"
        )

@router.post("/session/{session_id}/command")
async def execute_command(
    session_id: str,
    command: Dict[str, Any],
    x_api_token: str | None = Header(None)
):
    """セッションでコマンドを実行"""
    check_token(x_api_token)
    
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    result = session.send_command(command)
    return result

@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    x_api_token: str | None = Header(None)
):
    """セッションの削除"""
    check_token(x_api_token)
    
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    session.cleanup()
    return {"success": True}

@router.get("/session/list", response_model=SessionsListResponse)
def list_sessions(x_api_token: str | None = Header(None)):
    """アクティブなセッションのリストを取得"""
    check_token(x_api_token)
    
    session_manager = get_session_manager()
    return {"sessions": session_manager.list_sessions()}

@router.delete("/session")
def close_all_sessions(x_api_token: str | None = Header(None), background_tasks: BackgroundTasks = None):
    """すべてのセッションを終了"""
    check_token(x_api_token)
    
    session_manager = get_session_manager()
    
    if background_tasks:
        # バックグラウンドで終了処理を行う
        background_tasks.add_task(session_manager.close_all_sessions)
        return {"success": True, "message": "セッション終了処理をバックグラウンドで実行中"}
    else:
        count = session_manager.close_all_sessions()
        return {"success": True, "closed_count": count}

# ----- セッションIDを指定するバージョンのエンドポイント ----- #

@router.post("/session/{session_id}/order/create", response_model=OrderResponse)
def session_order_create(session_id: str, req: OrderCreate, x_api_token: str | None = Header(None)):
    """指定セッションで注文を発注"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    # MT5命令を送信
    params = req.dict()
    cmd_res = session.send_command({"type": "order_send", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    res = cmd_res.get("result") or {}
    # retCode として retcode フィールドを利用
    return {"retCode": res.get("retcode", -1), "result": res}

@router.get("/session/{session_id}/quote")
def session_quote(session_id: str, symbol: str, x_api_token: str | None = Header(None)):
    """指定セッションで価格を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    # MT5命令を送信
    cmd_res = session.send_command({"type": "quote", "params": {"symbol": symbol}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.post("/session/{session_id}/candles", response_model=CandleResponse)
def session_get_candles(session_id: str, req: CandleRequest, x_api_token: str | None = Header(None)):
    """指定セッションでローソク足データを取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    # コマンド送信
    params: Dict[str, Any] = {
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "count": req.count
    }
    if req.start_time:
        # datetime を UNIX タイムスタンプ (秒) に変換して JSON シリアライズ可能にする
        params["start_time"] = int(req.start_time.timestamp())
    result = session.send_command({"type": "candles", "params": params})
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return {"data": result.get("result")}

# 他のセッションエンドポイントはここに追加...

# ---- HTTP エンドポイント ---- #

@router.post("/private/order/create", response_model=OrderResponse)
def order_create(req: OrderCreate, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで注文を発注"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = req.dict()
    cmd_res = session.send_command({"type": "order_send", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    res = cmd_res.get("result") or {}
    
    # retCode として retcode フィールドを利用
    return {"retCode": res.get("retcode", -1), "result": res}

@router.get("/public/quote")
def quote(symbol: str, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで価格を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "quote", "params": {"symbol": symbol}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.post("/public/candles", response_model=CandleResponse)
def get_candles(req: CandleRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでローソク足データを取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # コマンド送信
    params: Dict[str, Any] = {
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "count": req.count
    }
    if req.start_time:
        # datetime を UNIX タイムスタンプ (秒) に変換して JSON シリアライズ可能にする
        params["start_time"] = int(req.start_time.timestamp())
    result = session.send_command({"type": "candles", "params": params})
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return {"data": result.get("result")}

# ---- 追加エンドポイント ---- #

@router.post("/private/login")
def login(req: LoginRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでログイン"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "login", "params": req.dict()})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"success": True}

@router.get("/public/version", response_model=VersionResponse)
def get_version(session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでバージョン取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "version", "params": {}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"version": cmd_res.get("result")}

@router.get("/public/last_error", response_model=ErrorResponse)
def get_last_error(session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで最後のエラー取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "last_error", "params": {}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.get("/private/account_info", response_model=AccountInfoResponse)
def get_account_info(session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでアカウント情報取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "account_info", "params": {}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.get("/public/terminal_info", response_model=TerminalInfoResponse)
def get_terminal_info(session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでターミナル情報取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "terminal_info", "params": {}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.get("/public/symbols_total")
def get_symbols_total(session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでシンボル総数取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "symbols_total", "params": {}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"total": cmd_res.get("result")}

@router.post("/public/symbols")
def get_symbols(session_id: str, x_api_token: str | None = Header(None), req: Optional[SymbolsRequest] = None):
    """セッションベースでシンボル一覧取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {}
    if req and req.group:
        params["group"] = req.group
    
    cmd_res = session.send_command({"type": "symbols", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"symbols": cmd_res.get("result")}

@router.post("/public/symbol_info", response_model=SymbolInfoResponse)
def get_symbol_info(req: SymbolInfoRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでシンボル情報取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "symbol_info", "params": {"symbol": req.symbol}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.post("/public/symbol_info_tick", response_model=SymbolTickResponse)
def get_symbol_info_tick(req: SymbolInfoRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでシンボルティック情報取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "symbol_info_tick", "params": {"symbol": req.symbol}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.post("/public/symbol_select")
def symbol_select(req: SymbolSelectRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでシンボル選択"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "symbol_select", "params": req.dict()})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"success": True}

@router.post("/public/market_book_add")
def market_book_add(req: MarketBookRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで板情報追加"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "market_book_add", "params": {"symbol": req.symbol}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"success": True}

@router.post("/public/market_book_get", response_model=MarketBookResponse)
def market_book_get(req: MarketBookRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで板情報取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "market_book_get", "params": {"symbol": req.symbol}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"items": cmd_res.get("result")}

@router.post("/public/market_book_release")
def market_book_release(req: MarketBookRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで板情報解放"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "market_book_release", "params": {"symbol": req.symbol}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"success": True}

@router.post("/public/candles_range", response_model=CandleResponse)
def get_candles_range(req: CandlesRangeRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで期間指定ローソク足データを取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "date_from": int(req.date_from.timestamp()) if req.date_from else None,
        "date_to": int(req.date_to.timestamp()) if req.date_to else None
    }
    
    cmd_res = session.send_command({"type": "candles_range", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"data": cmd_res.get("result")}

@router.post("/public/ticks_from", response_model=TicksResponse)
def get_ticks_from(req: TicksRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで指定日時以降のティックデータを取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "symbol": req.symbol,
        "date_from": int(req.date_from.timestamp()) if req.date_from else None,
        "count": req.count,
        "flags": req.flags
    }
    
    cmd_res = session.send_command({"type": "ticks_from", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"ticks": cmd_res.get("result")}

@router.post("/public/ticks_range", response_model=TicksResponse)
def get_ticks_range(req: TicksRangeRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで期間指定ティックデータを取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "symbol": req.symbol,
        "date_from": int(req.date_from.timestamp()) if req.date_from else None,
        "date_to": int(req.date_to.timestamp()) if req.date_to else None,
        "flags": req.flags
    }
    
    cmd_res = session.send_command({"type": "ticks_range", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"ticks": cmd_res.get("result")}

@router.get("/private/orders_total")
def get_orders_total(session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで注文総数を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "orders_total", "params": {}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"total": cmd_res.get("result")}

@router.post("/private/orders")
def get_orders(
    session_id: str,
    x_api_token: str | None = Header(None),
    symbol: Optional[str] = None, 
    group: Optional[str] = None, 
    ticket: Optional[int] = None
):
    """セッションベースで注文一覧を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {}
    if symbol:
        params["symbol"] = symbol
    if group:
        params["group"] = group
    if ticket:
        params["ticket"] = ticket
    
    cmd_res = session.send_command({"type": "orders", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"orders": cmd_res.get("result")}

@router.post("/private/order_calc_margin")
def order_calc_margin(
    session_id: str,
    action: int, 
    symbol: str, 
    volume: float, 
    price: float,
    x_api_token: str | None = Header(None)
):
    """セッションベースで証拠金計算"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "action": action,
        "symbol": symbol,
        "volume": volume,
        "price": price
    }
    
    cmd_res = session.send_command({"type": "order_calc_margin", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"margin": cmd_res.get("result")}

@router.post("/private/order_calc_profit")
def order_calc_profit(
    session_id: str,
    action: int, 
    symbol: str, 
    volume: float, 
    price_open: float,
    price_close: float,
    x_api_token: str | None = Header(None)
):
    """セッションベースで利益計算"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "action": action,
        "symbol": symbol,
        "volume": volume,
        "price_open": price_open,
        "price_close": price_close
    }
    
    cmd_res = session.send_command({"type": "order_calc_profit", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"profit": cmd_res.get("result")}

@router.post("/private/order_check", response_model=OrderCheckResponse)
def order_check(req: OrderRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで注文チェック"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "order_check", "params": req.dict()})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.post("/private/order_send", response_model=OrderSendResponse)
def order_send(req: OrderRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで注文送信"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "order_send", "params": req.dict()})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.get("/private/positions_total")
def get_positions_total(session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでポジション総数を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    cmd_res = session.send_command({"type": "positions_total", "params": {}})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"total": cmd_res.get("result")}

@router.post("/private/positions", response_model=PositionsResponse)
def get_positions(req: PositionsRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでポジション一覧を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "symbol": req.symbol,
        "group": req.group,
        "ticket": req.ticket
    }
    cmd_res = session.send_command({"type": "positions", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"positions": cmd_res.get("result")}

@router.post("/private/history_orders_total")
def get_history_orders_total(
    session_id: str,
    x_api_token: str | None = Header(None),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
):
    """セッションベースで注文履歴総数を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {}
    if date_from:
        params["date_from"] = int(date_from.timestamp())
    if date_to:
        params["date_to"] = int(date_to.timestamp())
    
    cmd_res = session.send_command({"type": "history_orders_total", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"total": cmd_res.get("result")}

@router.post("/private/history_orders", response_model=HistoryOrdersResponse)
def get_history_orders(req: HistoryOrdersRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで注文履歴を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "group": req.group,
        "ticket": req.ticket,
        "position": req.position
    }
    if req.date_from:
        params["date_from"] = int(req.date_from.timestamp())
    if req.date_to:
        params["date_to"] = int(req.date_to.timestamp())
    
    cmd_res = session.send_command({"type": "history_orders", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"orders": cmd_res.get("result")}

@router.post("/private/history_deals_total")
def get_history_deals_total(
    session_id: str,
    x_api_token: str | None = Header(None),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
):
    """セッションベースで約定履歴総数を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {}
    if date_from:
        params["date_from"] = int(date_from.timestamp())
    if date_to:
        params["date_to"] = int(date_to.timestamp())
    
    cmd_res = session.send_command({"type": "history_deals_total", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"total": cmd_res.get("result")}

@router.post("/private/history_deals", response_model=HistoryDealsResponse)
def get_history_deals(req: HistoryDealsRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで約定履歴を取得"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "group": req.group,
        "ticket": req.ticket,
        "position": req.position
    }
    if req.date_from:
        params["date_from"] = int(req.date_from.timestamp())
    if req.date_to:
        params["date_to"] = int(req.date_to.timestamp())
    
    cmd_res = session.send_command({"type": "history_deals", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return {"deals": cmd_res.get("result")}


@router.post("/private/position/close")
def position_close(req: PositionCloseRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでポジションを閉じる"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "symbol": req.symbol,
        "ticket": req.ticket
    }
    cmd_res = session.send_command({"type": "position_close", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.post("/private/position/close_partial")
def position_close_partial(req: PositionClosePartialRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでポジションを部分的に閉じる"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "ticket": req.ticket,
        "volume": req.volume
    }
    cmd_res = session.send_command({"type": "position_close_partial", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.post("/private/position/modify")
def position_modify(req: PositionModifyRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースでポジションのSL/TPを変更する"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "ticket": req.ticket,
        "sl": req.sl,
        "tp": req.tp
    }
    cmd_res = session.send_command({"type": "position_modify", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")


@router.post("/private/order/cancel")
def order_cancel(req: OrderCancelRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで注文をキャンセルする"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "ticket": req.ticket
    }
    cmd_res = session.send_command({"type": "order_cancel", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

@router.post("/private/order/modify")
def order_modify(req: OrderModifyRequest, session_id: str, x_api_token: str | None = Header(None)):
    """セッションベースで注文を変更する"""
    check_token(x_api_token)
    
    # セッションを取得
    session = get_session_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # MT5命令を送信
    params = {
        "ticket": req.ticket,
        "price": req.price,
        "sl": req.sl,
        "tp": req.tp,
        "expiration": req.expiration
    }
    cmd_res = session.send_command({"type": "order_modify", "params": params})
    if not cmd_res.get("success"):
        raise HTTPException(status_code=500, detail=cmd_res.get("error"))
    return cmd_res.get("result")

# ---- WebSocket ---- #

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocketエンドポイント"""
    try:
        # クエリパラメータからトークンを取得
        token = websocket.query_params.get("token")
        if token != settings.bridge_token:
            await websocket.close(code=4001)
            return
        
        await websocket.accept()
        
        # セッションの取得
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            await websocket.close(code=4004)
            return
        
        # WebSocketループ
        while True:
            try:
                # コマンドの受信
                command = await websocket.receive_json()
                
                # コマンドの実行
                result = session.send_command(command)
                
                # 結果の送信
                await websocket.send_json(result)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket接続が切断されました: session_id={session_id}")
                break
            except Exception as e:
                logger.error(f"WebSocketエラー: {e}")
                await websocket.send_json({
                    "success": False,
                    "error": str(e)
                })
                
    except Exception as e:
        logger.error(f"WebSocket処理エラー: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass

@router.get("/debug/whoami")
def debug_whoami():
    """このプロセスを動かしているOSユーザー情報を返します"""
    user_login = None
    try:
        user_login = os.getlogin()
    except Exception:
        pass
    ps_user = None
    try:
        import psutil
        ps_user = psutil.Process(os.getpid()).username()
    except Exception:
        pass
    return {
        "os_getlogin": user_login,
        "getpass_user": getpass.getuser(),
        "psutil_user": ps_user
    }                                                                                                                                