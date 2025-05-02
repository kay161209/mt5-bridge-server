#!/usr/bin/env python3
import sys
import os
import json
import argparse
import platform
import socket
import io
# MT5 モジュールのインポートを安全に行う
try:
    import MetaTrader5 as mt5
except Exception as e:
    # インポートに失敗したら親プロセスへエラーを通知して終了
    print(json.dumps({"type":"init","success":False,"error":f"MetaTrader5 import error: {e}"}), flush=True)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--login", type=int, required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--server", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--exe-path", required=True)
    parser.add_argument("--ipc-port", type=int, required=False)
    args = parser.parse_args()

    # macOS/Linux では WINEPREFIX をセッション固有ディレクトリに設定
    if platform.system() != 'Windows':
        os.environ['WINEPREFIX'] = args.data_dir
        os.environ['WINEARCH'] = 'win64'

    terminal_exe = args.exe_path
    config_path = args.data_dir
    # MT5.initialize() にタイムアウト(60000ms=60秒)を指定して無限待ちを防止
    ok = mt5.initialize(
        path=terminal_exe,
        login=args.login, password=args.password, server=args.server,
        portable=True, timeout=60000, config_path=config_path
    )
    if not ok:
        err = mt5.last_error()
        # 初期化失敗を親プロセスへ通知（フラッシュ付き）
        print(json.dumps({"type":"init","success":False,"error":err}), flush=True)
        sys.exit(1)
    # 初期化成功を親プロセスへ通知
    init_msg = {"type":"init","success":True,"error":None}
    # Windows環境でMetaTraderのウィンドウを非表示化
    if platform.system() == "Windows":
        try:
            # 初期化済みのターミナルプロセスIDを取得
            term_info = mt5.terminal_info()
            pid = term_info.pid
            import ctypes
            # 定数・API定義
            SW_HIDE = 0
            EnumWindows = ctypes.windll.user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
            ShowWindow = ctypes.windll.user32.ShowWindow
            # コールバックでウィンドウハンドルを隠す
            def _hide(hwnd, lParam):
                pid_buf = ctypes.c_ulong()
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid_buf))
                if pid_buf.value == pid:
                    ShowWindow(hwnd, SW_HIDE)
                return True
            EnumWindows(EnumWindowsProc(_hide), 0)
        except Exception:
            pass
    if args.ipc_port:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", args.ipc_port))
        in_stream = sock.makefile('r', encoding='utf-8')
        out_stream = sock.makefile('w', encoding='utf-8')
        out_stream.write(json.dumps(init_msg) + "\n")
        out_stream.flush()
    else:
        sys.stdout.write(json.dumps(init_msg) + "\n")
        sys.stdout.flush()
    # 入出力ストリームの選択
    if not args.ipc_port:
        in_stream = sys.stdin
        out_stream = sys.stdout

    for line in in_stream:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        if req.get("type") == "terminate":
            break
        cmd_type = req.get("type")
        params = req.get("params", {})
        res = {"type": cmd_type}
        try:
            if cmd_type == "candles":
                symbol = params.get("symbol")
                timeframe = params.get("timeframe")
                tf = getattr(mt5, "TIMEFRAME_" + timeframe.upper()) if timeframe else None
                count = params.get("count", 100)
                start_time = params.get("start_time")
                if start_time:
                    rates = mt5.copy_rates_from(symbol, tf, start_time, count)
                else:
                    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
                if rates is None or len(rates) == 0:
                    result_list = []
                else:
                    result_list = [
                        {"time": r['time'], "open": r['open'], "high": r['high'], "low": r['low'], "close": r['close'], "tick_volume": r['tick_volume']}
                        for r in rates
                    ]
                res.update({"success": True, "result": result_list})
            elif cmd_type == "order_send":
                result = mt5.order_send(**params)
                if result is None:
                    error = mt5.last_error()
                    res.update({"success": False, "error": f"order_sendに失敗: {error}"})
                else:
                    res.update({"success": True, "result": result._asdict()})
            elif cmd_type == "quote":
                tick = mt5.symbol_info_tick(params.get("symbol"))
                if tick is None:
                    error = mt5.last_error()
                    res.update({"success": False, "error": f"quoteに失敗: {error}"})
                else:
                    res.update({"success": True, "result": {"bid": tick.bid, "ask": tick.ask, "time": tick.time}})
            elif cmd_type == "positions_get":
                result = mt5.positions_get(**params)
                positions_list = [pos._asdict() for pos in result] if result else []
                res.update({"success": True, "result": positions_list})
            elif cmd_type == "symbol_select":
                symbol = params.get("symbol")
                enable = params.get("enable", True)
                ok = mt5.symbol_select(symbol, enable)
                if ok:
                    res.update({"success": True, "result": None})
                else:
                    error = mt5.last_error()
                    res.update({"success": False, "error": f"symbol_selectに失敗: {error}"})
            else:
                res.update({"success": False, "error": f"不明なコマンド: {cmd_type}"})
        except Exception as e:
            res.update({"success": False, "error": str(e)})
        out_stream.write(json.dumps(res) + "\n")
        out_stream.flush()

    mt5.shutdown()
    # Windows環境: MetaTrader ターミナルプロセスを終了
    if platform.system() == "Windows":
        try:
            # プロセスIDを取得・kill
            term_info = mt5.terminal_info()
            pid = term_info.pid
            import psutil
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 予期せぬ例外を親プロセスへ通知
        err_msg = {"type":"init","success":False,"error":str(e)}
        try:
            out_stream.write(json.dumps(err_msg) + "\n")
            out_stream.flush()
        except:
            sys.stdout.write(json.dumps(err_msg) + "\n")
            sys.stdout.flush()
        sys.exit(1) 