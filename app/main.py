from fastapi import FastAPI, HTTPException, Header
from app.session_manager import init_session_manager, get_session_manager
from app.config import settings
from typing import Dict, Any, Optional

app = FastAPI(title="MT5 Bridge API")

# セッションマネージャーの初期化
init_session_manager()

async def verify_token(x_api_token: str = Header(...)) -> None:
    if x_api_token != settings.bridge_token:
        raise HTTPException(status_code=401, detail="Invalid API token")

@app.get("/")
async def root():
    return {"message": "MT5 Bridge API"}

@app.post("/v5/session/create")
async def create_session(
    data: Dict[str, Any],
    x_api_token: str = Header(...)
) -> Dict[str, Any]:
    await verify_token(x_api_token)
    manager = get_session_manager()
    session_id = manager.create_session(
        login=data["login"],
        password=data["password"],
        server=data["server"]
    )
    return {"success": True, "session_id": session_id}

@app.get("/v5/session/list")
async def list_sessions(x_api_token: str = Header(...)) -> Dict[str, Any]:
    await verify_token(x_api_token)
    manager = get_session_manager()
    sessions = manager.list_sessions()
    return {"success": True, "sessions": sessions}

@app.post("/v5/session/{session_id}/command")
async def execute_command(
    session_id: str,
    data: Dict[str, Any],
    x_api_token: str = Header(...)
) -> Dict[str, Any]:
    await verify_token(x_api_token)
    manager = get_session_manager()
    result = manager.execute_command(
        session_id=session_id,
        command=data["command"],
        params=data.get("params", {})
    )
    return {"success": True, "result": result}

@app.delete("/v5/session/{session_id}")
async def delete_session(
    session_id: str,
    x_api_token: str = Header(...)
) -> Dict[str, Any]:
    await verify_token(x_api_token)
    manager = get_session_manager()
    manager.cleanup_session(session_id)
    return {"success": True} 