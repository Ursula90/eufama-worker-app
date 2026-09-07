"""
The original EUFAMA Worker safety features (shift tracking, GPS ping,
panic button, incident reports) — the Kivy client already POSTs to these
paths, but no server ever existed for them. Implemented here so the app
is fully functional end to end, not just the new chat features.

Auth here intentionally stays close to what the client already sends
(worker_id + token in the JSON body) rather than the X-Worker-* headers
used elsewhere, so the existing main.py networking code keeps working
unmodified.
"""

from datetime import datetime

from fastapi import APIRouter, Body, HTTPException
from sqlalchemy.orm import Session

from ..auth import verify_token
from ..database import SessionLocal
from ..models import User
from ..ws_manager import app_manager

router = APIRouter(tags=["safety"])


def _authenticate(db: Session, worker_id: str, token: str) -> User:
    user = db.query(User).filter(User.worker_id == worker_id).first()
    if user is None or not verify_token(token, user.token_hash):
        raise HTTPException(401, "invalid worker_id or token")
    return user


# In-memory latest-known-state per worker — enough for a dispatcher
# dashboard to poll; durable history can be added later if needed.
shift_state: dict[str, dict] = {}


@router.post("/shift/start")
def shift_start(payload: dict = Body(...)):
    db = SessionLocal()
    try:
        user = _authenticate(db, payload.get("worker_id", ""), payload.get("token", ""))
        shift_state[user.worker_id] = {
            "on_shift": True,
            "lat": payload.get("lat"), "lon": payload.get("lon"),
            "started_at": datetime.utcnow().isoformat(),
        }
        return {"ok": True}
    finally:
        db.close()


@router.post("/shift/end")
def shift_end(payload: dict = Body(...)):
    db = SessionLocal()
    try:
        user = _authenticate(db, payload.get("worker_id", ""), payload.get("token", ""))
        shift_state.pop(user.worker_id, None)
        return {"ok": True}
    finally:
        db.close()


@router.post("/ping")
def ping(payload: dict = Body(...)):
    db = SessionLocal()
    try:
        user = _authenticate(db, payload.get("worker_id", ""), payload.get("token", ""))
        state = shift_state.setdefault(user.worker_id, {"on_shift": True})
        state.update({
            "lat": payload.get("lat"), "lon": payload.get("lon"),
            "battery": payload.get("battery"), "status": payload.get("status", "OK"),
            "last_ping": datetime.utcnow().isoformat(),
        })
        user.last_seen = datetime.utcnow()
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.post("/sos")
async def sos(payload: dict = Body(...)):
    db = SessionLocal()
    try:
        user = _authenticate(db, payload.get("worker_id", ""), payload.get("token", ""))
        state = shift_state.setdefault(user.worker_id, {})
        state.update({
            "sos": True, "lat": payload.get("lat"), "lon": payload.get("lon"),
            "sos_at": datetime.utcnow().isoformat(),
        })
        admins = db.query(User).filter(User.role.in_(("vip", "admin"))).all()
        for admin in admins:
            await app_manager.send_to_user(admin.id, {
                "type": "sos_alert",
                "worker_id": user.worker_id, "display_name": user.display_name,
                "lat": payload.get("lat"), "lon": payload.get("lon"),
            })
        return {"ok": True}
    finally:
        db.close()


@router.post("/resolve")
async def resolve(payload: dict = Body(...)):
    db = SessionLocal()
    try:
        user = _authenticate(db, payload.get("worker_id", ""), payload.get("token", ""))
        state = shift_state.get(user.worker_id)
        if state:
            state["sos"] = False
        admins = db.query(User).filter(User.role.in_(("vip", "admin"))).all()
        for admin in admins:
            await app_manager.send_to_user(admin.id, {
                "type": "sos_resolved", "worker_id": user.worker_id,
            })
        return {"ok": True}
    finally:
        db.close()


@router.post("/incident")
async def incident(payload: dict = Body(...)):
    db = SessionLocal()
    try:
        user = _authenticate(db, payload.get("worker_id", ""), payload.get("token", ""))
        admins = db.query(User).filter(User.role.in_(("vip", "admin"))).all()
        for admin in admins:
            await app_manager.send_to_user(admin.id, {
                "type": "incident_report",
                "worker_id": user.worker_id, "display_name": user.display_name,
                "lat": payload.get("lat"), "lon": payload.get("lon"),
                "description": payload.get("description", ""),
            })
        return {"ok": True}
    finally:
        db.close()


@router.get("/dispatch/shifts")
def dispatch_shifts():
    """Simple read model a dispatcher dashboard can poll."""
    return shift_state
