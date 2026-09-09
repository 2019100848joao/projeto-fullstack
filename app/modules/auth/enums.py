from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    PATIENT = "patient"
    DOCTOR = "doctor"
    ATTENDANT = "attendant"
