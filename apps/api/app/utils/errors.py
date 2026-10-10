from typing import Any


class AppError(Exception):
    """Domain error rendered as the error envelope: code, message, details."""

    def __init__(
        self, code: str, message: str, status: int = 400, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}
