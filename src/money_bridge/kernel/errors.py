from enum import StrEnum


class ErrorCode(StrEnum):
    UNAUTHENTICATED = "unauthenticated"
    SCOPE_DENIED = "scope_denied"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"
    CONFLICT = "conflict"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    RATE_LIMITED = "rate_limited"
    LOCKED = "locked"
    STORAGE_FAILURE = "storage_failure"
    READ_ONLY = "read_only"
    INTERNAL = "internal"


HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.SCOPE_DENIED: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.CONFLICT: 409,
    ErrorCode.CAPABILITY_UNAVAILABLE: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.LOCKED: 503,
    ErrorCode.STORAGE_FAILURE: 503,
    ErrorCode.READ_ONLY: 409,
    ErrorCode.INTERNAL: 500,
}

CLI_EXIT: dict[ErrorCode, int] = {
    ErrorCode.INVALID_REQUEST: 2,
    ErrorCode.CONFLICT: 2,
    ErrorCode.UNAUTHENTICATED: 3,
    ErrorCode.SCOPE_DENIED: 4,
    ErrorCode.NOT_FOUND: 5,
    ErrorCode.CAPABILITY_UNAVAILABLE: 6,
    ErrorCode.RATE_LIMITED: 6,
    ErrorCode.LOCKED: 6,
    ErrorCode.STORAGE_FAILURE: 6,
    ErrorCode.READ_ONLY: 6,
    ErrorCode.INTERNAL: 1,
}


class MoneyBridgeError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @property
    def http_status(self) -> int:
        return HTTP_STATUS[self.code]

    @property
    def exit_code(self) -> int:
        return CLI_EXIT[self.code]

    def to_dict(self) -> dict[str, object]:
        body: dict[str, object] = {"code": self.code.value, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body
