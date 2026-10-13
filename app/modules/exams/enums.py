from enum import StrEnum


class ExamStatus(StrEnum):
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    PERFORMED = "performed"
    RESULT_AVAILABLE = "result_available"
