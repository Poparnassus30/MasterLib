#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kernel_ihm.py — KernelIhm (vue système du MasterKernel)

Rôle
-----
KernelIhm est la **vue** du MasterKernel : elle expose une “image” lisible de l'état
global en se basant sur le Registre (source de vérité). L'objectif est d'obtenir
un affichage type “gestionnaire système” (à la Windows) : services, threads,
processus, sockets, charge, logs récents, jobs en cours, etc.

KernelIhm ne prend **aucune décision d'orchestration** : elle observe et affiche.
Elle peut proposer des actions (start/stop/restart, filtrage, recherche), mais
l'exécution réelle passe par le KernelBus (et donc par le MasterKernel).

Entrées
--------
- Registre (kernel_registre) :
  - état des services (id, version, node_id, capabilities, health, charge)
  - état des ressources (threads, subprocess, sockets, files, queues…)
  - jobs (en attente / en cours / terminés) + timestamps
  - logs / événements (optionnel) ou références vers un service de logs
- (optionnel) Bus :
  - abonnements à des événements pour rafraîchir l'affichage en temps réel

Sorties
--------
- Affichage interactif (console Rich / TUI / GUI)
- Actions utilisateur (commandes) transmises au KernelBus :
  - "service.start", "service.stop", "service.restart"
  - "job.cancel", "job.retry"
  - "registry.inspect", "log.tail", etc.

Responsabilités principales
----------------------------
1) Rendering (rendu)
   - Transformer l'état du registre en tableaux/listes/graphes lisibles
   - Gérer la fréquence de rafraîchissement (polling ou events)
2) Navigation
   - Vues : services, jobs, ressources, logs, réseau (LAN/DHT), alertes
   - Filtres : par service, par état, par tag, par node_id, etc.
3) Interaction
   - Capturer les actions utilisateur (clavier/souris selon UI)
   - Émettre des commandes via le bus (sans exécuter directement)
4) Observabilité
   - Mettre en évidence : services down, redémarrages, latence, backlog, erreurs
   - Aider au debug : afficher trace/request_id, version modèle, artefacts

Principes d'architecture
-------------------------
- Lecture seule du registre (par défaut) : KernelIhm **n'écrit pas** l'état global.
- Les actions passent par le bus (contrat masterstruct), jamais par appels directs
  aux services (évite les dépendances et les chemins parallèles).
- KernelIhm est remplaçable : console TUI aujourd'hui, web UI demain, sans changer
  le registre ni les services.

Interfaces attendues
---------------------
- Registry API (local) :
  - `snapshot()` : état complet sérialisable
  - `get(path|query)` : accès ciblé (ex: services actifs)
  - (optionnel) `subscribe()` : events de modification
- KernelBus (optionnel) :
  - `emit(task, payload)` : envoyer commandes issues de l'IHM

Notes d'évolution
------------------
- Mode “dashboard” (rafraîchissement auto + alertes)
- Vue “topology” (graphe des nœuds/services via DHT/LAN)
- Historique (sparklines / séries temporelles des health/loads)
- UI web (même modèle : registre -> rendu)
"""

"""IHM console de diagnostic en lecture seule du MasterKernel."""

import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


class KernelIhm:
    """Affiche périodiquement l'état du registre local."""

    def __init__(self, noyau, live_mode=True):
        self.noyau = noyau
        self.system = noyau.system
        self.live_mode = live_mode
        self.logger = self.system.logger
        self.console = Console()

    def generer_affichage(self):
        """Construit l'affichage à partir du registre local."""
        try:
            groupes = self.system.registre.get_etat_registre(grouped=True)
        except Exception as exc:
            self.logger.error("Impossible de lire le registre : %s", exc)
            return Panel(
                f"Registre indisponible : {exc}",
                title="MasterKernel",
                border_style="red",
            )

        tables = []

        for type_registre, lignes in groupes.items():
            table = Table(
                title=f"Registre : {type_registre}",
                expand=True,
            )
            table.add_column("Type", style="bold magenta")
            table.add_column("Nom", style="bold cyan")
            table.add_column("PID / Identifiant", justify="right")
            table.add_column("État", style="bold green")
            table.add_column("Parent", style="bold yellow")
            table.add_column("Relations", style="dim")
            table.add_column("Mis à jour", style="dim")

            for ligne in lignes:
                try:
                    table.add_row(*(str(valeur) for valeur in ligne))
                except Exception as exc:
                    self.logger.warning(
                        "Entrée du registre ignorée : %s (%s)",
                        ligne,
                        exc,
                    )

            tables.append(table)

        if not tables:
            return Panel(
                "Aucune entrée dans le registre.",
                title="MasterKernel — registre local",
            )

        return Group(*tables)

    def afficher_console_manager(self):
        """Rafraîchit l'affichage sans lire le clavier ni envoyer de commande."""
        with Live(
            self.generer_affichage(),
            refresh_per_second=1,
            console=self.console,
            screen=True,
        ) as live:
            self.logger.info("Affichage console de supervision démarré.")

            try:
                while True:
                    time.sleep(1)
                    live.update(self.generer_affichage())
            except KeyboardInterrupt:
                self.logger.info("Affichage console interrompu.")

    def run(self):
        if self.live_mode:
            self.afficher_console_manager()
        else:
            self.console.print(self.generer_affichage())