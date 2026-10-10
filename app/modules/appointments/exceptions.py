class AppointmentError(Exception):
    pass


class AppointmentNotFoundError(AppointmentError):
    pass


class InvalidPatientError(AppointmentError):
    pass


class InvalidDoctorError(AppointmentError):
    pass


class DoctorUnavailableError(AppointmentError):
    pass


class AppointmentNotScheduledError(AppointmentError):
    pass


class AgendaDoctorRequiredError(AppointmentError):
    pass
