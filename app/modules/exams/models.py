from datetime import datetime

import ulid
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.auth.models import User
from app.modules.exams.enums import ExamStatus


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        default=lambda: ulid.new().str,
    )
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(20),
        default=ExamStatus.REQUESTED.value,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(Text)
    result_available_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    patient: Mapped[User] = relationship(foreign_keys=[patient_id])
    doctor: Mapped[User] = relationship(foreign_keys=[doctor_id])
