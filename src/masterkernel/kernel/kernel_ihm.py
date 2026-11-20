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


class KernelIhm:
    """Affiche un snapshot du registre; ne lit pas le clavier et n'envoie pas d'action."""

    def __init__(self, endpoint_file: str | Path, app_name: str = "MasterLib") -> None:
        self.endpoint_file = Path(endpoint_file)
        self.app_name = app_name
        self.console = Console()

    def _snapshot(self) -> tuple[dict, dict]:
        status = TransportIpc.request(
            self.endpoint_file,
            {"topic": "kernel.status", "source": "kernel_ihm", "data": {}},
        )
        registry = TransportIpc.request(
            self.endpoint_file,
            {"topic": "registry.snapshot", "source": "kernel_ihm", "data": {}},
        )
        if not status.get("ok"):
            raise RuntimeError(status.get("error", "Statut du noyau indisponible"))
        if not registry.get("ok"):
            raise RuntimeError(registry.get("error", "Snapshot du registre indisponible"))
        return status, registry.get("entries", {})

    def generer_affichage(self):
        try:
            status, entries = self._snapshot()
        except Exception as exc:
            return Panel(
                f"Transport local indisponible : {exc}\n\nVérifie que le noyau est démarré.",
                title=f"{self.app_name} — supervision Rich",
                border_style="red",
            )

        header = Panel(
            f"État : [bold green]{status.get('state', 'inconnu')}[/bold green]   "
            f"PID : {status.get('pid', '—')}   "
            f"Démarré : {status.get('started_at') or '—'}\n"
            f"Transport local : {self.endpoint_file}",
            title=f"{self.app_name} — MasterKernel",
            border_style="cyan",
        )

        table = Table(title="Registre local", expand=True)
        table.add_column("Type", style="magenta")
        table.add_column("Nom", style="cyan")
        table.add_column("PID / ID", justify="right")
        table.add_column("État", style="green")
        table.add_column("Souhaité")
        table.add_column("Relations", style="dim")
        table.add_column("Erreur", style="red")

        for entry in entries.values():
            pid = entry.get("pid", entry.get("ident", "—"))
            relations = ", ".join(entry.get("relations", [])) or "—"
            table.add_row(
                str(entry.get("type", "—")),
                str(entry.get("nom", "—")),
                str(pid if pid is not None else "—"),
                str(entry.get("state", "—")),
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
