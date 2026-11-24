#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IHM Rich locale : lecture seule du registre à travers KernelBus."""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from masterservice.transport.ipc.transport_ipc import TransportIpc


class _ServiceIhmError(Exception):
    def __init__(self, error: dict) -> None:
        self.error = error
        super().__init__(error.get("message", "Erreur ServiceIhm"))


class KernelIhm:
    """Affiche un snapshot du registre; ne lit pas le clavier et n'envoie pas d'action."""

    def __init__(self, endpoint_file: str | Path, app_name: str = "MasterLib") -> None:
        self.endpoint_file = Path(endpoint_file)
        self.app_name = app_name
        self.console = Console()

    def _snapshot(self) -> dict:
        response = TransportIpc.request(
            self.endpoint_file,
            {"topic": "ihm.snapshot", "source": "kernel_ihm", "data": {}},
        )
        if not response.get("ok"):
            error = response.get("error")
            if isinstance(error, dict):
                raise _ServiceIhmError(error)
            raise RuntimeError(str(error or "Snapshot de supervision indisponible"))
        return response.get("snapshot", {})

    def generer_affichage(self):
        try:
            snapshot = self._snapshot()
        except _ServiceIhmError as exc:
            error = exc.error
            return Panel(
                f"[bold]{error.get('code', 'MLIB.KERNEL.IHM.SNAPSHOT_UNAVAILABLE')}[/bold]\n"
                f"{error.get('message', 'Snapshot de supervision indisponible.')}\n"
                f"Identifiant : {error.get('error_id', '—')}",
                title=f"{self.app_name} — supervision Rich",
                border_style="red",
            )
        except Exception as exc:
            return Panel(
                f"Transport local indisponible : {exc}\n\nVérifie que le noyau est démarré.",
                title=f"{self.app_name} — supervision Rich",
                border_style="red",
            )

        status = snapshot.get("kernel", {})
        transport = snapshot.get("transport", {})
        entries = snapshot.get("registry", {}).get("entries", {})
        header = Panel(
            f"État : [bold green]{status.get('state', 'inconnu')}[/bold green]   "
            f"PID : {status.get('pid', '—')}   "
            f"Démarré : {status.get('started_at') or '—'}\n"
            f"Transport : {transport.get('name', '—')} — {transport.get('endpoint', self.endpoint_file)}",
            title=f"{snapshot.get('app', self.app_name)} — MasterKernel",
            border_style="cyan",
        )

        table = Table(title="Registre local", expand=True)
        table.add_column("Type", style="magenta")
        table.add_column("Nom", style="cyan")
        table.add_column("PID / TID", justify="right")
        table.add_column("État", style="green")
        table.add_column("Relances", justify="right")
        table.add_column("Souhaité")
        table.add_column("Relations", style="dim")
        table.add_column("Erreur", style="red")

        entry_names = {
            entry_id: f"{entry.get('type', '—')}/{entry.get('nom', '—')}"
            for entry_id, entry in entries.items()
        }
        for entry in entries.values():
            pid = entry.get("pid", entry.get("ident", "—"))
            relations = ", ".join(
                entry_names.get(relation_id, relation_id)
                for relation_id in entry.get("relations", [])
            ) or "—"
            table.add_row(
                str(entry.get("type", "—")),
                str(entry.get("nom", "—")),
                str(pid if pid is not None else "—"),
                str(entry.get("state", "—")),
                str(entry.get("restart_count", 0)),
                str(entry.get("desired_state", "—")),
                relations,
                str(entry.get("last_error") or "—"),
            )

        return Group(header, table)

    def run(self, refresh_seconds: float = 1.0, once: bool = False) -> None:
        if once:
            self.console.print(self.generer_affichage())
            return
        with Live(
            self.generer_affichage(),
            refresh_per_second=1,
            console=self.console,
            screen=True,
        ) as live:
            try:
                while True:
                    time.sleep(refresh_seconds)
                    live.update(self.generer_affichage(), refresh=True)
            except KeyboardInterrupt:
                self.console.print("\n[dim]Supervision Rich fermée; le noyau continue.[/dim]")
