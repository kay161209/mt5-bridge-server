# MT5 Bridge API

MetaTrader 5 を FastAPI / WebSocket で操作するシンプルなブリッジ。
すべての MT5 取引機能（ローソク足データの取得、注文の発注・キャンセル、ポジション管理など）をREST APIとして提供します。

**注意**: このシステムは MetaTrader 5 を使用するため、Windows OS 環境が必要です。
**Note**: This system requires a Windows OS environment as it uses MetaTrader 5.

## 起動方法 (ローカル検証)

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # BRIDGE_TOKEN 等を設定
uvicorn main:app --reload --port 8000
```

http://localhost:8000/docs で Swagger UI を確認

ws://localhost:8000/v5/ws/{session_id}?token=<BRIDGE_TOKEN> で WebSocket 接続
