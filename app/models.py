from pydantic import BaseModel, Field
from typing import Literal

class OrderCreate(BaseModel):
    symbol: str
    volume: float = Field(gt=0)
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    price: float | None = None        # LIMIT 時のみ

class OrderResponse(BaseModel):
    retCode: int
    result: dict | None 