import sys
import json
import logging
import MetaTrader5 as mt5
from multiprocessing import Process, Pipe
from typing import Dict, Any, Optional
import os
import time

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
        
        # セッション固有のファイルハンドラを追加
        try:
            os.makedirs('logs', exist_ok=True)
            file_handler = logging.FileHandler(
                os.path.join('logs', f'mt5_session_{self.session_id}.log'),
                encoding='utf-8'
            )
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"ログファイルハンドラの設定に失敗: {e}")

    def initialize_mt5(self) -> bool:
        """MT5の初期化（ポータブルモード）"""
        try:
            logger.info(f"MT5初期化開始 - セッション: {self.session_id}")
            logger.info(f"MT5パス: {self.mt5_path}")
            logger.info(f"MT5ディレクトリ: {self.mt5_dir}")
            
            # ディレクトリ構造の確認
            required_dirs = ['Config', 'MQL5', 'MQL5/Data']
            for dir_path in required_dirs:
                full_path = os.path.join(self.mt5_dir, dir_path)
                exists = os.path.exists(full_path)
                logger.info(f"ディレクトリチェック {dir_path}: {'存在します' if exists else '存在しません'}")
                if not exists:
                    logger.error(f"必要なディレクトリが見つかりません: {full_path}")
                    return False

            # ポータブルモードのための環境変数を設定
            os.environ["MT5_PORTABLE_MODE"] = "1"
            data_path = os.path.join(self.mt5_dir, "MQL5", "Data")
            config_path = os.path.join(self.mt5_dir, "Config")
            os.environ["MT5_DATA_PATH"] = data_path
            os.environ["MT5_CONFIG_PATH"] = config_path
            
            logger.info(f"環境変数設定:")
            logger.info(f"MT5_PORTABLE_MODE: {os.environ.get('MT5_PORTABLE_MODE')}")
            logger.info(f"MT5_DATA_PATH: {os.environ.get('MT5_DATA_PATH')}")
            logger.info(f"MT5_CONFIG_PATH: {os.environ.get('MT5_CONFIG_PATH')}")
            
            # MT5の初期化（ポータブルモード）
            init_params = {
                "path": self.mt5_path,
                "portable": True,  # ポータブルモードを有効化
                "timeout": 30000,  # タイムアウトを30秒に設定
            }
            
            logger.info(f"MT5初期化パラメータ: {init_params}")
            
            if not mt5.initialize(**init_params):
                error = mt5.last_error()
                error_code, error_msg = error if isinstance(error, tuple) else (0, str(error))
                logger.error(f"MT5初期化エラー: [{error_code}] {error_msg}")
                return False
                
            self.initialized = True
            logger.info(f"MT5初期化成功（ポータブルモード） - セッション: {self.session_id}")
            
            # 初期化後の状態確認
            terminal_info = mt5.terminal_info()
            if terminal_info is not None:
                logger.info("ターミナル情報:")
                logger.info(f"  接続状態: {terminal_info.connected}")
                logger.info(f"  DLLバージョン: {terminal_info.version}")
                logger.info(f"  ディレクトリ: {terminal_info.path}")
                logger.info(f"  データディレクトリ: {terminal_info.data_path}")
                logger.info(f"  コモンディレクトリ: {terminal_info.commondata_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"MT5初期化中の例外: {e}", exc_info=True)
            return False

    def cleanup(self):
        """MT5接続のクリーンアップ"""
        try:
            if self.initialized:
                logger.info(f"MT5シャットダウン開始 - セッション: {self.session_id}")
                mt5.shutdown()
                self.initialized = False
                logger.info(f"MT5シャットダウン完了 - セッション: {self.session_id}")
                
                # ログハンドラをクリーンアップ
                for handler in logger.handlers[:]:
                    try:
                        handler.close()
                        logger.removeHandler(handler)
                    except Exception as e:
                        logger.error(f"ログハンドラのクリーンアップ中にエラー: {e}")
                
                # 少し待機してファイルハンドルが解放されるのを待つ
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"クリーンアップ中にエラー: {e}", exc_info=True)

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
                    logger.error(f"MT5ログインエラー: {error}")
                    return {'success': False, 'error': f"ログインに失敗: {error}"}
                
                return {'success': True, 'error': None}
            
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