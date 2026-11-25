import uuid
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.security import hash_token
from db.session import get_db
from db.models import AuthSession, User, Project, Document

COOKIE = "td_session"

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(COOKIE)
    if not raw:
        raise HTTPException(401, "Not authenticated")
    s = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(raw)))
    if not s or s.expires_at < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")
    user = db.get(User, s.user_id)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user

def project_for_user(project_id: uuid.UUID, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> Project:
    """Single authorization choke point. 404 (not 403) so IDs can't be probed."""
    p = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    if not p:
        raise HTTPException(404, "Project not found")
    return p

def document_for_user(document_id: uuid.UUID, user: User = Depends(current_user),
                      db: Session = Depends(get_db)) -> Document:
    d = db.scalar(select(Document).join(Project, Project.id == Document.project_id)
                  .where(Document.id == document_id, Project.owner_id == user.id))
    if not d:
        raise HTTPException(404, "Document not found")
    return d
