import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import SECRET_KEY
from .database import get_db
from .models import User


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hmac.new(SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def get_current_user(
    x_worker_id: str = Header(..., alias="X-Worker-Id"),
    x_worker_token: str = Header(..., alias="X-Worker-Token"),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.worker_id == x_worker_id).first()
    if user is None or not verify_token(x_worker_token, user.token_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return user


def require_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> None:
    from .config import ADMIN_API_KEY
    if not hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid admin key")


def authenticate_ws(worker_id: str, token: str, db: Session) -> User:
    user = db.query(User).filter(User.worker_id == worker_id).first()
    if user is None or not verify_token(token, user.token_hash):
        return None
    return user
