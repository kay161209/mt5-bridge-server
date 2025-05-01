import sys
import json
import logging
import MetaTrader5 as mt5
from multiprocessing import Process, Pipe
from typing import Dict, Any, Optional
import os
import time
import psutil
from datetime import datetime

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # 標準出力へのハンドラ
    ]
)
logger = logging.getLogger(__name__)

class MT5SessionProcess:
    def __init__(self, session_id: str, mt5_path: str, connection):
        """
        MT5セッションプロセスの初期化
        
        Args:
            session_id (str): セッションID
            mt5_path (str): MT5実行ファイルのパス
            connection: プロセス間通信用のパイプ接続
        """
        self.session_id = session_id
        self.mt5_path = mt5_path
        self.mt5_dir = os.path.dirname(mt5_path)  # MT5のディレクトリパス
        self.connection = connection
        self.initialized = False
        self.logger = None
        self.setup_logger()

    def setup_logger(self):
        """セッション固有のロガーを設定"""
        try:
            self.logger = logging.getLogger(f"mt5_session_{self.session_id}")
            self.logger.setLevel(logging.INFO)
            
            # ログディレクトリを作成
            os.makedirs('logs', exist_ok=True)
            file_handler = logging.FileHandler(
                os.path.join('logs', f'mt5_session_{self.session_id}.log'),
                encoding='utf-8'
            )
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"ロガーの設定に失敗: {e}")
            raise

    def initialize_mt5(self, login: int, password: str, server: str) -> bool:
        """MT5を初期化し、ログインする"""
        try:
            self.logger.info(f"MT5の初期化を開始 - セッションID: {self.session_id}")
            self.logger.info(f"MT5パス: {self.mt5_path}")
            self.logger.info(f"MT5ディレクトリ: {self.mt5_dir}")

            # 必須ファイル(terminal64.exe)の存在確認
            if not os.path.exists(self.mt5_path):
                raise FileNotFoundError(f"必須ファイルが見つかりません: {self.mt5_path}")

            # ワーキングディレクトリをMT5実行フォルダに変更
            os.chdir(self.mt5_dir)
            self.logger.info(f"作業ディレクトリを変更: {os.getcwd()}")

            # MT5の初期化およびログインを一括実行
            self.logger.info("MT5.initialize() を login, password, server を指定して呼び出します")
            if mt5.initialize(
                path=self.mt5_path,
                login=login,
                password=password,
                server=server,
                portable=True,
                timeout=60000,
                config_path=self.mt5_dir
            ):
                self.logger.info("MT5.initialize() に成功しました (ログイン完了)")
                self.initialized = True
                return True
            else:
                code, msg = mt5.last_error()
                self.logger.error(f"MT5.initialize() に失敗: エラーコード {code}, メッセージ: {msg}")
                return False
        except Exception as e:
            self.logger.error(f"MT5の初期化中に例外が発生: {e}", exc_info=True)
            return False

    def handle_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        コマンドの処理
        
        Args:
            command (Dict[str, Any]): 実行するコマンドと引数
        
        Returns:
            Dict[str, Any]: コマンドの実行結果
        """
        cmd_type = command.get('type')
        params = command.get('params', {})
        
        try:
            if cmd_type == 'initialize':
                # MT5の初期化とログインを同時に実行
                login_val = params.get('login')
                password_val = params.get('password')
                server_val = params.get('server')
                if not self.initialize_mt5(login_val, password_val, server_val):
                    error = mt5.last_error()
                    return {'success': False, 'error': f"MT5の初期化に失敗: {error}"}
                self.initialized = True
                return {'success': True, 'error': None}
            
            if not self.initialized:
                return {'success': False, 'error': 'MT5が初期化されていません'}
            
            if cmd_type == 'order_send':
                result = mt5.order_send(**params)
                return {'success': True, 'result': result._asdict() if result else None}
            
            elif cmd_type == 'positions_get':
                result = mt5.positions_get(**params)
                return {'success': True, 'result': [pos._asdict() for pos in result] if result else []}
            
            elif cmd_type == 'symbol_select':
                # シンボルをマーケットウォッチに追加/削除
                symbol = params.get('symbol')
                enable = params.get('enable', True)
                res = mt5.symbol_select(symbol, enable)
                if res:
                    return {'success': True, 'result': None}
                else:
                    error = mt5.last_error()
                    return {'success': False, 'error': f"symbol_selectに失敗: {error}"}
            
            elif cmd_type == 'candles':
                # ローソク足データを取得
                symbol = params.get('symbol')
                timeframe = params.get('timeframe')
                count = params.get('count', 100)
                start_time = params.get('start_time')
                # タイムフレーム文字列を定数に変換
                tf_map = {
                    'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5, 'M15': mt5.TIMEFRAME_M15,
                    'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
                    'D1': mt5.TIMEFRAME_D1, 'W1': mt5.TIMEFRAME_W1, 'MN1': mt5.TIMEFRAME_MN1
                }
                tf = tf_map.get(timeframe.upper()) if timeframe else None
                if tf is None:
                    return {'success': False, 'error': f'不正なタイムフレーム: {timeframe}'}
                # データ取得
                if start_time:
                    rates = mt5.copy_rates_from(symbol, tf, start_time, count)
                else:
                    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
                if rates is None or len(rates) == 0:
                    return {'success': True, 'result': []}
                # データ整形
                result = []
                for r in rates:
                    result.append({
                        'time': datetime.fromtimestamp(r['time']).isoformat(),
                        'open': r['open'], 'high': r['high'],
                        'low': r['low'], 'close': r['close'],
                        'tick_volume': r['tick_volume']
                    })
                return {'success': True, 'result': result}
            
            return {'success': False, 'error': f'不明なコマンド: {cmd_type}'}
            
        except Exception as e:
            self.logger.error(f"コマンド実行エラー: {e}")
            return {'success': False, 'error': str(e)}

    def cleanup(self):
        """MT5接続のクリーンアップ"""
        try:
            if self.initialized:
                self.logger.info(f"MT5シャットダウン開始 - セッション: {self.session_id}")
                mt5.shutdown()
                self.initialized = False
                self.logger.info(f"MT5シャットダウン完了 - セッション: {self.session_id}")
                # ターミナルプロセスを強制終了してログファイルを解放
                for proc in psutil.process_iter(['pid', 'exe']):
                    try:
                        exe = proc.info.get('exe')
                        if exe and os.path.normcase(exe) == os.path.normcase(self.mt5_path):
                            self.logger.info(f"ターミナルプロセスを終了します: PID {proc.pid}")
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                self.logger.warning(f"ターミナルプロセス終了タイムアウト: PID {proc.pid}")
                                proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        self.logger.warning(f"プロセス操作中にエラー: {e}")
                    except Exception as e:
                        self.logger.error(f"予期せぬエラー: {e}", exc_info=True)

            # ログハンドラをクリーンアップ
            for handler in self.logger.handlers[:]:
                try:
                    handler.close()
                    self.logger.removeHandler(handler)
                except Exception as e:
                    self.logger.error(f"ログハンドラのクリーンアップ中にエラー: {e}")
            
            # 少し待機してファイルハンドルが解放されるのを待つ
            time.sleep(1)
            
        except Exception as e:
            self.logger.error(f"クリーンアップ中にエラー: {e}", exc_info=True)

    def run(self):
        """メインループ - コマンドの受信と実行"""
        try:
            while True:
                if self.connection.poll(timeout=1.0):  # タイムアウト付きで待機
                    command = self.connection.recv()
                    
                    if command.get('type') == 'terminate':
                        break
                    
                    result = self.handle_command(command)
                    self.connection.send(result)
                
        except EOFError:
            self.logger.info("親プロセスとの接続が閉じられました")
        except Exception as e:
            self.logger.error(f"予期せぬエラー: {e}")
        finally:
            self.cleanup()
            self.logger.info("MT5セッションプロセスを終了します")

def start_session_process(session_id: str, mt5_path: str, connection):
    """
    セッションプロセスのエントリーポイント
    
    Args:
        session_id (str): セッションID
        mt5_path (str): MT5実行ファイルのパス
        connection: プロセス間通信用のパイプ接続
    """
    process = MT5SessionProcess(session_id, mt5_path, connection)
    process.run()

if __name__ == '__main__':
    # このスクリプトが直接実行された場合（子プロセスとして）
    if len(sys.argv) < 3:
        print("Usage: python mt5_session_process.py <session_id> <mt5_path>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    mt5_path = sys.argv[2]
    parent_conn, child_conn = Pipe()
    
    start_session_process(session_id, mt5_path, child_conn) 