#!/usr/bin/env python3
#
# ServiceApi, base hérité pour les services de MasterLib
# L'API "ServiceApi" commune doit couvrir tout ce qui est identique pour n’importe quel service, et laisser le reste au service lui-même.

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class ServiceApi(ABC):
    def __init__(self, service_name: str, service_version: str = "0.0.0"):
        self.service_name = service_name
        self.service_id: Optional[str] = None
        self.node_id: Optional[str] = None
        self.service_version = service_version

    def get_identity(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "service_id": self.service_id,
            "node_id": self.node_id,
            "service_version": self.service_version,
        }

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_handlers(self) -> Dict[str, Any]:
        ...

    def dispatch_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        # impl simple maintenant, extensible plus tard
        handlers = self.get_handlers()
        topic = request.get("topic")
        if topic not in handlers:
            return {"ok": False, "error": f"no_handler:{topic}"}
        return handlers[topic](request)


