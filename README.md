# MT5 Bridge API

MetaTrader 5 を FastAPI / WebSocket で操作するシンプルなブリッジ。

**注意**: このシステムは MetaTrader 5 を使用するため、Windows OS 環境が必要です。

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
