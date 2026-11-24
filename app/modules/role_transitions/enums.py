from enum import StrEnum


class TransitionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TransitionTargetRole(StrEnum):
    DOCTOR = "doctor"
    ATTENDANT = "attendant"
