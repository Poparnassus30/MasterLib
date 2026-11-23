#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Service de supervision en lecture seule pour les interfaces MasterLib."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from masterservice.errors import ErrorCodes, MasterLibError


class ServiceIhm:
    """Fournit un snapshot commun au terminal Rich et aux futures interfaces Web.

    Le service ne dépend pas du Kernel : les données runtime lui sont fournies par
    des fonctions de lecture et il expose une seule opération sur le KernelBus.
    """

    TOPIC = "ihm.snapshot"
    SNAPSHOT_SCHEMA_VERSION = 1

    def __init__(
        self,
        system,
        kernel_status_provider: Callable[[], dict[str, Any]],
        transport_provider: Callable[[], dict[str, Any]],
    ) -> None:
        self.system = system
        self.kernel_status_provider = kernel_status_provider
        self.transport_provider = transport_provider

    def register(self, bus) -> None:
        """Enregistre le point d'entrée de supervision en lecture seule."""
        bus.register_handler(self.TOPIC, self.handle_snapshot)

    def handle_snapshot(self, message: dict[str, Any]) -> dict[str, Any]:
        """Retourne l'état runtime, le transport et le registre dans une réponse."""
        correlation_id = message.get("id")
        try:
            snapshot = {
                "schema_version": self.SNAPSHOT_SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "app": self.system.app_name,
                "kernel": self.kernel_status_provider(),
                "transport": self.transport_provider(),
                "registry": {"entries": self.system.registre.to_dict()},
            }
            return {"snapshot": snapshot}
        except Exception as exc:
            error = MasterLibError(
                ErrorCodes.KERNEL_IHM_SNAPSHOT_UNAVAILABLE,
                "Le snapshot de supervision est indisponible.",
                component="masterservice.service.ihm",
                operation="snapshot",
                context={"exception_type": type(exc).__name__},
            )
            return self.system.errors.to_response(
                error,
                correlation_id=correlation_id,
                component="masterservice.service.ihm",
                cause=exc,
            )
