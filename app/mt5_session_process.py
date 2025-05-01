import sys
import json
import logging
import MetaTrader5 as mt5
from multiprocessing import Process, Pipe
from typing import Dict, Any, Optional

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/mt5_session_{id}.log'),
        logging.StreamHandler()
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
        self.connection = connection
        self.initialized = False

    def initialize_mt5(self) -> bool:
        """MT5の初期化"""
        try:
            if not mt5.initialize(path=self.mt5_path):
                logger.error(f"MT5初期化エラー: {mt5.last_error()}")
                return False
            self.initialized = True
            logger.info(f"MT5初期化成功 - セッション: {self.session_id}")
            return True
        except Exception as e:
            logger.error(f"MT5初期化中の例外: {e}")
            return False

    def cleanup(self):
        """MT5接続のクリーンアップ"""
        if self.initialized:
            mt5.shutdown()
            self.initialized = False
            logger.info(f"MT5シャットダウン完了 - セッション: {self.session_id}")

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
                success = self.initialize_mt5()
                return {'success': success, 'error': None if success else str(mt5.last_error())}
            
            if not self.initialized:
                return {'success': False, 'error': 'MT5が初期化されていません'}
            
            if cmd_type == 'order_send':
                result = mt5.order_send(**params)
                return {'success': True, 'result': result._asdict() if result else None}
            
            elif cmd_type == 'positions_get':
                result = mt5.positions_get(**params)
                return {'success': True, 'result': [pos._asdict() for pos in result] if result else []}
            
            # 他のMT5コマンドも同様に実装
            
            return {'success': False, 'error': f'不明なコマンド: {cmd_type}'}
            
        except Exception as e:
            logger.error(f"コマンド実行エラー: {e}")
            return {'success': False, 'error': str(e)}

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
            logger.info("親プロセスとの接続が閉じられました")
        except Exception as e:
            logger.error(f"予期せぬエラー: {e}")
        finally:
            self.cleanup()
            logger.info("MT5セッションプロセスを終了します")

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