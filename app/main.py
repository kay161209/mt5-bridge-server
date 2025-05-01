from fastapi import FastAPI

app = FastAPI(title="MT5 Bridge API")

@app.get("/")
async def root():
    return {"message": "MT5 Bridge API"} 