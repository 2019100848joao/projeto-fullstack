from enum import StrEnum


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class AgendaView(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
