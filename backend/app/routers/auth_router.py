from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import verify_token
from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.worker_id == req.worker_id).first()
    if user is None or not verify_token(req.token, user.token_hash):
        raise HTTPException(401, "Invalid worker ID or token")

    user.last_seen = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return LoginResponse(user=UserOut.model_validate(user))
