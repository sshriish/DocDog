import uuid
from datetime import datetime
from sqlalchemy import (ForeignKey, String, Text, BigInteger, Integer, DateTime, Index,
                        UniqueConstraint, CheckConstraint, Computed, func)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from .session import Base

def pk(): return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
def now(): return mapped_column(DateTime(timezone=True), server_default=func.now())
def fkey(target, **kw): return mapped_column(ForeignKey(target, **kw), **({"index": True}))

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = now()

class AuthSession(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fkey("users.id", ondelete="CASCADE")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now()

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fkey("users.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fkey("projects.id", ondelete="CASCADE")
    uploader_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(20), index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(1000))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    processing_status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    processing_error: Mapped[str | None] = mapped_column(Text)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint("processing_status in ('queued','running','succeeded','failed','unsupported')"),)

class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[uuid.UUID] = pk()
    document_id: Mapped[uuid.UUID] = fkey("documents.id", ondelete="CASCADE")
    version_number: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(1000))
    checksum: Mapped[str] = mapped_column(String(64))
    change_description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = now()
    __table_args__ = (UniqueConstraint("document_id", "version_number"),)

class DocumentContent(Base):
    __tablename__ = "document_content"
    id: Mapped[uuid.UUID] = pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    structure: Mapped[dict | None] = mapped_column(JSONB)
    search_vector = mapped_column(TSVECTOR, Computed("to_tsvector('english', coalesce(extracted_text,''))", persisted=True))
    __table_args__ = (Index("ix_doc_content_fts", "search_vector", postgresql_using="gin"),)

class DocumentMetadata(Base):
    __tablename__ = "document_metadata"
    id: Mapped[uuid.UUID] = pk()
    document_id: Mapped[uuid.UUID] = fkey("documents.id", ondelete="CASCADE")
    key: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(10), default="system")
    __table_args__ = (CheckConstraint("source in ('system','user','ai')"),)

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = pk()
    document_id: Mapped[uuid.UUID] = fkey("documents.id", ondelete="CASCADE")
    job_type: Mapped[str] = mapped_column(String(50), default="process_document")
    stage: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = now()
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now()
    __table_args__ = (Index("ix_jobs_claim", "status", "run_after"),
                      CheckConstraint("status in ('queued','running','succeeded','failed','retrying')"))

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = now()
