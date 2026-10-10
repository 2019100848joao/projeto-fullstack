from datetime import datetime

import ulid
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.appointments.enums import AppointmentStatus
from app.modules.auth.models import User


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        default=lambda: ulid.new().str,
    )
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20),
        default=AppointmentStatus.SCHEDULED.value,
    )
    observations: Mapped[str | None] = mapped_column(Text)
    consultation_info: Mapped[str | None] = mapped_column(Text)
    attended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    patient: Mapped[User] = relationship(foreign_keys=[patient_id])
    doctor: Mapped[User] = relationship(foreign_keys=[doctor_id])
