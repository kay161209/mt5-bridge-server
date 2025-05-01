from fastapi import FastAPI, HTTPException, Header, Body
from app.session_manager import init_session_manager, get_session_manager
from app.config import settings
from typing import Dict, Any, Optional
from pydantic import BaseModel

app = FastAPI(title="MT5 Bridge API")

# セッションマネージャーの初期化
init_session_manager()

class SessionCreateRequest(BaseModel):
    login: int
    password: str
    server: str

class CommandRequest(BaseModel):
    command: str
    params: Dict[str, Any] = {}

async def verify_token(x_api_token: str = Header(...)) -> None:
    if x_api_token != settings.bridge_token:
        raise HTTPException(status_code=401, detail="Invalid API token")

@app.get("/")
async def root():
    return {"message": "MT5 Bridge API"}

@app.post("/v5/session/create")
async def create_session(
    data: SessionCreateRequest,
    x_api_token: str = Header(...)
) -> Dict[str, Any]:
    await verify_token(x_api_token)
    try:
        manager = get_session_manager()
        session_id = manager.create_session(
            login=data.login,
            password=data.password,
            server=data.server
        )
        if not session_id:
            raise HTTPException(status_code=500, detail="Failed to create session")
        return {"success": True, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v5/session/list")
async def list_sessions(x_api_token: str = Header(...)) -> Dict[str, Any]:
    await verify_token(x_api_token)
    try:
        manager = get_session_manager()
        sessions = manager.list_sessions()
        return {"success": True, "sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v5/session/{session_id}/command")
async def execute_command(
    session_id: str,
    data: CommandRequest,
    x_api_token: str = Header(...)
) -> Dict[str, Any]:
    await verify_token(x_api_token)
    try:
        manager = get_session_manager()
        session = manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        result = manager.execute_command(
            session_id=session_id,
            command=data.command,
            params=data.params
        )
        if result is None:
            raise HTTPException(status_code=400, detail="Command execution failed")
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/v5/session/{session_id}")
async def delete_session(
    session_id: str,
    x_api_token: str = Header(...)
) -> Dict[str, Any]:
    await verify_token(x_api_token)
    try:
        manager = get_session_manager()
        session = manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        manager.cleanup_session(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 