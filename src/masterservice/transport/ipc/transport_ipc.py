#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transport IPC local portable, avec protocole JSON lignes sur TCP loopback."""

from __future__ import annotations

import hmac
import json
import os
import secrets
import socket
import threading
from pathlib import Path
from typing import Any, Callable


BusHandler = Callable[[dict[str, Any]], dict[str, Any]]
MAX_MESSAGE_BYTES = 1024 * 1024


class TransportIpc:
    """Relie des clients locaux au KernelBus, sans dépendre du Kernel."""

    name = "ipc.tcp_loopback"

    def __init__(self, endpoint_file: str | Path, *, timeout: float = 2.0) -> None:
        self.endpoint_file = Path(endpoint_file)
        self.timeout = timeout
        self.socket: socket.socket | None = None
        self.handler: BusHandler | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._token: str | None = None

    def start(self, handler: BusHandler) -> None:
        if self.is_ready():
            return

        self.handler = handler
        self._stop_event.clear()
        self.endpoint_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.endpoint_file.parent, 0o700)
        except OSError:
            pass
        self._remove_stale_endpoint()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(16)
            server.settimeout(0.5)
            host, port = server.getsockname()
            self._token = secrets.token_urlsafe(32)
            self._write_endpoint(host, port, self._token)
        except Exception:
            server.close()
            self.endpoint_file.unlink(missing_ok=True)
            raise

        self.socket = server
        self._ready.set()
        self._thread = threading.Thread(
            target=self._serve,
            name="masterkernel-ipc",
            daemon=True,
        )
        self._thread.start()

    def _write_endpoint(self, host: str, port: int, token: str) -> None:
        payload = json.dumps({"host": host, "port": port, "token": token})
        temporary = self.endpoint_file.with_suffix(self.endpoint_file.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(self.endpoint_file)

    def _remove_stale_endpoint(self) -> None:
        if not self.endpoint_file.exists():
            return
        try:
            endpoint = json.loads(self.endpoint_file.read_text(encoding="utf-8"))
            host, port = endpoint["host"], int(endpoint["port"])
            if host != "127.0.0.1":
                raise ValueError("Endpoint IPC hors loopback refusé")
            with socket.create_connection((host, port), timeout=0.25):
                raise RuntimeError(f"Un transport IPC écoute déjà sur {host}:{port}")
        except RuntimeError:
            raise
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            self.endpoint_file.unlink(missing_ok=True)

    def _serve(self) -> None:
        assert self.socket is not None
        while not self._stop_event.is_set():
            try:
                conn, _ = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stop_event.is_set():
                    break
                raise
            with conn:
                conn.settimeout(self.timeout)
                self._handle_client(conn)

    def _handle_client(self, conn: socket.socket) -> None:
        try:
            with conn.makefile("rb") as reader:
                raw = reader.readline(MAX_MESSAGE_BYTES + 1)
            if not raw:
                return
            if len(raw) > MAX_MESSAGE_BYTES:
                raise ValueError("Message trop volumineux")

            message = json.loads(raw.decode("utf-8"))
            if not isinstance(message, dict):
                raise ValueError("Le message doit être un objet JSON")
            token = message.pop("auth_token", None)
            if not self._token or not isinstance(token, str) or not hmac.compare_digest(token, self._token):
                raise PermissionError("Authentification IPC refusée")
            if self.handler is None:
                raise RuntimeError("Le handler du KernelBus n'est pas initialisé")
            response = self.handler(message)
            if not isinstance(response, dict):
                response = {"ok": False, "error": "invalid_handler_response"}
        except Exception as exc:
            response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

        try:
            payload = json.dumps(response, ensure_ascii=False, default=str).encode("utf-8") + b"\n"
            conn.sendall(payload)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def stop(self) -> None:
        self._stop_event.set()
        self._ready.clear()
        server, self.socket = self.socket, None
        if server is not None:
            server.close()

        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

        try:
            endpoint = json.loads(self.endpoint_file.read_text(encoding="utf-8"))
            if endpoint.get("token") == self._token:
                self.endpoint_file.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        self._token = None

    def is_ready(self) -> bool:
        return self._ready.is_set() and self.socket is not None

    @staticmethod
    def request(
        endpoint_file: str | Path,
        message: dict[str, Any],
        *,
        timeout: float = 2.0,
    ) -> dict[str, Any]:
        endpoint = json.loads(Path(endpoint_file).read_text(encoding="utf-8"))
        host, port, token = endpoint["host"], int(endpoint["port"]), endpoint["token"]
        if host != "127.0.0.1":
            raise ValueError("L'endpoint IPC doit rester sur 127.0.0.1")

        request = dict(message)
        request["auth_token"] = token
        payload = json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n"
        if len(payload) > MAX_MESSAGE_BYTES:
            raise ValueError("Message trop volumineux")

        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            client.sendall(payload)
            with client.makefile("rb") as reader:
                raw = reader.readline(MAX_MESSAGE_BYTES + 1)

        if not raw:
            raise ConnectionError("Le serveur IPC a fermé la connexion sans réponse")
        if len(raw) > MAX_MESSAGE_BYTES:
            raise ValueError("Réponse IPC trop volumineuse")
        response = json.loads(raw.decode("utf-8"))
        if not isinstance(response, dict):
            raise ValueError("La réponse IPC n'est pas un objet JSON")
        return response
