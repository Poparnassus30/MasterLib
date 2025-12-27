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

from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Group, Console
from rich.columns import Columns
import json
import os
import sys
import time

class KernelIhm():
    def __init__(self, noyau, live_mode):
        self.noyau = noyau
        self.system = noyau.system
        self.live_mode = live_mode
        self.logger = self.system.logger
        self.console = Console()
        self.CHEMIN_SOCKET = "/tmp/master.sock"

    def envoyer_commande(self, commande: str) -> str:
        if not os.path.exists(self.CHEMIN_SOCKET):
            self.logger.error("❌ Socket du noyau introuvable")
            return "❌ Noyau déconnecté"

        try:
            import socket
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(self.CHEMIN_SOCKET)
                client.sendall(commande.encode())
                return client.recv(1024).decode()
        except Exception as e:
            self.logger.error(f"❌ Erreur socket : {e}")
            return f"❌ Erreur : {e}"

    def get_etat_modules(self):
        """Analyse les modules déclarés et leur état d'exécution réel (via subprocess)"""
        try:
            config = self.system.config
        except Exception:
            return []

        if "modules" not in config:
            return []

        lignes = []

        for module, status in config["modules"].items():
            statut_config = "✅ activé" if status.lower() == "true" else "❌ désactivé"

            if self.system.process_manager.is_alive(module):
                processus = "🟢 lancé"
            else:
                processus = "🔴 arrêté"

            lignes.append((module, statut_config, processus))

        return lignes

    def generer_affichage(self):
        # 🎛️ CONSOLE INSTRUCTIONS
        instructions = Panel.fit(
            "[bold cyan]CTRL+M[/bold cyan] : ouvrir sélecteur\n"
            "[bold cyan]CTRL+N[/bold cyan] : ouvrir manager\n"
            "[bold cyan]CTRL+C[/bold cyan] : quitter",
            title="🎛️ Console",
            padding=(0, 1),
            border_style="white"
        )

        # 📡 ÉTAT MASTERAPP
        status = self.envoyer_commande("status")
        config_status = self.envoyer_commande("config_status")
        uuid = self.envoyer_commande("uuid")

        contenu = (
            f"[bold yellow]UUID :[/bold yellow] {uuid}\n"
            f"[bold yellow]Noyau :[/bold yellow] {status}\n"
            f"[bold magenta]config.ini :[/bold magenta] {config_status}"
        )

        panneau = Panel.fit(
            contenu,
            title="📡 État MasterApp",
            padding=(0, 1),
            border_style="white"
        )

        colonnes = Columns([panneau, instructions])

        # 📋 REGISTRE GLOBAL (processus, threads, modules, etc.)
        try:
            groupes = self.system.registre.get_etat_registre(grouped=True)
            tables = []

            for type_registre, lignes in groupes.items():
                t = Table(title=f"📂 Registre : {type_registre}", expand=True)
                t.add_column("Type", style="bold magenta")
                t.add_column("Nom", style="bold cyan")
                t.add_column("PID / Ident", justify="right")
                t.add_column("État", style="bold green")
                t.add_column("Parent", style="bold yellow")
                t.add_column("Relations", style="dim")
                t.add_column("🕓 Maj", style="dim")

                for ligne in lignes:
                    try:
                        t.add_row(*ligne)
                    except Exception as e:
                        self.logger.warning(f"[⚠️] Erreur ligne registre : {ligne} — {e}")

                tables.append(t)

        except Exception as e:
            self.logger.error(f"[❌] Erreur dans l'affichage du registre : {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            tables = []

        # 🔁 Affichage global combiné
        return Group(colonnes, *tables)
        def affichage_debug_terminal(self):
            self.logger.info("🧪 Mode debug terminal activé (sans Rich)")
            try:
                while True:
                    print("[MANAGER DEBUG] Noyau actif")
                    time.sleep(2)
            except KeyboardInterrupt:
                print("Arrêt demandé.")

    def afficher_console_manager(self):
        with Live(self.generer_affichage(), refresh_per_second=1, console=self.console, screen=True) as live:
            self.logger.info("🟢 Affichage console manager démarré")
            try:
                while True:
                    live.update(self.generer_affichage())
                    time.sleep(1)
            except KeyboardInterrupt:
                self.console.print("\n[bold red]🛑 Arrêt du manager[/bold red]")

    def run(self):
        if self.live_mode:
            self.afficher_console_manager()
        else:
            self.affichage_debug_terminal()
