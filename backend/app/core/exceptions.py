"""
Domain errors.

One central handler (in main.py) turns them into
{"error": {"code": ..., "message": ...}} responses.
"""


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class InvalidImageError(AppError):
    status_code = 422
    code = "invalid_image"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class ModelUnavailableError(AppError):
    status_code = 503
    code = "model_unavailable"


class ConflictError(AppError):
    """For example: a field with that name already exists."""

    status_code = 409
    code = "conflict"


class InvalidParameterError(AppError):
    """A request value that passed type checks but is not acceptable, such as
    an unknown model key. Same code as other validation failures."""

    status_code = 422
    code = "validation_error"
