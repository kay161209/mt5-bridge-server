#!/usr/bin/env python
"""
MT5セッション作成のテストスクリプト
このスクリプトはMT5ブリッジサーバーの/session/createエンドポイントを直接テストします。
"""
import os
import sys
import json
import time
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_create_session")

# 環境変数の読み込み
env_file = Path(__file__).resolve().parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    logger.info(f"環境変数を読み込みました: {env_file}")
else:
    logger.warning(f".envファイルが見つかりません: {env_file}")

# 設定値
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/v5")
API_TOKEN = os.getenv("BRIDGE_TOKEN", "development_token")
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

def test_create_session():
    """MT5セッション作成をテストする"""
    logger.info("MT5セッション作成テストを開始します")
    
    # エンドポイントとヘッダー
    url = f"{BASE_URL}/session/create"
    headers = {
        "Content-Type": "application/json",
        "X-API-Token": API_TOKEN
    }
    
    # リクエストボディ
    payload = {
        "login": MT5_LOGIN,
        "password": MT5_PASSWORD,
        "server": MT5_SERVER
    }
    
    logger.info(f"リクエスト先: {url}")
    logger.info(f"ログイン情報: login={MT5_LOGIN}, server={MT5_SERVER}")
    
    try:
        # APIリクエスト
        response = requests.post(url, headers=headers, json=payload)
        
        # レスポンスの確認
        logger.info(f"ステータスコード: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"レスポンス: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if result.get("success"):
                session_id = result.get("session_id")
                logger.info(f"セッション作成成功！ session_id={session_id}")
                return session_id
            else:
                error_msg = result.get("message", "不明なエラー")
                logger.error(f"セッション作成失敗: {error_msg}")
        else:
            logger.error(f"APIエラー: {response.text}")
    
    except Exception as e:
        logger.exception(f"テスト実行中にエラーが発生しました: {e}")
    
    return None

def test_list_sessions(session_id=None):
    """作成されたセッションを一覧表示する"""
    logger.info("セッション一覧を取得します")
    
    url = f"{BASE_URL}/session/list"
    headers = {"X-API-Token": API_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            sessions = result.get("sessions", {})
            logger.info(f"アクティブなセッション: {len(sessions)}件")
            
            for sid, session in sessions.items():
                logger.info(f"- session_id={sid}: login={session.get('login')}, server={session.get('server')}")
                
                if session_id and sid == session_id:
                    logger.info(f"  作成したセッションが一覧に含まれています！")
        else:
            logger.error(f"セッション一覧取得エラー: {response.text}")
    
    except Exception as e:
        logger.exception(f"セッション一覧取得中にエラーが発生しました: {e}")

def main():
    """メイン処理"""
    logger.info("APIサーバーに接続してMT5セッション作成テストを実行します")
    
    # 必須パラメータの確認
    if not MT5_LOGIN or not MT5_PASSWORD or not MT5_SERVER:
        logger.error("MT5ログイン情報が設定されていません。.envファイルを確認してください。")
        logger.info("必要な環境変数: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER")
        return
    
    # セッション作成テスト
    session_id = test_create_session()
    
    if session_id:
        # 少し待機してプロセスが起動するのを待つ
        logger.info("5秒待機しています...")
        time.sleep(5)
        
        # セッション一覧の確認
        test_list_sessions(session_id)
    
    logger.info("テスト完了")

if __name__ == "__main__":
    main() 