class ServiceError(Exception):
    """Base exception for service layer failures."""

    def __init__(self, message: str, *, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


class DownstreamServiceError(ServiceError):
    """Raised when an external service returns an error response."""

    def __init__(self, message: str, status_code: int | None = None, *, cause: Exception | None = None):
        super().__init__(message, cause=cause)
        self.status_code = status_code
