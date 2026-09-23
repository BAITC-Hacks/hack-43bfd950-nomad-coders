from app.contracts import Issue


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list[Issue] | None = None):
        self.status, self.code, self.message = status, code, message
        self.details = details or []
