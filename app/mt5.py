import MetaTrader5 as mt5
from app.config import settings

def init_mt5():
    if mt5.initialize(path=settings.mt5_path):
        print("[MT5] initialized")
    else:
        raise RuntimeError(f"[MT5] init failed: {mt5.last_error()}")

def shutdown_mt5():
    mt5.shutdown()
    print("[MT5] shutdown")

def place_order(req):
    """req は app.models.OrderCreate"""
    order_type = mt5.ORDER_TYPE_BUY if req.side == "BUY" else mt5.ORDER_TYPE_SELL
    ticket = mt5.order_send(
        {
            "action":      mt5.TRADE_ACTION_DEAL,
            "symbol":      req.symbol,
            "volume":      req.volume,
            "type":        order_type,
            "price":       req.price or mt5.symbol_info_tick(req.symbol).ask,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
    )
    return ticket

def get_price(symbol: str):
    tick = mt5.symbol_info_tick(symbol)
    return {"bid": tick.bid, "ask": tick.ask, "time": tick.time} 