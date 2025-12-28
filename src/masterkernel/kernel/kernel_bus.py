#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# masterkernel/kernel/kernel_bus.py

# Descripteur: KernelBus (bus de communication du MasterKernel)
"""
   kernel_bus.py — KernelBus (bus de communication du MasterKernel)

   Rôle
   -----
   Le KernelBus est le **point central de messagerie** du MasterKernel.
   Il reçoit les messages (events / requêtes) provenant des services et modules,
   les **normalise** selon le contrat (masterstruct), les **route** vers les bons
   gestionnaires (registre, ihm, scheduler…), et émet en retour des commandes.

   Le bus est de la **logique de routage**, pas un “tuyau réseau”.
   Le transport (socket UNIX/TCP, etc.) est séparé : un service ou une couche
   Transport fournit `recv()` / `send()`, et le bus décide quoi faire des messages.

   Objectifs
   ----------
   - Unifier la communication Kernel <-> Services (même format, mêmes erreurs, même trace)
   - Centraliser : logs, traçabilité (request_id), sécurité/politiques, et routage
   - Découpler : les services n'importent jamais le Kernel, ils parlent au bus via contrat
   - Supporter 2 styles :
   - Event (asynchrone) : health, logs, hotkeys, découvertes DHT/LAN…
   - Request/Response (synchrone) : job.run -> job.result

   Responsabilités principales
   ---------------------------
   1) Réception
      - Lire des messages entrants depuis un ou plusieurs transports (IPC local, LAN, DHT).
   2) Validation / Normalisation
      - Vérifier `api_version`, `request_id`, structure du payload, etc.
   3) Routage (Dispatch)
      - Appeler le handler correspondant à `task` (ex: "health", "registry.register", "job.result").
   4) Émission
      - Envoyer des commandes aux services (ex: "shutdown", "job.run", "scan.start").
   5) Intégration Kernel
      - Mettre à jour le Registre (source de vérité)
      - Notifier l'IHM (vue du registre)
      - Déclencher des actions (policies) : ping, relance, escalade, etc.

   Interfaces attendues
   ---------------------
   - Transport(s) : objets fournissant au minimum :
   - `recv() -> dict|Message`  (bloquant ou non)
   - `send(message) -> None`
   - optionnel : `name`, `close()`, `is_alive()`
   - Contrat messages (masterstruct) :
   - Request : {api_version, request_id, task, payload, options, context, trace}
   - Response: {api_version, request_id, status, result, artifacts, metrics, trace, error}

   Handlers (exemples de tasks)
   -----------------------------
   - "health"                 : état du service / ping
   - "registry.register"      : annonce d'un service (capabilities, endpoint)
   - "registry.heartbeat"     : heartbeat + charge
   - "log.append"             : logs remontés par service
   - "hotkey.event"           : combinaisons clavier détectées
   - "job.run" / "job.result" : exécution et retour de job
   - "net.lan.discovered"     : découverte LAN
   - "net.dht.discovered"     : découverte DHT

   Règles d'architecture
   ----------------------
   - Le KernelBus ne contient **aucune logique métier** (ex: segmentation U-Net).
   - Aucun service n'importe MasterKernel. Communication uniquement via bus+contrat.
   - Le bus peut fonctionner en thread dédié, ou en boucle principale non-bloquante.

   Notes d'évolution
   ------------------
   - Ajouter une politique de routage (local d'abord, remote fallback)
   - Ajouter authentification/signature des messages (node_id, clés)
   - Ajouter QoS/priorités (events vs jobs)

   Logging — Convention & Rappel d'usage
   ------------------------------------
   Source de vérité :
   - Le logger racine est initialisé UNE SEULE FOIS par `System` (system.py -> setup_logger()).
   - `System` crée le logger nommé `<app_name>` et lui attache les handlers (console + fichier).
   - Donc : aucune classe "métier" (KernelBus, services, etc.) ne crée de FileHandler/StreamHandler.
   - Référence : System.setup_logger() crée logging.getLogger(self.app_name) et ajoute les handlers. 

   Convention de nommage :
   - Logger racine : <app_name>
   - Sous-loggers (via getChild) :
   - Kernel        : <app_name>.kernel
   - Bus           : <app_name>.bus
   - Registre      : <app_name>.registre
   - Threads       : <app_name>.thread
   - Subprocess    : <app_name>.subprocess
   - Config        : <app_name>.config
   - IHM           : <app_name>.ihm

   Rappel — Comment l'utiliser (pattern obligatoire) :
   - Le composant reçoit le logger depuis System, et crée un sous-logger :
   - self.logger = system.logger.getChild("bus")     # => <app_name>.bus
   - Le composant loggue uniquement via self.logger.* (info/warning/error/debug).
   - Si on veut un fichier dédié (ex: logs/kernel_bus.log), ça se fait côté System/LoggingManager
   en ajoutant un handler filtré sur <app_name>.bus — jamais dans KernelBus.

"""


from __future__ import annotations
from typing import Any, Dict, Callable, Optional
import time, uuid

Handler = Callable[[Dict[str, Any]], Dict[str, Any]]

class KernelBus:
    def __init__(self, system, registre=None):
        self.system = system
        self.registre = registre
        self.logger = system.logger.getChild("bus")

        self._handlers: dict[str, Handler] = {}
        self._transports = []
        self._running = False

    # --------- Public API ----------
    def register_handler(self, topic: str, handler: Handler) -> None:
        self._handlers[topic] = handler

    def register_transport(self, transport: Any) -> None:
        # transport = BaseTransport (duck typing)
        self._transports.append(transport)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.logger.info("🧠 KernelBus start")
        for t in self._transports:
            try:
                t.start(self.handle)   # handler = bus.handle
                self.logger.info(f"🔌 Transport démarré: {getattr(t,'name',t.__class__.__name__)}")
            except Exception as e:
                self.logger.exception(f"❌ Transport start failed: {t} -> {e}")

    def stop(self) -> None:
        self._running = False
        for t in self._transports:
            try:
                t.stop()
            except Exception:
                pass
        self.logger.info("🛑 KernelBus stop")

    def publish(self, topic: str, data: Optional[dict] = None, source: str = "kernel") -> Dict[str, Any]:
        msg = {
            "type": "event",
            "topic": topic,
            "source": source,
            "id": str(uuid.uuid4()),
            "ts": time.time(),
            "data": data or {},
        }
        return self.handle(msg)

    # --------- Core dispatch ----------
    def handle(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Entrée unique pour TOUS les messages (thread/module/subprocess)."""
        msg = self._normalize(msg)
        topic = msg["topic"]

        handler = self._handlers.get(topic)
        if handler is None:
            return {"ok": False, "id": msg["id"], "error": f"no_handler:{topic}"}

        try:
            resp = handler(msg) or {}
            return {"ok": True, "id": msg["id"], **resp}
        except Exception as e:
            self.logger.exception(f"💥 Handler crash topic={topic}: {e}")
            return {"ok": False, "id": msg["id"], "error": str(e)}

    def _normalize(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        # garde-fous (contract stable)
        out = dict(msg)
        out.setdefault("type", "event")
        out.setdefault("topic", "unknown")
        out.setdefault("source", "unknown")
        out.setdefault("id", str(uuid.uuid4()))
        out.setdefault("ts", time.time())
        out.setdefault("data", {})
        return out
