from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect
from app.config import settings
from app import mt5
from app.models import OrderCreate, OrderResponse
import asyncio
import json

router = APIRouter()

def _auth(token: str | None):
    if token != settings.bridge_token:
        raise HTTPException(status_code=401, detail="Invalid token")

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