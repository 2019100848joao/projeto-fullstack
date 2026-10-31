from datetime import datetime

import ulid
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.auth.enums import UserRole
from app.modules.document_types.models import DocumentType  # noqa: F401


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        default=lambda: ulid.new().str,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    documents: Mapped[list["UserDocument"]] = relationship(
        cascade="all, delete-orphan",
        order_by=lambda: UserDocument.id,
    )
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.PATIENT.value)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    @property
    def document(self) -> "UserDocument | None":
        return self.documents[0] if self.documents else None


class UserDocument(Base):
    __tablename__ = "user_documents"
    __table_args__ = (
        UniqueConstraint("user_id", "type_id", name="uq_user_documents_user_type"),
    )

    id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        default=lambda: ulid.new().str,
    )
    user_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    value: Mapped[str] = mapped_column(String(255))
    type_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("document_type.id", ondelete="CASCADE"),
        index=True,
    )
