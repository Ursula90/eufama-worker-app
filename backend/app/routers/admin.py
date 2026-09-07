"""
Provisioning endpoints used by EUFAMA IT/Valy to create worker accounts.
Protected by a shared X-Admin-Key header (see config.ADMIN_API_KEY) — this
is not meant to be exposed to workers, only used from a trusted machine
when setting up a new phone.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import generate_token, hash_token, require_admin_key
from ..database import get_db
from ..models import User
from ..schemas import AdminCreateUserRequest, AdminCreateUserResponse, UserOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


@router.post("/users", response_model=AdminCreateUserResponse)
def create_user(req: AdminCreateUserRequest, db: Session = Depends(get_db)):
    if req.role not in ("worker", "vip", "admin"):
        raise HTTPException(400, "role must be worker, vip or admin")
    if db.query(User).filter(User.worker_id == req.worker_id).first():
        raise HTTPException(409, "worker_id already exists")

    token = generate_token()
    user = User(
        worker_id=req.worker_id,
        display_name=req.display_name,
        role=req.role,
        token_hash=hash_token(token),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AdminCreateUserResponse(user=UserOut.model_validate(user), token=token)


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.display_name).all()


@router.post("/users/{user_id}/reset-token", response_model=AdminCreateUserResponse)
def reset_token(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "user not found")
    token = generate_token()
    user.token_hash = hash_token(token)
    db.commit()
    return AdminCreateUserResponse(user=UserOut.model_validate(user), token=token)
