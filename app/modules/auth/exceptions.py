class AuthError(Exception):
    pass


class EmailAlreadyRegisteredError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InactiveUserError(AuthError):
    pass


class UserNotFoundError(AuthError):
    pass


class RoleChangeNotAllowedError(AuthError):
    pass


class DoctorHasOpenWorkError(AuthError):
    """A doctor cannot leave the role with scheduled appointments or open exams."""
