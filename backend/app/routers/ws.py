import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..auth import authenticate_ws
from ..call_tokens import resolve_call_token
from ..database import SessionLocal
from ..ws_manager import app_manager, call_manager

router = APIRouter()


@router.websocket("/ws/app")
async def app_socket(websocket: WebSocket, worker_id: str, token: str):
    db = SessionLocal()
    try:
        user = authenticate_ws(worker_id, token, db)
        if user is None:
            await websocket.close(code=4401)
            return

        await app_manager.connect(user.id, websocket)
        user.is_online = True
        user.last_seen = datetime.utcnow()
        db.commit()

        try:
            while True:
                # This socket is mainly server -> client; we just need to
                # detect disconnects. Anything the client sends (e.g. a
                # keepalive ping) is simply discarded.
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await app_manager.disconnect(user.id, websocket)
            if not app_manager.is_online(user.id):
                user.is_online = False
                user.last_seen = datetime.utcnow()
                db.commit()
    finally:
        db.close()


@router.websocket("/ws/call/{call_id}")
async def call_socket(websocket: WebSocket, call_id: str, token: str):
    resolved = resolve_call_token(token)
    if resolved is None or resolved[0] != call_id:
        await websocket.close(code=4401)
        return
    _, user_id = resolved

    existing = call_manager.participants(call_id)
    await call_manager.join(call_id, user_id, websocket)
    await websocket.send_text(json.dumps({"type": "joined", "participants": existing}))
    await call_manager.broadcast(call_id, user_id, {"type": "peer-joined", "user_id": user_id})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type in ("offer", "answer", "candidate") and "to" in data:
                await call_manager.relay(call_id, user_id, data["to"], {
                    "type": msg_type, "payload": data.get("payload"),
                })
            elif msg_type == "leave":
                break
    except WebSocketDisconnect:
        pass
    finally:
        await call_manager.leave(call_id, user_id)
        await call_manager.broadcast(call_id, user_id, {"type": "peer-left", "user_id": user_id})
