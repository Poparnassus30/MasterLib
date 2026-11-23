#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrat sérialisable des erreurs MasterLib."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import uuid
from typing import Any


_CODE_PATTERN = re.compile(r"^MLIB\.[A-Z][A-Z0-9_]*(\.[A-Z][A-Z0-9_]*)+$")
_VALID_SEVERITIES = {"warning", "error", "critical"}


@dataclass(frozen=True)
class ErrorEnvelope:
    """Enveloppe stable et sûre à transmettre à un autre composant."""

    code: str
    message: str
    component: str
    severity: str = "error"
    operation: str | None = None
    correlation_id: str | None = None
    retryable: bool = False
    context: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Seule la version 1 du contrat d'erreur est prise en charge")
        if not _CODE_PATTERN.fullmatch(self.code):
            raise ValueError(f"Code d'erreur MasterLib invalide : {self.code}")
        if self.severity not in _VALID_SEVERITIES:
            raise ValueError(f"Gravité invalide : {self.severity}")
        if not self.message.strip() or not self.component.strip():
            raise ValueError("Le message et le composant sont obligatoires")
        uuid.UUID(self.error_id)
        if not isinstance(self.context, dict):
            raise TypeError("Le contexte d'erreur doit être un objet")

    def to_dict(self) -> dict[str, Any]:
        """Retourne uniquement des valeurs compatibles avec le transport JSON."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "error_id": self.error_id,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "component": self.component,
            "occurred_at": self.occurred_at,
            "correlation_id": self.correlation_id,
            "retryable": self.retryable,
            "context": dict(self.context),
        }
        if self.operation:
            result["operation"] = self.operation
        return result
