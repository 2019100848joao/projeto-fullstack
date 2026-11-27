from datetime import datetime

import ulid
from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.role_transitions.enums import TransitionStatus


class RoleTransitionRequest(Base):
    __tablename__ = "role_transition_requests"
    __table_args__ = (
        # Mirrors migration 005: at most one pending request per user.
        Index(
            "ux_role_transition_requests_user_pending",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
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
    requested_role: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20),
        default=TransitionStatus.PENDING.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    reviewed_by_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
