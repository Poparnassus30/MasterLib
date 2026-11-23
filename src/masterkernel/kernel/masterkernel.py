#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MasterKernel : registre local, KernelBus et supervision minimale."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone

from masterkernel.kernel.kernel_bus import KernelBus
from masterkernel.system.system_registre import DesiredState, EntryState, RegistreEntry
from masterservice.transport.ipc.transport_ipc import TransportIpc
from masterservice.service.ihm import ServiceIhm


class Kernel:
    """Démarre les composants essentiels d'une instance MasterLib."""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self.system = getattr(ctx, "system", None)
        self.paths = getattr(ctx, "paths", None)
        if isinstance(ctx, dict):
            self.system = self.system or ctx.get("system")
            self.paths = self.paths or ctx.get("paths")
        if self.system is None or self.paths is None:
            raise RuntimeError("runtime doit fournir ctx.system et ctx.paths")

        self.logger = getattr(self.system, "logger", logging.getLogger("MasterKernel"))
        self.running = False
        self.stopping = False
        self.started_at: str | None = None
        self.status_update_config = "RAS"
        self._shutdown_event = threading.Event()
        self._stop_lock = threading.Lock()
        self.system.shutdown_cb = self.stop

        kernel_entries = self.system.registre.get_by_name("kernel")
        if not kernel_entries:
            raise RuntimeError("Entrée 'kernel' absente du registre")
        self.kernel_entry = kernel_entries[0]
        self.kernel_entry.pid = os.getpid()
        self.kernel_entry.set_desired(DesiredState.RUNNING)

        self.bus = KernelBus(system=self.system, registre=self.system.registre)
        self.bus.register_handler("kernel.ping", lambda _message: {"pong": True})
        self.bus.register_handler("kernel.status", self._handle_status)
        self.bus.register_handler("registry.snapshot", self._handle_registry_snapshot)
        self.bus.register_handler("kernel.shutdown", self._handle_shutdown)

        self.transport = TransportIpc(self.paths.master_endpoint)
        self.bus.register_transport(self.transport)

        self.transport_entry = RegistreEntry("transport.ipc", type_objet="transport")
        self.transport_entry.source = self.system.app_name
        self.transport_entry.meta.update({
            "name": self.transport.name,
            "endpoint": str(self.paths.master_endpoint),
            "protocol": "json-lines",
        })
        self.transport_entry.set_desired(DesiredState.RUNNING)
        self.transport_entry.set_state(EntryState.STARTING)
        self.system.registre.ajouter(self.transport_entry)

        self.ihm_service = ServiceIhm(
            self.system,
            kernel_status_provider=lambda: self._handle_status({}),
            transport_provider=self._handle_transport_status,
        )
        self.ihm_service.register(self.bus)

        self.logger.info("Démarrage du KernelBus et du transport local.")
        try:
            self.bus.start()
        except Exception as exc:
            self.transport_entry.set_state(EntryState.CRASHED, error=str(exc))
            self.kernel_entry.set_state(EntryState.CRASHED, error=str(exc))
            raise
        self.transport_entry.set_state(EntryState.RUNNING)
        self.logger.info("Transport IPC prêt : %s", self.paths.master_endpoint)

    def _handle_status(self, _message: dict) -> dict:
        return {
            "app": self.system.app_name,
            "pid": self.kernel_entry.pid,
            "state": self.kernel_entry.state,
            "running": self.running,
            "stopping": self.stopping,
            "started_at": self.started_at,
            "config_status": self.status_update_config,
        }

    def _handle_registry_snapshot(self, _message: dict) -> dict:
        return {"entries": self.system.registre.to_dict()}

    def _handle_transport_status(self) -> dict:
        return {
            "name": self.transport.name,
            "endpoint": str(self.paths.master_endpoint),
            "protocol": "json-lines",
            "state": self.transport_entry.state,
        }

    def _handle_shutdown(self, message: dict) -> dict:
        data = message.get("data") or {}
        reason = data.get("reason", "ipc_shutdown")
        # Laisse le transport envoyer l'accusé de réception avant de le fermer.
        threading.Timer(0.2, self.stop, kwargs={"reason": reason}).start()
        return {"shutdown": "accepted", "reason": reason}

    def run(self) -> int:
        self.running = True
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.kernel_entry.set_state(EntryState.RUNNING)
        self.kernel_entry.meta.update({"running": True, "stopping": False})

        self.logger.info("Noyau actif : registre, KernelBus et transport IPC prêts.")
        self.system.thread_manager.run(
            "watch_config",
            self.system.config_manager.controle_maj_configuration,
            self,
            self._shutdown_event,
        )

        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            self.stop(reason="keyboard_interrupt")
        finally:
            self.running = False
        return 0

    def stop(self, reason: str = "requested") -> None:
        with self._stop_lock:
            if self.stopping:
                return
            self.stopping = True

        self.logger.info("Arrêt demandé : %s", reason)
        self.running = False
        self._shutdown_event.set()
        self.system.en_cours_clavier = False
        self.kernel_entry.set_state(EntryState.STOPPING)
        self.kernel_entry.meta.update({"running": False, "stopping": True})

        try:
            self.system.process_manager.stop_all()
        except Exception:
            self.logger.exception("Erreur pendant l'arrêt des processus enfants")

        self.bus.stop()
        self.transport_entry.set_state(EntryState.STOPPED)
        try:
            self.system.thread_manager.join_all()
        except Exception:
            self.logger.exception("Erreur pendant l'attente des threads")

        self.kernel_entry.set_state(EntryState.STOPPED)
        self.kernel_entry.meta.update({"running": False, "stopping": False})
        try:
            self.system.registre.sauvegarder_json(str(self.paths.registry_file))
        except Exception:
            self.logger.exception("Impossible de sauvegarder le registre à l'arrêt")
        self.logger.info("Arrêt propre terminé.")
