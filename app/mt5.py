import MetaTrader5 as mt5
from app.config import settings
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple

def init_mt5():
    if mt5.initialize(path=settings.mt5_path):
        print("[MT5] initialized")
    else:
        raise RuntimeError(f"[MT5] init failed: {mt5.last_error()}")

def shutdown_mt5():
    mt5.shutdown()
    print("[MT5] shutdown")

def login(login_id: int, password: str, server: str) -> bool:
    """
    MT5アカウントにログインする
    
    Args:
        login_id: MT5ログインID
        password: MT5パスワード
        server: MT5サーバー名
        
    Returns:
        ログイン成功ならTrue、失敗ならFalse
    """
    return mt5.login(login=login_id, password=password, server=server)

def get_version() -> str:
    """MT5のバージョンを取得"""
    return mt5.version()

def get_last_error() -> dict:
    """最後のエラー情報を取得"""
    error = mt5.last_error()
    return {"code": error[0], "message": error[1]}

def get_account_info() -> dict:
    """取引口座情報を取得"""
    account_info = mt5.account_info()
    if account_info is None:
        return {}
    return {prop: getattr(account_info, prop) for prop in dir(account_info) if not prop.startswith('_')}

def get_terminal_info() -> dict:
    """MT5ターミナル情報を取得"""
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        return {}
    return {prop: getattr(terminal_info, prop) for prop in dir(terminal_info) if not prop.startswith('_')}

def get_symbols_total() -> int:
    """利用可能な金融商品の数を取得"""
    return mt5.symbols_total()

def get_symbols(group: Optional[str] = None) -> List[dict]:
    """
    金融商品のリストを取得
    
    Args:
        group: 取得するシンボルグループ（例: "*, !USD", "*,EUR", など）
        
    Returns:
        金融商品情報のリスト
    """
    symbols = mt5.symbols_get(group)
    if symbols is None:
        return []
    
    result = []
    for symbol in symbols:
        symbol_dict = {}
        for prop in dir(symbol):
            if not prop.startswith('_'):
                symbol_dict[prop] = getattr(symbol, prop)
        result.append(symbol_dict)
    
    return result

def get_symbol_info(symbol: str) -> dict:
    """
    指定した金融商品の情報を取得
    
    Args:
        symbol: 金融商品名（例: "EURUSD"）
        
    Returns:
        金融商品の詳細情報
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return {}
    
    return {prop: getattr(symbol_info, prop) for prop in dir(symbol_info) if not prop.startswith('_')}

def get_symbol_info_tick(symbol: str) -> dict:
    """
    指定した金融商品の最新価格を取得
    
    Args:
        symbol: 金融商品名（例: "EURUSD"）
        
    Returns:
        最新価格情報
    """
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {}
    
    return {
        "symbol": symbol,
        "time": tick.time,
        "bid": tick.bid,
        "ask": tick.ask,
        "last": tick.last,
        "volume": tick.volume,
        "time_msc": tick.time_msc,
        "flags": tick.flags,
        "volume_real": tick.volume_real
    }

def symbol_select(symbol: str, enable: bool = True) -> bool:
    """
    マーケットウォッチウィンドウでシンボルを選択または削除
    
    Args:
        symbol: 金融商品名
        enable: Trueで追加、Falseで削除
        
    Returns:
        操作成功ならTrue
    """
    return mt5.symbol_select(symbol, enable)

def market_book_add(symbol: str) -> bool:
    """
    指定したシンボルのMarket Depth変更イベントへの購読を開始
    
    Args:
        symbol: 金融商品名
        
    Returns:
        操作成功ならTrue
    """
    return mt5.market_book_add(symbol)

def market_book_get(symbol: str) -> List[dict]:
    """
    指定したシンボルのMarket Depth情報を取得
    
    Args:
        symbol: 金融商品名
        
    Returns:
        Market Depth情報のリスト
    """
    book = mt5.market_book_get(symbol)
    if book is None:
        return []
    
    result = []
    for item in book:
        result.append({
            "type": item.type,
            "price": item.price,
            "volume": item.volume,
            "volume_real": item.volume_real
        })
    
    return result

def market_book_release(symbol: str) -> bool:
    """
    指定したシンボルのMarket Depth変更イベントへの購読を解除
    
    Args:
        symbol: 金融商品名
        
    Returns:
        操作成功ならTrue
    """
    return mt5.market_book_release(symbol)

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

def get_candles(symbol: str, timeframe: str, count: int = 100, start_time: Optional[datetime] = None):
    """
    指定したシンボルとタイムフレームのローソク足データを取得
    
    Args:
        symbol: 通貨ペア (例: "EURUSD")
        timeframe: タイムフレーム (例: "M1", "M5", "M15", "H1", "H4", "D1")
        count: 取得するローソク足の数
        start_time: 取得開始日時 (指定がない場合は最新のデータから)
    
    Returns:
        ローソク足データのリスト
    """
    # タイムフレームの文字列をMT5の定数に変換
    tf_dict = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1
    }
    
    tf = tf_dict.get(timeframe.upper())
    if tf is None:
        raise ValueError(f"不正なタイムフレーム: {timeframe}。有効なタイムフレーム: {', '.join(tf_dict.keys())}")
    
    # ローソク足データを取得
    if start_time:
        rates = mt5.copy_rates_from(symbol, tf, start_time, count)
    else:
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    
    if rates is None or len(rates) == 0:
        return []
    
    # データをPandasデータフレームに変換
    df = pd.DataFrame(rates)
    
    # 時間をdatetime形式に変換
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # 必要なカラムのみを抽出
    result = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].to_dict('records')
    
    # datetimeオブジェクトをISO形式の文字列に変換
    for item in result:
        item['time'] = item['time'].isoformat()
    
    return result

def get_candles_range(symbol: str, timeframe: str, date_from: datetime, date_to: datetime) -> List[dict]:
    """
    指定期間のローソク足データを取得
    
    Args:
        symbol: 通貨ペア (例: "EURUSD")
        timeframe: タイムフレーム
        date_from: 開始日時
        date_to: 終了日時
    
    Returns:
        ローソク足データのリスト
    """
    # タイムフレームの文字列をMT5の定数に変換
    tf_dict = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1
    }
    
    tf = tf_dict.get(timeframe.upper())
    if tf is None:
        raise ValueError(f"不正なタイムフレーム: {timeframe}。有効なタイムフレーム: {', '.join(tf_dict.keys())}")
    
    # 指定期間のローソク足データを取得
    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
    
    if rates is None or len(rates) == 0:
        return []
    
    # データをPandasデータフレームに変換
    df = pd.DataFrame(rates)
    
    # 時間をdatetime形式に変換
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # 必要なカラムのみを抽出
    result = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].to_dict('records')
    
    # datetimeオブジェクトをISO形式の文字列に変換
    for item in result:
        item['time'] = item['time'].isoformat()
    
    return result

def get_ticks_from(symbol: str, date_from: datetime, count: int = 1000, flags: int = 0) -> List[dict]:
    """
    指定日時以降のティックデータを取得
    
    Args:
        symbol: 通貨ペア
        date_from: 開始日時
        count: 取得するティック数
        flags: フラグ (0: すべて, mt5.COPY_TICKS_INFO: Bid/Ask, mt5.COPY_TICKS_TRADE: Last/Volume)
    
    Returns:
        ティックデータのリスト
    """
    ticks = mt5.copy_ticks_from(symbol, date_from, count, flags)
    
    if ticks is None or len(ticks) == 0:
        return []
    
    # データをPandasデータフレームに変換して整形
    df = pd.DataFrame(ticks)
    
    # 結果を辞書のリストに変換
    return df.to_dict('records')

def get_ticks_range(symbol: str, date_from: datetime, date_to: datetime, flags: int = 0) -> List[dict]:
    """
    指定期間のティックデータを取得
    
    Args:
        symbol: 通貨ペア
        date_from: 開始日時
        date_to: 終了日時
        flags: フラグ (0: すべて, mt5.COPY_TICKS_INFO: Bid/Ask, mt5.COPY_TICKS_TRADE: Last/Volume)
    
    Returns:
        ティックデータのリスト
    """
    ticks = mt5.copy_ticks_range(symbol, date_from, date_to, flags)
    
    if ticks is None or len(ticks) == 0:
        return []
    
    # データをPandasデータフレームに変換して整形
    df = pd.DataFrame(ticks)
    
    # 結果を辞書のリストに変換
    return df.to_dict('records')

def get_orders_total() -> int:
    """アクティブな注文の総数を取得"""
    return mt5.orders_total()

def get_orders(symbol: Optional[str] = None, group: Optional[str] = None, ticket: Optional[int] = None) -> List[dict]:
    """
    アクティブな注文のリストを取得
    
    Args:
        symbol: 通貨ペア (Noneなら全て)
        group: 通貨ペアグループ (例: "*,!EUR")
        ticket: 注文チケット番号
    
    Returns:
        注文情報のリスト
    """
    orders = mt5.orders_get(symbol, group, ticket)
    
    if orders is None or len(orders) == 0:
        return []
    
    result = []
    for order in orders:
        order_dict = {}
        for prop in dir(order):
            if not prop.startswith('_'):
                order_dict[prop] = getattr(order, prop)
        result.append(order_dict)
    
    return result

def order_calc_margin(action: int, symbol: str, volume: float, price: float) -> float:
    """
    取引の必要証拠金を計算
    
    Args:
        action: 取引タイプ (mt5.ORDER_TYPE_BUY/mt5.ORDER_TYPE_SELL)
        symbol: 通貨ペア
        volume: 取引量
        price: 価格
    
    Returns:
        必要証拠金、エラー時は0
    """
    result = mt5.order_calc_margin(action, symbol, volume, price)
    return result if result is not None else 0.0

def order_calc_profit(action: int, symbol: str, volume: float, price_open: float, price_close: float) -> float:
    """
    取引の利益を計算
    
    Args:
        action: 取引タイプ (mt5.ORDER_TYPE_BUY/mt5.ORDER_TYPE_SELL)
        symbol: 通貨ペア
        volume: 取引量
        price_open: オープン価格
        price_close: クローズ価格
    
    Returns:
        利益、エラー時は0
    """
    result = mt5.order_calc_profit(action, symbol, volume, price_open, price_close)
    return result if result is not None else 0.0

def order_check(request: dict) -> dict:
    """
    注文をチェック
    
    Args:
        request: 注文リクエスト
    
    Returns:
        チェック結果
    """
    result = mt5.order_check(request)
    
    if result is None:
        error = mt5.last_error()
        return {"retcode": error[0], "comment": error[1]}
    
    result_dict = {}
    for prop in dir(result):
        if not prop.startswith('_'):
            if prop == 'request':
                request_dict = {}
                for req_prop in dir(result.request):
                    if not req_prop.startswith('_'):
                        request_dict[req_prop] = getattr(result.request, req_prop)
                result_dict[prop] = request_dict
            else:
                result_dict[prop] = getattr(result, prop)
    
    return result_dict

def order_send(request: dict) -> dict:
    """
    注文を送信
    
    Args:
        request: 注文リクエスト
    
    Returns:
        発注結果
    """
    result = mt5.order_send(request)
    
    if result is None:
        error = mt5.last_error()
        return {"retcode": error[0], "comment": error[1]}
    
    result_dict = {}
    for prop in dir(result):
        if not prop.startswith('_'):
            if prop == 'request':
                request_dict = {}
                for req_prop in dir(result.request):
                    if not req_prop.startswith('_'):
                        request_dict[req_prop] = getattr(result.request, req_prop)
                result_dict[prop] = request_dict
            else:
                result_dict[prop] = getattr(result, prop)
    
    return result_dict

def get_positions_total() -> int:
    """オープンポジションの総数を取得"""
    return mt5.positions_total()

def get_positions(symbol: Optional[str] = None, group: Optional[str] = None, ticket: Optional[int] = None) -> List[dict]:
    """
    オープンポジションのリストを取得
    
    Args:
        symbol: 通貨ペア (Noneなら全て)
        group: 通貨ペアグループ (例: "*,!EUR")
        ticket: ポジションチケット番号
    
    Returns:
        ポジション情報のリスト
    """
    positions = mt5.positions_get(symbol, group, ticket)
    
    if positions is None or len(positions) == 0:
        return []
    
    result = []
    for position in positions:
        position_dict = {}
        for prop in dir(position):
            if not prop.startswith('_'):
                position_dict[prop] = getattr(position, prop)
        result.append(position_dict)
    
    return result

def get_history_orders_total(date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> int:
    """履歴注文の総数を取得"""
    return mt5.history_orders_total(date_from, date_to)

def get_history_orders(date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, group: Optional[str] = None, 
                      ticket: Optional[int] = None, position: Optional[int] = None) -> List[dict]:
    """
    履歴注文のリストを取得
    
    Args:
        date_from: 開始日時
        date_to: 終了日時
        group: 通貨ペアグループ
        ticket: 注文チケット番号
        position: ポジションID
    
    Returns:
        履歴注文情報のリスト
    """
    orders = mt5.history_orders_get(date_from, date_to, group, ticket, position)
    
    if orders is None or len(orders) == 0:
        return []
    
    result = []
    for order in orders:
        order_dict = {}
        for prop in dir(order):
            if not prop.startswith('_'):
                order_dict[prop] = getattr(order, prop)
        result.append(order_dict)
    
    return result

def get_history_deals_total(date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> int:
    """取引履歴の総数を取得"""
    return mt5.history_deals_total(date_from, date_to)

def get_history_deals(date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, group: Optional[str] = None, 
                     ticket: Optional[int] = None, position: Optional[int] = None) -> List[dict]:
    """
    取引履歴のリストを取得
    
    Args:
        date_from: 開始日時
        date_to: 終了日時
        group: 通貨ペアグループ
        ticket: 取引チケット番号
        position: ポジションID
    
    Returns:
        取引履歴情報のリスト
    """
    deals = mt5.history_deals_get(date_from, date_to, group, ticket, position)
    
    if deals is None or len(deals) == 0:
        return []
    
    result = []
    for deal in deals:
        deal_dict = {}
        for prop in dir(deal):
            if not prop.startswith('_'):
                deal_dict[prop] = getattr(deal, prop)
        result.append(deal_dict)
    
    return result       

def position_close(symbol: str, ticket: Optional[int] = None) -> dict:
    """
    ポジションをクローズする
    
    Args:
        symbol: 通貨ペア
        ticket: ポジションチケット番号 (Noneの場合は指定シンボルの全ポジション)
        
    Returns:
        クローズ結果
    """
    if ticket is not None:
        position = mt5.positions_get(ticket=ticket)
        if position is None or len(position) == 0:
            return {"retcode": -1, "comment": f"ポジションが見つかりません: {ticket}"}
        
        position = position[0]
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": position.ticket,
            "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
            "deviation": 20,
            "magic": position.magic,
            "comment": f"Close position #{position.ticket}",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is None:
            error = mt5.last_error()
            return {"retcode": error[0], "comment": error[1]}
        
        result_dict = {}
        for prop in dir(result):
            if not prop.startswith('_'):
                if prop == 'request':
                    request_dict = {}
                    for req_prop in dir(result.request):
                        if not req_prop.startswith('_'):
                            request_dict[req_prop] = getattr(result.request, req_prop)
                    result_dict[prop] = request_dict
                else:
                    result_dict[prop] = getattr(result, prop)
        
        return result_dict
    else:
        positions = mt5.positions_get(symbol=symbol)
        if positions is None or len(positions) == 0:
            return {"retcode": -1, "comment": f"ポジションが見つかりません: {symbol}"}
        
        results = []
        for position in positions:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
                "deviation": 20,
                "magic": position.magic,
                "comment": f"Close position #{position.ticket}",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result is None:
                error = mt5.last_error()
                results.append({"retcode": error[0], "comment": error[1], "ticket": position.ticket})
            else:
                result_dict = {}
                for prop in dir(result):
                    if not prop.startswith('_'):
                        if prop == 'request':
                            request_dict = {}
                            for req_prop in dir(result.request):
                                if not req_prop.startswith('_'):
                                    request_dict[req_prop] = getattr(result.request, req_prop)
                            result_dict[prop] = request_dict
                        else:
                            result_dict[prop] = getattr(result, prop)
                results.append(result_dict)
        
        return {"results": results}

def position_close_partial(ticket: int, volume: float) -> dict:
    """
    ポジションを部分的にクローズする
    
    Args:
        ticket: ポジションチケット番号
        volume: クローズする量
        
    Returns:
        クローズ結果
    """
    position = mt5.positions_get(ticket=ticket)
    if position is None or len(position) == 0:
        return {"retcode": -1, "comment": f"ポジションが見つかりません: {ticket}"}
    
    position = position[0]
    
    if volume >= position.volume:
        return {"retcode": -1, "comment": f"クローズ量がポジション量以上です: {volume} >= {position.volume}"}
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "position": position.ticket,
        "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
        "deviation": 20,
        "magic": position.magic,
        "comment": f"Partial close position #{position.ticket}",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result is None:
        error = mt5.last_error()
        return {"retcode": error[0], "comment": error[1]}
    
    result_dict = {}
    for prop in dir(result):
        if not prop.startswith('_'):
            if prop == 'request':
                request_dict = {}
                for req_prop in dir(result.request):
                    if not req_prop.startswith('_'):
                        request_dict[req_prop] = getattr(result.request, req_prop)
                result_dict[prop] = request_dict
            else:
                result_dict[prop] = getattr(result, prop)
    
    return result_dict

def position_modify(ticket: int, sl: float = 0.0, tp: float = 0.0) -> dict:
    """
    ポジションのSL/TPを変更する
    
    Args:
        ticket: ポジションチケット番号
        sl: 新しいストップロス価格 (0.0で変更なし)
        tp: 新しい利益確定価格 (0.0で変更なし)
        
    Returns:
        変更結果
    """
    position = mt5.positions_get(ticket=ticket)
    if position is None or len(position) == 0:
        return {"retcode": -1, "comment": f"ポジションが見つかりません: {ticket}"}
    
    position = position[0]
    
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": position.symbol,
        "position": position.ticket,
        "sl": sl,
        "tp": tp,
    }
    
    result = mt5.order_send(request)
    if result is None:
        error = mt5.last_error()
        return {"retcode": error[0], "comment": error[1]}
    
    result_dict = {}
    for prop in dir(result):
        if not prop.startswith('_'):
            if prop == 'request':
                request_dict = {}
                for req_prop in dir(result.request):
                    if not req_prop.startswith('_'):
                        request_dict[req_prop] = getattr(result.request, req_prop)
                result_dict[prop] = request_dict
            else:
                result_dict[prop] = getattr(result, prop)
    
    return result_dict

def order_cancel(ticket: int) -> dict:
    """
    注文をキャンセルする
    
    Args:
        ticket: 注文チケット番号
        
    Returns:
        キャンセル結果
    """
    order = mt5.orders_get(ticket=ticket)
    if order is None or len(order) == 0:
        return {"retcode": -1, "comment": f"注文が見つかりません: {ticket}"}
    
    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket,
    }
    
    result = mt5.order_send(request)
    if result is None:
        error = mt5.last_error()
        return {"retcode": error[0], "comment": error[1]}
    
    result_dict = {}
    for prop in dir(result):
        if not prop.startswith('_'):
            if prop == 'request':
                request_dict = {}
                for req_prop in dir(result.request):
                    if not req_prop.startswith('_'):
                        request_dict[req_prop] = getattr(result.request, req_prop)
                result_dict[prop] = request_dict
            else:
                result_dict[prop] = getattr(result, prop)
    
    return result_dict

def order_modify(ticket: int, price: float = 0.0, sl: float = 0.0, tp: float = 0.0, expiration: int = 0) -> dict:
    """
    注文を変更する
    
    Args:
        ticket: 注文チケット番号
        price: 新しい価格 (0.0で変更なし)
        sl: 新しいストップロス価格 (0.0で変更なし)
        tp: 新しい利益確定価格 (0.0で変更なし)
        expiration: 新しい有効期限 (0で変更なし)
        
    Returns:
        変更結果
    """
    order = mt5.orders_get(ticket=ticket)
    if order is None or len(order) == 0:
        return {"retcode": -1, "comment": f"注文が見つかりません: {ticket}"}
    
    order = order[0]
    
    request = {
        "action": mt5.TRADE_ACTION_MODIFY,
        "order": ticket,
        "symbol": order.symbol,
        "price": price if price > 0.0 else order.price_open,
        "sl": sl,
        "tp": tp,
    }
    
    if expiration > 0:
        request["expiration"] = expiration
    
    result = mt5.order_send(request)
    if result is None:
        error = mt5.last_error()
        return {"retcode": error[0], "comment": error[1]}
    
    result_dict = {}
    for prop in dir(result):
        if not prop.startswith('_'):
            if prop == 'request':
                request_dict = {}
                for req_prop in dir(result.request):
                    if not req_prop.startswith('_'):
                        request_dict[req_prop] = getattr(result.request, req_prop)
                result_dict[prop] = request_dict
            else:
                result_dict[prop] = getattr(result, prop)
    
    return result_dict  