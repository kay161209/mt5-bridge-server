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
    SessionCreateRequest, SessionCreateResponse, SessionsListResponse
)
from app.session_manager import get_session_manager
from typing import List, Optional
import asyncio
import json
from datetime import datetime

router = APIRouter()

def _auth(token: str | None):
    if token != settings.bridge_token:
        raise HTTPException(status_code=401, detail="Invalid token")

# ----- セッション管理エンドポイント ----- #

@router.post("/session/create", response_model=SessionCreateResponse)
def create_session(req: SessionCreateRequest, x_api_token: str | None = Header(None)):
    """新しいMT5セッションを作成"""
    _auth(x_api_token)
    
    try:
        session_manager = get_session_manager()
        session_id = session_manager.create_session(
            login=req.login,
            password=req.password,
            server=req.server
        )
        return {
            "session_id": session_id,
            "success": True
        }
    except Exception as e:
        return {
            "session_id": "",
            "success": False,
            "message": str(e)
        }

@router.get("/session/list", response_model=SessionsListResponse)
def list_sessions(x_api_token: str | None = Header(None)):
    """アクティブなセッションのリストを取得"""
    _auth(x_api_token)
    
    session_manager = get_session_manager()
    return {"sessions": session_manager.get_all_sessions()}

@router.delete("/session/{session_id}")
def close_session(session_id: str, x_api_token: str | None = Header(None)):
    """指定されたセッションを終了"""
    _auth(x_api_token)
    
    session_manager = get_session_manager()
    success = session_manager.close_session(session_id)
    return {"success": success}

@router.delete("/session")
def close_all_sessions(x_api_token: str | None = Header(None), background_tasks: BackgroundTasks = None):
    """すべてのセッションを終了"""
    _auth(x_api_token)
    
    session_manager = get_session_manager()
    
    if background_tasks:
        # バックグラウンドで終了処理を行う
        background_tasks.add_task(session_manager.close_all_sessions)
        return {"success": True, "message": "セッション終了処理をバックグラウンドで実行中"}
    else:
        count = session_manager.close_all_sessions()
        return {"success": True, "closed_count": count}

# ----- セッションIDを指定するバージョンのエンドポイント ----- #

@router.post("/{session_id}/order/create", response_model=OrderResponse)
def session_order_create(session_id: str, req: OrderCreate, x_api_token: str | None = Header(None)):
    """指定セッションで注文を発注"""
    _auth(x_api_token)
    
    # セッションを取得
    try:
        session_manager = get_session_manager()
        session_manager.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    # セッションではMT5はすでに初期化されているので、直接注文発注
    result = mt5.place_order(req)
    code = 0 if result > 0 else -1
    return {"retCode": code, "result": {"ticket": result}}

@router.get("/{session_id}/quote")
def session_quote(session_id: str, symbol: str, x_api_token: str | None = Header(None)):
    """指定セッションで価格を取得"""
    _auth(x_api_token)
    
    # セッションを取得
    try:
        session_manager = get_session_manager()
        session_manager.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    return mt5.get_price(symbol)

@router.post("/{session_id}/candles", response_model=CandleResponse)
def session_get_candles(session_id: str, req: CandleRequest, x_api_token: str | None = Header(None)):
    """指定セッションでローソク足データを取得"""
    _auth(x_api_token)
    
    # セッションを取得
    try:
        session_manager = get_session_manager()
        session_manager.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"セッション {session_id} が見つかりません")
    
    candles = mt5.get_candles(
        symbol=req.symbol,
        timeframe=req.timeframe,
        count=req.count,
        start_time=req.start_time
    )
    return {"data": candles}

# 他のセッションエンドポイントはここに追加...

# ---- HTTP エンドポイント ---- #

@router.post("/private/order/create", response_model=OrderResponse)
def order_create(req: OrderCreate, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    result = mt5.place_order(req)
    code = 0 if result > 0 else -1
    return {"retCode": code, "result": {"ticket": result}}

@router.get("/public/quote")
def quote(symbol: str, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return mt5.get_price(symbol)

@router.post("/public/candles", response_model=CandleResponse)
def get_candles(req: CandleRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    candles = mt5.get_candles(
        symbol=req.symbol,
        timeframe=req.timeframe,
        count=req.count,
        start_time=req.start_time
    )
    return {"data": candles}

# ---- 追加エンドポイント ---- #

@router.post("/private/login")
def login(req: LoginRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    success = mt5.login(req.login, req.password, req.server)
    return {"success": success}

@router.get("/public/version", response_model=VersionResponse)
def get_version(x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return {"version": mt5.get_version()}

@router.get("/public/last_error", response_model=ErrorResponse)
def get_last_error(x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return mt5.get_last_error()

@router.get("/private/account_info", response_model=AccountInfoResponse)
def get_account_info(x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return mt5.get_account_info()

@router.get("/public/terminal_info", response_model=TerminalInfoResponse)
def get_terminal_info(x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return mt5.get_terminal_info()

@router.get("/public/symbols_total")
def get_symbols_total(x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return {"total": mt5.get_symbols_total()}

@router.post("/public/symbols")
def get_symbols(req: SymbolsRequest = None, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    group = req.group if req else None
    return {"symbols": mt5.get_symbols(group)}

@router.post("/public/symbol_info", response_model=SymbolInfoResponse)
def get_symbol_info(req: SymbolInfoRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return mt5.get_symbol_info(req.symbol)

@router.post("/public/symbol_info_tick", response_model=SymbolTickResponse)
def get_symbol_info_tick(req: SymbolInfoRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return mt5.get_symbol_info_tick(req.symbol)

@router.post("/public/symbol_select")
def symbol_select(req: SymbolSelectRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    success = mt5.symbol_select(req.symbol, req.enable)
    return {"success": success}

@router.post("/public/market_book_add")
def market_book_add(req: MarketBookRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    success = mt5.market_book_add(req.symbol)
    return {"success": success}

@router.post("/public/market_book_get", response_model=MarketBookResponse)
def market_book_get(req: MarketBookRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    items = mt5.market_book_get(req.symbol)
    return {"items": items}

@router.post("/public/market_book_release")
def market_book_release(req: MarketBookRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    success = mt5.market_book_release(req.symbol)
    return {"success": success}

@router.post("/public/candles_range", response_model=CandleResponse)
def get_candles_range(req: CandlesRangeRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    candles = mt5.get_candles_range(
        symbol=req.symbol,
        timeframe=req.timeframe,
        date_from=req.date_from,
        date_to=req.date_to
    )
    return {"data": candles}

@router.post("/public/ticks_from", response_model=TicksResponse)
def get_ticks_from(req: TicksRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    ticks = mt5.get_ticks_from(
        symbol=req.symbol,
        date_from=req.date_from,
        count=req.count,
        flags=req.flags
    )
    return {"ticks": ticks}

@router.post("/public/ticks_range", response_model=TicksResponse)
def get_ticks_range(req: TicksRangeRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    ticks = mt5.get_ticks_range(
        symbol=req.symbol,
        date_from=req.date_from,
        date_to=req.date_to,
        flags=req.flags
    )
    return {"ticks": ticks}

@router.get("/private/orders_total")
def get_orders_total(x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return {"total": mt5.get_orders_total()}

@router.post("/private/orders")
def get_orders(
    symbol: Optional[str] = None, 
    group: Optional[str] = None, 
    ticket: Optional[int] = None,
    x_api_token: str | None = Header(None)
):
    _auth(x_api_token)
    orders = mt5.get_orders(symbol, group, ticket)
    return {"orders": orders}

@router.post("/private/order_calc_margin")
def order_calc_margin(
    action: int, 
    symbol: str, 
    volume: float, 
    price: float,
    x_api_token: str | None = Header(None)
):
    _auth(x_api_token)
    margin = mt5.order_calc_margin(action, symbol, volume, price)
    return {"margin": margin}

@router.post("/private/order_calc_profit")
def order_calc_profit(
    action: int, 
    symbol: str, 
    volume: float, 
    price_open: float,
    price_close: float,
    x_api_token: str | None = Header(None)
):
    _auth(x_api_token)
    profit = mt5.order_calc_profit(action, symbol, volume, price_open, price_close)
    return {"profit": profit}

@router.post("/private/order_check", response_model=OrderCheckResponse)
def order_check(req: OrderRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    request_dict = req.dict()
    return mt5.order_check(request_dict)

@router.post("/private/order_send", response_model=OrderSendResponse)
def order_send(req: OrderRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    request_dict = req.dict()
    return mt5.order_send(request_dict)

@router.get("/private/positions_total")
def get_positions_total(x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    return {"total": mt5.get_positions_total()}

@router.post("/private/positions", response_model=PositionsResponse)
def get_positions(req: PositionsRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    positions = mt5.get_positions(req.symbol, req.group, req.ticket)
    return {"positions": positions}

@router.post("/private/history_orders_total")
def get_history_orders_total(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    x_api_token: str | None = Header(None)
):
    _auth(x_api_token)
    total = mt5.get_history_orders_total(date_from, date_to)
    return {"total": total}

@router.post("/private/history_orders", response_model=HistoryOrdersResponse)
def get_history_orders(req: HistoryOrdersRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    orders = mt5.get_history_orders(
        date_from=req.date_from,
        date_to=req.date_to,
        group=req.group,
        ticket=req.ticket,
        position=req.position
    )
    return {"orders": orders}

@router.post("/private/history_deals_total")
def get_history_deals_total(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    x_api_token: str | None = Header(None)
):
    _auth(x_api_token)
    total = mt5.get_history_deals_total(date_from, date_to)
    return {"total": total}

@router.post("/private/history_deals", response_model=HistoryDealsResponse)
def get_history_deals(req: HistoryDealsRequest, x_api_token: str | None = Header(None)):
    _auth(x_api_token)
    deals = mt5.get_history_deals(
        date_from=req.date_from,
        date_to=req.date_to,
        group=req.group,
        ticket=req.ticket,
        position=req.position
    )
    return {"deals": deals}

# ---- WebSocket ---- #

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    token = ws.query_params.get("token")
    if token != settings.bridge_token:
        await ws.close(code=4001, reason="Invalid token")
        return
    try:
        while True:
            # Echo 受信（心拍代わり）
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=settings.ws_broadcast_interval)
                if msg != "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                pass  # interval 経過で定期プッシュ
            
            # 例: EURUSD の価格を送信
            price = mt5.get_price("EURUSD")
            await ws.send_text(json.dumps({"stream":"price.EURUSD","data":price}))
    except WebSocketDisconnect:
        pass 