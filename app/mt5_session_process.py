import sys
import json
import logging
import MetaTrader5 as mt5
from multiprocessing import Process, Pipe
from typing import Dict, Any, Optional
import os
import time
import psutil

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

    def initialize_mt5(self) -> bool:
        """MT5を初期化する"""
        try:
            self.logger.info(f"MT5の初期化を開始 - セッションID: {self.session_id}")
            self.logger.info(f"MT5パス: {self.mt5_path}")
            self.logger.info(f"MT5ディレクトリ: {self.mt5_dir}")

            # 必須ファイル(terminal64.exe)の存在確認
            if not os.path.exists(self.mt5_path):
                raise FileNotFoundError(f"必須ファイルが見つかりません: {self.mt5_path}")

            # プロセス情報とワーキングディレクトリの設定
            self.logger.info(f"プロセスID: {os.getpid()}")
            self.logger.info(f"実行パス: {os.getcwd()}")
            self.logger.info(f"作業ディレクトリ: {self.mt5_dir}")
            # ワーキングディレクトリをMT5実行フォルダに変更
            os.chdir(self.mt5_dir)

            # 既存のMT5プロセスをチェックして終了
            mt5_processes = [p for p in psutil.process_iter(['name', 'pid', 'cmdline']) 
                            if p.info['name'] and 'terminal64' in p.info['name'].lower()]
            
            if mt5_processes:
                self.logger.info(f"既存のMT5プロセスを確認中: {len(mt5_processes)}個")
                for proc in mt5_processes:
                    try:
                        # プロセスの詳細情報を取得
                        proc_info = proc.as_dict(attrs=['pid', 'name', 'cmdline', 'create_time'])
                        self.logger.info(f"既存のプロセス情報:")
                        self.logger.info(f"  - PID: {proc_info['pid']}")
                        self.logger.info(f"  - 名前: {proc_info['name']}")
                        self.logger.info(f"  - コマンドライン: {proc_info.get('cmdline', ['不明'])}")
                        
                        # プロセスを終了
                        self.logger.info(f"MT5プロセスを終了します: PID {proc_info['pid']}")
                        proc.terminate()
                        
                        # 終了を待機（最大10秒）
                        try:
                            proc.wait(timeout=10)
                            self.logger.info(f"プロセスが正常に終了しました: PID {proc_info['pid']}")
                        except psutil.TimeoutExpired:
                            self.logger.warning(f"プロセスの終了待機がタイムアウト。強制終了を試みます: PID {proc_info['pid']}")
                            proc.kill()
                            proc.wait(timeout=5)  # 強制終了の完了を待機
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        self.logger.warning(f"プロセス操作中にエラー: {e}")
                    except Exception as e:
                        self.logger.error(f"予期せぬエラー: {e}", exc_info=True)

            # 少し待機してプロセスが完全に終了するのを待つ
            self.logger.info("既存プロセスの終了を待機中...")
            time.sleep(3)

            # 再度プロセスをチェック
            remaining_processes = [p for p in psutil.process_iter(['name']) 
                                if p.info['name'] and 'terminal64' in p.info['name'].lower()]
            if remaining_processes:
                self.logger.warning(f"まだ {len(remaining_processes)} 個のMT5プロセスが実行中です")
                for proc in remaining_processes:
                    self.logger.warning(f"残存プロセス - PID: {proc.pid}")

            # MT5の初期化を試行
            self.logger.info("MT5の初期化を開始します...")
            if mt5.initialize(
                path=self.mt5_path,
                portable=True,
                timeout=60000,
                config_path=self.mt5_dir
            ):
                self.logger.info("MT5の初期化に成功しました")
                terminal_info = mt5.terminal_info()
                self.logger.info(f"ターミナル情報: {terminal_info}")
                return True
            else:
                error = mt5.last_error()
                code, msg = error
                self.logger.error(f"MT5の初期化に失敗: エラーコード {code}, メッセージ: {msg}")
                return False

        except Exception as e:
            self.logger.error(f"MT5の初期化中に例外が発生: {str(e)}", exc_info=True)
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
                # まずMT5を初期化
                if not self.initialize_mt5():
                    return {'success': False, 'error': f"MT5の初期化に失敗: {mt5.last_error()}"}
                
                # 次にログイン
                if not mt5.login(
                    login=params.get('login'),
                    password=params.get('password'),
                    server=params.get('server')
                ):
                    error = mt5.last_error()
                    self.logger.error(f"MT5ログインエラー: {error}")
                    return {'success': False, 'error': f"ログインに失敗: {error}"}
                
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