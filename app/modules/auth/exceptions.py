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
