from enum import StrEnum


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class CalendarView(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
