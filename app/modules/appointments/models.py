from datetime import datetime

import ulid
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.appointments.enums import AppointmentStatus


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        default=lambda: ulid.new().str,
    )
    doctor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=AppointmentStatus.SCHEDULED.value,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
