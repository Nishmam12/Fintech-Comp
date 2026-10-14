"""Kernel errors. Every error maps to an HTTP status and a stable machine code (fail closed)."""
from __future__ import annotations


class KernelError(Exception):
    http_status = 400
    code = "KERNEL_ERROR"

    def __init__(self, message: str = "", *, code: str | None = None):
        super().__init__(message or (code or self.code))
        if code:
            self.code = code


class ValidationFailed(KernelError):
    http_status = 422
    code = "VALIDATION_FAILED"


class NotFound(KernelError):
    http_status = 404
    code = "NOT_FOUND"


class Forbidden(KernelError):
    http_status = 403
    code = "FORBIDDEN"


class Conflict(KernelError):
    http_status = 409
    code = "CONFLICT"


class IdempotencyConflict(Conflict):
    code = "IDEMPOTENCY_CONFLICT"


class DelegationRejected(KernelError):
    http_status = 422
    code = "DELEGATION_REJECTED"


class KernelBusy(KernelError):
    """Lock or statement timeout. Retryable; never an approval."""

    http_status = 503
    code = "KERNEL_BUSY"


class KernelInvariantError(KernelError):
    """A guard that must never fail did fail (e.g. a conditional UPDATE matched no row).
    The transaction rolls back. Never replace this with `assert`: asserts vanish under python -O."""

    http_status = 500
    code = "KERNEL_INVARIANT"


def ensure(cond: bool, what: str) -> None:
    if not cond:
        raise KernelInvariantError(what)
