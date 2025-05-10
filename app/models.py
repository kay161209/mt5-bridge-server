from pydantic import BaseModel, Field
from typing import Literal, List, Optional, Dict, Any
from datetime import datetime

class OrderCreate(BaseModel):
    symbol: str
    volume: float = Field(gt=0)
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    price: float | None = None        # LIMIT 時のみ

class OrderResponse(BaseModel):
    retCode: int
    result: dict | None 

class CandleRequest(BaseModel):
    symbol: str
    timeframe: Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]
    count: int = Field(gt=0, le=1000, default=100)
    start_time: Optional[datetime] = None

class CandleData(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: float
    pandas_timeframe: Optional[str] = None

class CandleResponse(BaseModel):
    data: List[CandleData]

# 追加モデル

class LoginRequest(BaseModel):
    login: int
    password: str
    server: str

class VersionResponse(BaseModel):
    version: str

class ErrorResponse(BaseModel):
    code: int
    message: str

class AccountInfoResponse(BaseModel):
    login: int
    trade_mode: int
    leverage: int
    limit_orders: int
    margin_so_mode: int
    trade_allowed: bool
    trade_expert: bool
    margin_mode: int
    currency: str
    balance: float
    credit: float
    profit: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    margin_so_call: float
    margin_so_so: float
    margin_initial: float
    margin_maintenance: float
    assets: float
    liabilities: float
    commission_blocked: float
    name: str
    server: str
    currency_digits: int
    company: str

class TerminalInfoResponse(BaseModel):
    community_account: bool
    community_connection: bool
    connected: bool
    dlls_allowed: bool
    trade_allowed: bool
    tradeapi_disabled: bool
    email_enabled: bool
    ftp_enabled: bool
    notifications_enabled: bool
    mqid: bool
    build: int
    maxbars: int
    codepage: int
    ping_last: int
    community_balance: float
    retransmission: int
    company: str
    name: str
    language: str
    path: str
    data_path: str
    commondata_path: str

class SymbolsRequest(BaseModel):
    group: Optional[str] = None

class SymbolInfoRequest(BaseModel):
    symbol: str

class SymbolInfoResponse(BaseModel):
    symbol: str
    description: str
    currency_base: str
    currency_profit: str
    currency_margin: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    tick_value_profit: float
    tick_value_loss: float
    trade_mode: int
    trade_calc_mode: int
    order_mode: int
    spread: int
    spread_float: bool
    volume_min: float
    volume_max: float
    volume_step: float
    volume_limit: float
    swap_long: float
    swap_short: float
    swap_mode: int
    margin_initial: float
    margin_maintenance: float
    option_strike: float
    option_mode: int
    option_right: int
    path: str
    session_deals: int
    session_buy_orders: int
    session_sell_orders: int
    session_volume: float
    session_open_int: float
    session_trades: int
    session_turnover: float
    session_interest: float
    session_buy_orders_volume: float
    session_sell_orders_volume: float
    session_open: float
    session_close: float
    session_aw: float
    session_price_settlement: float
    session_price_limit_min: float
    session_price_limit_max: float
    session_quotes_count: int
    bid: float
    ask: float
    last: float
    bid_high: float
    bid_low: float
    ask_high: float
    ask_low: float
    last_high: float
    last_low: float
    time: int
    change: float
    change_percent: float
    last_deal_type: int

class SymbolTickResponse(BaseModel):
    symbol: str
    time: int
    bid: float
    ask: float
    last: float
    volume: float
    time_msc: int
    flags: int
    volume_real: float

class SymbolSelectRequest(BaseModel):
    symbol: str
    enable: bool = True

class MarketBookRequest(BaseModel):
    symbol: str

class MarketBookItem(BaseModel):
    type: int  # ORDER_BOOK_TYPE_*
    price: float
    volume: float
    volume_real: float

class MarketBookResponse(BaseModel):
    items: List[MarketBookItem]

class TicksRequest(BaseModel):
    symbol: str
    date_from: datetime
    count: int = 1000
    flags: int = 0

class TicksRangeRequest(BaseModel):
    symbol: str
    date_from: datetime
    date_to: datetime
    flags: int = 0

class TickData(BaseModel):
    time: int
    bid: float
    ask: float
    last: float
    volume: int
    time_msc: int
    flags: int
    volume_real: float

class TicksResponse(BaseModel):
    ticks: List[TickData]

class OrderRequest(BaseModel):
    action: int
    symbol: str
    volume: float
    type: int
    price: float
    sl: float = 0.0
    tp: float = 0.0
    deviation: int = 10
    magic: int = 0
    comment: str = ""
    type_time: int = 0
    type_filling: int = 0
    expiration: int = 0
    position: Optional[int] = None
    position_by: Optional[int] = None

class OrderCheckResponse(BaseModel):
    retcode: int
    balance: float
    equity: float
    profit: float
    margin: float
    margin_free: float
    margin_level: float
    comment: str
    request: Dict[str, Any]

class OrderSendResponse(BaseModel):
    retcode: int
    deal: int
    order: int
    volume: float
    price: float
    bid: float
    ask: float
    comment: str
    request: Dict[str, Any]
    request_id: int
    retcode_external: int
    volume_real: float

class PositionsRequest(BaseModel):
    symbol: Optional[str] = None
    group: Optional[str] = None
    ticket: Optional[int] = None

class PositionData(BaseModel):
    ticket: int
    time: int
    time_msc: int
    time_update: int
    time_update_msc: int
    type: int
    magic: int
    identifier: int
    reason: int
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    swap: float
    profit: float
    symbol: str
    comment: str
    external_id: str

class PositionsResponse(BaseModel):
    positions: List[PositionData]

class HistoryOrdersRequest(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    group: Optional[str] = None
    ticket: Optional[int] = None
    position: Optional[int] = None

class HistoryOrderData(BaseModel):
    ticket: int
    time_setup: int
    time_setup_msc: int
    time_done: int
    time_done_msc: int
    time_expiration: int
    type: int
    type_time: int
    type_filling: int
    state: int
    magic: int
    position_id: int
    reason: int
    volume_initial: float
    volume_current: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    price_stoplimit: float
    symbol: str
    comment: str
    external_id: str

class HistoryOrdersResponse(BaseModel):
    orders: List[HistoryOrderData]

class HistoryDealsRequest(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    group: Optional[str] = None
    ticket: Optional[int] = None
    position: Optional[int] = None

class HistoryDealData(BaseModel):
    ticket: int
    order: int
    time: int
    time_msc: int
    type: int
    entry: int
    magic: int
    position_id: int
    reason: int
    volume: float
    price: float
    commission: float
    swap: float
    profit: float
    fee: float
    symbol: str
    comment: str
    external_id: str

class HistoryDealsResponse(BaseModel):
    deals: List[HistoryDealData]

class CandlesRangeRequest(BaseModel):
    symbol: str
    timeframe: Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]
    date_from: datetime
    date_to: datetime

# セッション関連モデル

class SessionCreateRequest(BaseModel):
    login: int
    password: str
    server: str

class SessionCreateResponse(BaseModel):
    session_id: str
    success: bool
    message: Optional[str] = None

class SessionResponse(BaseModel):
    id: str
    login: int
    server: str
    created_at: str
    last_accessed: str
    age_seconds: float

class SessionsListResponse(BaseModel):
    sessions: Dict[str, SessionResponse]

class PositionCloseRequest(BaseModel):
    symbol: str
    ticket: Optional[int] = None

class PositionClosePartialRequest(BaseModel):
    ticket: int
    volume: float = Field(gt=0)

class PositionModifyRequest(BaseModel):
    ticket: int
    sl: float = 0.0
    tp: float = 0.0


class OrderCancelRequest(BaseModel):
    ticket: int

class OrderModifyRequest(BaseModel):
    ticket: int
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    expiration: int = 0

