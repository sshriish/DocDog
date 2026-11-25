from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from core.config import get_settings
from core.security import hash_password, verify_password, new_session_token, hash_token
from db.session import get_db
from db.models import User, AuthSession, AuditLog
from .deps import current_user, COOKIE

router = APIRouter(prefix="/auth", tags=["auth"])

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    name: str = ""

class UserOut(BaseModel):
    id: str
    email: str
    name: str

def _start_session(db: Session, user: User, resp: Response):
    s = get_settings()
    raw, h = new_session_token()
    db.add(AuthSession(user_id=user.id, token_hash=h,
           expires_at=datetime.now(timezone.utc) + timedelta(hours=s.session_ttl_hours)))
    resp.set_cookie(COOKIE, raw, httponly=True, samesite="lax", secure=s.cookie_secure,
                    max_age=s.session_ttl_hours * 3600, path="/")

@router.post("/register", response_model=UserOut, status_code=201)
def register(body: Credentials, resp: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    db.add(user); db.flush()
    db.add(AuditLog(user_id=user.id, action="register", target=email))
    _start_session(db, user, resp); db.commit()
    return UserOut(id=str(user.id), email=user.email, name=user.name)

@router.post("/login", response_model=UserOut)
def login(body: Credentials, resp: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    db.add(AuditLog(user_id=user.id, action="login", target=user.email))
    _start_session(db, user, resp); db.commit()
    return UserOut(id=str(user.id), email=user.email, name=user.name)

@router.post("/logout", status_code=204)
def logout(request: Request, resp: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(COOKIE)
    if raw:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(raw))); db.commit()
    resp.delete_cookie(COOKIE, path="/")

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut(id=str(user.id), email=user.email, name=user.name)
