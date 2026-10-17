from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import UserOut
from ..ws_manager import app_manager

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("", response_model=list[UserOut])
def list_contacts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    others = db.query(User).filter(User.id != user.id).order_by(User.display_name).all()
    for o in others:
        o.is_online = app_manager.is_online(o.id)
    return others
