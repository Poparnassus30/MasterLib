"""Normalisation et journalisation centrale des erreurs MasterLib."""

from __future__ import annotations

import logging
from typing import Any

from masterstruct.schemas.errors import ErrorEnvelope
from .codes import ErrorCodes
from .exceptions import MasterLibError


class ErrorManager:
    """Construit les enveloppes d'erreur et conserve les détails dans le logger."""

    def __init__(self, logger: logging.Logger, component: str = "masterlib") -> None:
        self.logger = logger
        self.component = component

    def to_response(
        self,
        error: Exception,
        *,
        operation: str | None = None,
        correlation_id: str | None = None,
        component: str | None = None,
        cause: Exception | None = None,
    ) -> dict[str, Any]:
        """Journalise l'exception et retourne une réponse bus au format commun."""
        if isinstance(error, MasterLibError):
            code = error.code
            message = error.message
            severity = error.severity
            retryable = error.retryable
            context = error.context
            error_component = component or error.component
            error_operation = operation or error.operation
        else:
            code = ErrorCodes.INTERNAL_UNHANDLED_EXCEPTION
            message = "Une erreur interne empêche de terminer l'opération."
            severity = "error"
            retryable = False
            context = {"exception_type": type(error).__name__}
            error_component = component or self.component
            error_operation = operation

        log_method = (
            self.logger.warning if severity == "warning"
            else self.logger.critical if severity == "critical"
            else self.logger.error
        )
        logged_error = cause or error
        log_method(
            "Erreur %s dans %s%s (error_id généré dans la réponse)",
            code,
            error_component,
            f".{error_operation}" if error_operation else "",
            exc_info=(type(logged_error), logged_error, logged_error.__traceback__),
        )
        envelope = ErrorEnvelope(
            code=code,
            severity=severity,
            message=message,
            component=error_component,
            operation=error_operation,
            correlation_id=correlation_id,
            retryable=retryable,
            context=context,
        )
        return {"ok": False, "error": envelope.to_dict()}
