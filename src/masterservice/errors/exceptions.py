"""Exceptions typées communes de MasterLib."""

from __future__ import annotations

from typing import Any


class MasterLibError(Exception):
    """Erreur attendue ou normalisée avec un code stable."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        component: str,
        operation: str | None = None,
        severity: str = "error",
        retryable: bool = False,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.component = component
        self.operation = operation
        self.severity = severity
        self.retryable = retryable
        self.context = dict(context or {})
