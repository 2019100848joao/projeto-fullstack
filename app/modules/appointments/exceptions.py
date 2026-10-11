class AppointmentError(Exception):
    pass


class AppointmentPermissionError(AppointmentError):
    pass


class DoctorNotFoundError(AppointmentError):
    pass


class PatientNotFoundError(AppointmentError):
    pass


class InvalidAppointmentTimeError(AppointmentError):
    pass


class AppointmentConflictError(AppointmentError):
    pass
