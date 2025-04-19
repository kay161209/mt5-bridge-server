# MT5 Bridge API

MetaTrader 5 を FastAPI / WebSocket で操作するシンプルなブリッジ。

## 起動方法 (ローカル検証)

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # BRIDGE_TOKEN 等を設定
uvicorn main:app --reload --port 8000
```

http://localhost:8000/docs で Swagger UI を確認

ws://localhost:8000/v5/ws?token=<BRIDGE_TOKEN> で WebSocket 接続

## Git への push 例

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<user-or-org>/mt5-bridge.git
git push -u origin main
```

Private リポジトリの場合 は PAT か Deploy Key を用意し、
スタートアップ スクリプトで https://<token>@github.com/... 形式で clone してください。

これで完成
コードを GitHub に置く

GCE インスタンスにスタートアップ スクリプトを設定して起動
 → MT5 が立ち上がり、http(s)://<IP>/v5/... で即利用できます。

実装追加（注文キャンセル、口座残高取得、複数銘柄の価格プッシュなど）は routes.py に追記するだけで簡単に拡張可能です。