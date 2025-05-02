#!/usr/bin/env python3
import sys
import os
import json
import argparse
import platform
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
    # 初期化成功を親プロセスへ通知（フラッシュ付き）
    print(json.dumps({"type":"init","success":True,"error":None}), flush=True)

    for line in sys.stdin:
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
                    result = []
                else:
                    result = [
                        {"time": r['time'], "open": r['open'], "high": r['high'], "low": r['low'], "close": r['close'], "tick_volume": r['tick_volume']}
                        for r in rates
                    ]
                res.update({"success": True, "result": result})
            else:
                # 他のコマンドは必要に応じて拡張
                res.update({"success": False, "error": f"不明なコマンド: {cmd_type}"})
        except Exception as e:
            res.update({"success": False, "error": str(e)})
        print(json.dumps(res), flush=True)

    mt5.shutdown()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 予期せぬ例外を親プロセスへ通知
        print(json.dumps({"type":"init","success":False,"error":str(e)}), flush=True)
        sys.exit(1) 