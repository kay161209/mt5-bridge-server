# MT5 Bridge API Endpoint Samples

This document provides sample requests and responses for all session-based endpoints in the MT5 Bridge API.

## Session Management

### Create Session

**Request:**
```http
POST /session/create
Content-Type: application/json
X-API-Token: your_api_token

{
  "mt5_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
  "login": 12345678,
  "password": "your_password",
  "server": "MetaQuotes-Demo"
}
```

**Response:**
```json
{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "created_at": "2023-01-01T12:00:00Z"
}
```

### Execute Command

**Request:**
```http
POST /session/{session_id}/command
Content-Type: application/json
X-API-Token: your_api_token

{
  "type": "symbol_select",
  "params": {
    "symbol": "EURUSD",
    "enable": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "result": true
}
```

## Market Data Operations

### Quote

**Request:**
```http
POST /public/quote
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbols": ["EURUSD", "USDJPY"]
}
```

**Response:**
```json
{
  "quotes": [
    {
      "symbol": "EURUSD",
      "bid": 1.10325,
      "ask": 1.10327,
      "time": 1672567200,
      "time_msc": 1672567200123,
      "last": 1.10326,
      "volume": 100
    },
    {
      "symbol": "USDJPY",
      "bid": 130.45,
      "ask": 130.47,
      "time": 1672567200,
      "time_msc": 1672567200456,
      "last": 130.46,
      "volume": 50
    }
  ]
}
```

### Candles

**Request:**
```http
POST /public/candles
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "timeframe": "M5",
  "count": 10
}
```

**Response:**
```json
{
  "candles": [
    {
      "time": 1672567200,
      "open": 1.10320,
      "high": 1.10350,
      "low": 1.10310,
      "close": 1.10330,
      "tick_volume": 1250,
      "spread": 2,
      "real_volume": 1250000
    },
    {
      "time": 1672567500,
      "open": 1.10330,
      "high": 1.10360,
      "low": 1.10320,
      "close": 1.10340,
      "tick_volume": 1300,
      "spread": 2,
      "real_volume": 1300000
    }
    // ... more candles
  ]
}
```

### Candles Range

**Request:**
```http
POST /public/candles_range
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "timeframe": "M5",
  "date_from": "2023-01-01T12:00:00Z",
  "date_to": "2023-01-01T13:00:00Z"
}
```

**Response:**
```json
{
  "candles": [
    {
      "time": 1672567200,
      "open": 1.10320,
      "high": 1.10350,
      "low": 1.10310,
      "close": 1.10330,
      "tick_volume": 1250,
      "spread": 2,
      "real_volume": 1250000
    },
    // ... more candles
  ]
}
```

### Ticks From

**Request:**
```http
POST /public/ticks_from
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "date_from": "2023-01-01T12:00:00Z",
  "count": 100
}
```

**Response:**
```json
{
  "ticks": [
    {
      "time": 1672567200,
      "bid": 1.10325,
      "ask": 1.10327,
      "last": 1.10326,
      "volume": 1,
      "time_msc": 1672567200123,
      "flags": 2,
      "volume_real": 1.0
    },
    // ... more ticks
  ]
}
```

### Ticks Range

**Request:**
```http
POST /public/ticks_range
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "date_from": "2023-01-01T12:00:00Z",
  "date_to": "2023-01-01T12:01:00Z"
}
```

**Response:**
```json
{
  "ticks": [
    {
      "time": 1672567200,
      "bid": 1.10325,
      "ask": 1.10327,
      "last": 1.10326,
      "volume": 1,
      "time_msc": 1672567200123,
      "flags": 2,
      "volume_real": 1.0
    },
    // ... more ticks
  ]
}
```

### Symbols

**Request:**
```http
POST /public/symbols
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0"
}
```

**Response:**
```json
{
  "symbols": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF"]
}
```

### Symbol Info

**Request:**
```http
POST /public/symbol_info
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD"
}
```

**Response:**
```json
{
  "info": {
    "name": "EURUSD",
    "base_currency": "EUR",
    "profit_currency": "USD",
    "digits": 5,
    "spread": 2,
    "trade_mode": 0,
    "tick_value": 1.0,
    "tick_size": 0.00001,
    "contract_size": 100000.0,
    "volume_min": 0.01,
    "volume_max": 500.0,
    "volume_step": 0.01,
    "swap_long": -1.1,
    "swap_short": -0.9,
    "swap_mode": 1
  }
}
```

### Symbol Info Tick

**Request:**
```http
POST /public/symbol_info_tick
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD"
}
```

**Response:**
```json
{
  "tick": {
    "time": 1672567200,
    "bid": 1.10325,
    "ask": 1.10327,
    "last": 1.10326,
    "volume": 1,
    "time_msc": 1672567200123,
    "flags": 2,
    "volume_real": 1.0
  }
}
```

### Market Book Get

**Request:**
```http
POST /public/market_book_get
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD"
}
```

**Response:**
```json
{
  "book": [
    {
      "type": 1,
      "price": 1.10327,
      "volume": 1.5,
      "volume_real": 1.5
    },
    {
      "type": 1,
      "price": 1.10328,
      "volume": 2.3,
      "volume_real": 2.3
    },
    {
      "type": 2,
      "price": 1.10325,
      "volume": 1.2,
      "volume_real": 1.2
    },
    {
      "type": 2,
      "price": 1.10324,
      "volume": 3.1,
      "volume_real": 3.1
    }
  ]
}
```

## Trading Operations

### Order Create

**Request:**
```http
POST /private/order/create
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "type": "ORDER_TYPE_BUY",
  "volume": 0.1,
  "price": 1.10350,
  "sl": 1.10250,
  "tp": 1.10450,
  "comment": "Buy order"
}
```

**Response:**
```json
{
  "retcode": 10009,
  "deal": 12345678,
  "order": 87654321,
  "volume": 0.1,
  "price": 1.10350,
  "bid": 1.10325,
  "ask": 1.10327,
  "comment": "Buy order",
  "request_id": 1,
  "retcode_external": 0,
  "message": "Order executed"
}
```

### Order Cancel

**Request:**
```http
POST /private/order/cancel
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "ticket": 87654321
}
```

**Response:**
```json
{
  "retcode": 10009,
  "deal": 0,
  "order": 0,
  "volume": 0.0,
  "price": 0.0,
  "bid": 1.10325,
  "ask": 1.10327,
  "comment": "",
  "request_id": 2,
  "retcode_external": 0,
  "message": "Order canceled"
}
```

### Order Modify

**Request:**
```http
POST /private/order/modify
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "ticket": 87654321,
  "price": 1.10360,
  "sl": 1.10260,
  "tp": 1.10460,
  "expiration": "2023-01-02T12:00:00Z"
}
```

**Response:**
```json
{
  "retcode": 10009,
  "deal": 0,
  "order": 87654321,
  "volume": 0.1,
  "price": 1.10360,
  "bid": 1.10325,
  "ask": 1.10327,
  "comment": "",
  "request_id": 3,
  "retcode_external": 0,
  "message": "Order modified"
}
```

### Order Check

**Request:**
```http
POST /private/order/check
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "type": "ORDER_TYPE_BUY",
  "volume": 0.1,
  "price": 1.10350
}
```

**Response:**
```json
{
  "retcode": 0,
  "balance": 10000.0,
  "equity": 10000.0,
  "profit": 0.0,
  "margin": 33.11,
  "margin_free": 9966.89,
  "margin_level": 30203.56,
  "comment": "",
  "request_id": 4,
  "retcode_external": 0,
  "message": "Order check passed"
}
```

### Order Send

**Request:**
```http
POST /private/order/send
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "action": 1,
  "symbol": "EURUSD",
  "volume": 0.1,
  "type": 0,
  "price": 1.10350,
  "sl": 1.10250,
  "tp": 1.10450,
  "deviation": 10,
  "magic": 123456,
  "comment": "Buy order",
  "type_time": 0,
  "expiration": 0
}
```

**Response:**
```json
{
  "retcode": 10009,
  "deal": 12345678,
  "order": 87654321,
  "volume": 0.1,
  "price": 1.10350,
  "bid": 1.10325,
  "ask": 1.10327,
  "comment": "Buy order",
  "request_id": 5,
  "retcode_external": 0,
  "message": "Order executed"
}
```

### Position Close

**Request:**
```http
POST /private/position/close
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "ticket": 12345678
}
```

**Response:**
```json
{
  "retcode": 10009,
  "deal": 87654322,
  "order": 87654323,
  "volume": 0.1,
  "price": 1.10327,
  "bid": 1.10325,
  "ask": 1.10327,
  "comment": "",
  "request_id": 6,
  "retcode_external": 0,
  "message": "Position closed"
}
```

### Position Close Partial

**Request:**
```http
POST /private/position/close_partial
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "ticket": 12345678,
  "volume": 0.05
}
```

**Response:**
```json
{
  "retcode": 10009,
  "deal": 87654324,
  "order": 87654325,
  "volume": 0.05,
  "price": 1.10327,
  "bid": 1.10325,
  "ask": 1.10327,
  "comment": "",
  "request_id": 7,
  "retcode_external": 0,
  "message": "Position partially closed"
}
```

### Position Modify

**Request:**
```http
POST /private/position/modify
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "ticket": 12345678,
  "sl": 1.10260,
  "tp": 1.10460
}
```

**Response:**
```json
{
  "retcode": 10009,
  "deal": 0,
  "order": 0,
  "volume": 0.0,
  "price": 0.0,
  "bid": 1.10325,
  "ask": 1.10327,
  "comment": "",
  "request_id": 8,
  "retcode_external": 0,
  "message": "Position modified"
}
```

## Account Information

### Account Info

**Request:**
```http
POST /private/account_info
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0"
}
```

**Response:**
```json
{
  "login": 12345678,
  "trade_mode": 0,
  "leverage": 100,
  "limit_orders": 500,
  "margin_so_mode": 0,
  "trade_allowed": true,
  "trade_expert": true,
  "margin_mode": 0,
  "currency_digits": 2,
  "balance": 10000.0,
  "credit": 0.0,
  "profit": 0.0,
  "equity": 10000.0,
  "margin": 0.0,
  "margin_free": 10000.0,
  "margin_level": 0.0,
  "margin_so_call": 50.0,
  "margin_so_so": 30.0,
  "margin_initial": 0.0,
  "margin_maintenance": 0.0,
  "assets": 0.0,
  "liabilities": 0.0,
  "commission_blocked": 0.0,
  "name": "John Doe",
  "server": "MetaQuotes-Demo",
  "currency": "USD",
  "company": "MetaQuotes Software Corp."
}
```

### Terminal Info

**Request:**
```http
POST /public/terminal_info
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0"
}
```

**Response:**
```json
{
  "community_account": false,
  "community_connection": false,
  "connected": true,
  "dlls_allowed": true,
  "trade_allowed": true,
  "tradeapi_disabled": false,
  "email_enabled": false,
  "ftp_enabled": false,
  "notifications_enabled": false,
  "mqid": false,
  "build": 2755,
  "maxbars": 100000,
  "codepage": 1252,
  "ping_last": 45,
  "community_balance": 0.0,
  "retransmission": 0.0,
  "company": "MetaQuotes Software Corp.",
  "name": "MetaTrader 5",
  "language": "English",
  "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
  "data_path": "C:\\Users\\User\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common",
  "commondata_path": "C:\\Users\\User\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common"
}
```

### Positions Total

**Request:**
```http
POST /private/positions_total
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0"
}
```

**Response:**
```json
{
  "total": 2
}
```

### Positions

**Request:**
```http
POST /private/positions
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "group": "forex"
}
```

**Response:**
```json
{
  "positions": [
    {
      "ticket": 12345678,
      "time": 1672567200,
      "time_msc": 1672567200123,
      "time_update": 1672567300,
      "time_update_msc": 1672567300456,
      "type": 0,
      "magic": 123456,
      "identifier": 12345678,
      "reason": 0,
      "volume": 0.1,
      "price_open": 1.10350,
      "sl": 1.10250,
      "tp": 1.10450,
      "price_current": 1.10327,
      "swap": -0.12,
      "profit": -2.3,
      "symbol": "EURUSD",
      "comment": "Buy position"
    },
    {
      "ticket": 12345679,
      "time": 1672567400,
      "time_msc": 1672567400789,
      "time_update": 1672567500,
      "time_update_msc": 1672567500123,
      "type": 1,
      "magic": 123456,
      "identifier": 12345679,
      "reason": 0,
      "volume": 0.2,
      "price_open": 1.10330,
      "sl": 1.10430,
      "tp": 1.10230,
      "price_current": 1.10327,
      "swap": -0.24,
      "profit": 0.6,
      "symbol": "EURUSD",
      "comment": "Sell position"
    }
  ]
}
```

### Orders Total

**Request:**
```http
POST /private/orders_total
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0"
}
```

**Response:**
```json
{
  "total": 3
}
```

### Orders

**Request:**
```http
POST /private/orders
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "symbol": "EURUSD",
  "group": "forex"
}
```

**Response:**
```json
{
  "orders": [
    {
      "ticket": 87654321,
      "time_setup": 1672567600,
      "time_setup_msc": 1672567600123,
      "time_expiration": 1672654000,
      "type": 2,
      "type_time": 1,
      "type_filling": 1,
      "state": 1,
      "magic": 123456,
      "position_id": 0,
      "position_by_id": 0,
      "volume_initial": 0.1,
      "volume_current": 0.1,
      "price_open": 1.10400,
      "sl": 1.10300,
      "tp": 1.10500,
      "price_current": 1.10327,
      "price_stoplimit": 0.0,
      "symbol": "EURUSD",
      "comment": "Limit buy order"
    },
    {
      "ticket": 87654322,
      "time_setup": 1672567700,
      "time_setup_msc": 1672567700456,
      "time_expiration": 1672654000,
      "type": 3,
      "type_time": 1,
      "type_filling": 1,
      "state": 1,
      "magic": 123456,
      "position_id": 0,
      "position_by_id": 0,
      "volume_initial": 0.2,
      "volume_current": 0.2,
      "price_open": 1.10250,
      "sl": 1.10350,
      "tp": 1.10150,
      "price_current": 1.10327,
      "price_stoplimit": 0.0,
      "symbol": "EURUSD",
      "comment": "Limit sell order"
    }
  ]
}
```

### History Orders Total

**Request:**
```http
POST /private/history_orders_total
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "date_from": "2023-01-01T00:00:00Z",
  "date_to": "2023-01-02T00:00:00Z"
}
```

**Response:**
```json
{
  "total": 5
}
```

### History Orders

**Request:**
```http
POST /private/history_orders
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "date_from": "2023-01-01T00:00:00Z",
  "date_to": "2023-01-02T00:00:00Z",
  "group": "forex"
}
```

**Response:**
```json
{
  "orders": [
    {
      "ticket": 87654320,
      "time_setup": 1672531200,
      "time_setup_msc": 1672531200123,
      "time_expiration": 0,
      "type": 0,
      "type_time": 0,
      "type_filling": 1,
      "state": 3,
      "magic": 123456,
      "position_id": 12345677,
      "position_by_id": 0,
      "volume_initial": 0.1,
      "volume_current": 0.1,
      "price_open": 1.10320,
      "sl": 1.10220,
      "tp": 1.10420,
      "price_current": 1.10320,
      "price_stoplimit": 0.0,
      "symbol": "EURUSD",
      "comment": "Market buy order",
      "external_id": ""
    },
    {
      "ticket": 87654319,
      "time_setup": 1672534800,
      "time_setup_msc": 1672534800456,
      "time_expiration": 0,
      "type": 1,
      "type_time": 0,
      "type_filling": 1,
      "state": 3,
      "magic": 123456,
      "position_id": 12345676,
      "position_by_id": 0,
      "volume_initial": 0.2,
      "volume_current": 0.2,
      "price_open": 1.10340,
      "sl": 1.10440,
      "tp": 1.10240,
      "price_current": 1.10340,
      "price_stoplimit": 0.0,
      "symbol": "EURUSD",
      "comment": "Market sell order",
      "external_id": ""
    }
  ]
}
```

### History Deals Total

**Request:**
```http
POST /private/history_deals_total
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "date_from": "2023-01-01T00:00:00Z",
  "date_to": "2023-01-02T00:00:00Z"
}
```

**Response:**
```json
{
  "total": 8
}
```

### History Deals

**Request:**
```http
POST /private/history_deals
Content-Type: application/json
X-API-Token: your_api_token

{
  "session_id": "a1b2c3d4e5f6g7h8i9j0",
  "date_from": "2023-01-01T00:00:00Z",
  "date_to": "2023-01-02T00:00:00Z",
  "group": "forex"
}
```

**Response:**
```json
{
  "deals": [
    {
      "ticket": 98765432,
      "order": 87654320,
      "time": 1672531200,
      "time_msc": 1672531200123,
      "type": 0,
      "entry": 0,
      "magic": 123456,
      "position_id": 12345677,
      "volume": 0.1,
      "price": 1.10320,
      "commission": -0.7,
      "swap": 0.0,
      "profit": 0.0,
      "fee": 0.0,
      "symbol": "EURUSD",
      "comment": "Market buy deal",
      "external_id": ""
    },
    {
      "ticket": 98765431,
      "order": 87654319,
      "time": 1672534800,
      "time_msc": 1672534800456,
      "type": 1,
      "entry": 0,
      "magic": 123456,
      "position_id": 12345676,
      "volume": 0.2,
      "price": 1.10340,
      "commission": -1.4,
      "swap": 0.0,
      "profit": 0.0,
      "fee": 0.0,
      "symbol": "EURUSD",
      "comment": "Market sell deal",
      "external_id": ""
    },
    {
      "ticket": 98765430,
      "order": 87654318,
      "time": 1672538400,
      "time_msc": 1672538400789,
      "type": 1,
      "entry": 1,
      "magic": 123456,
      "position_id": 12345677,
      "volume": 0.1,
      "price": 1.10360,
      "commission": -0.7,
      "swap": -0.12,
      "profit": 4.0,
      "fee": 0.0,
      "symbol": "EURUSD",
      "comment": "Close buy position",
      "external_id": ""
    }
  ]
}
```

## WebSocket Interface

### WebSocket Connection

Connect to:
```
ws://localhost:8000/v5/ws/{session_id}?token=your_api_token
```

### WebSocket Commands

**Send Command:**
```json
{
  "type": "quote",
  "params": {
    "symbols": ["EURUSD", "USDJPY"]
  }
}
```

**Receive Response:**
```json
{
  "success": true,
  "result": [
    {
      "symbol": "EURUSD",
      "bid": 1.10325,
      "ask": 1.10327,
      "time": 1672567200,
      "time_msc": 1672567200123,
      "last": 1.10326,
      "volume": 100
    },
    {
      "symbol": "USDJPY",
      "bid": 130.45,
      "ask": 130.47,
      "time": 1672567200,
      "time_msc": 1672567200456,
      "last": 130.46,
      "volume": 50
    }
  ]
}
```
