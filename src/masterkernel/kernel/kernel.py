#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kernel.py — MasterKernel (superviseur central / noyau parent)

Vision
------
Le MasterKernel est le **parent** du système : il ne “fait pas le travail métier”.
Il **démarre**, **supervise**, **arrête** et **coordonne** des enfants (services/modules),
tout en maintenant une **source de vérité** via le Registre et une **vue** via l’IHM.

Le MasterKernel distribue des jobs : il choisit *qui* exécute (routing/policy),
envoie la requête via le Bus, puis collecte les résultats et met à jour l’état global.

Ce que le Kernel EST
---------------------
- Superviseur (orchestrateur) : lifecycle des services (start/stop/restart/health)
- Point de cohérence : registre global + politiques de routage
- Coordinateur : bus central, discovery, planification de jobs
- Poste de pilotage : IHM système (vue sur registre + actions)

Ce que le Kernel N’EST PAS
--------------------------
- Un service métier (ex: image segmentation, OCR, etc.)
- Un transport réseau (socket accept loop, DHT loop…) : ce sont des services/enfants
- Un endroit où importer les services directement (éviter imports circulaires)

Composants du MasterKernel
--------------------------
- kernel_registre.py
  - Source de vérité : état des services, ressources, jobs, liaisons, timestamps…
- kernel_bus.py
  - Messagerie/routage : réception/validation/dispatch des events & requêtes
- kernel_ihm.py
  - Vue : affiche le registre (style “gestionnaire système”) et interactions utilisateur
- (optionnel) kernel_policy.py
  - Règles : local d’abord, remote fallback, choix du meilleur worker, priorités…

Responsabilités principales
----------------------------
1) Boot / Initialisation
   - Charger config minimale
   - Initialiser logger
   - Initialiser Registre
   - Démarrer Bus + IHM
2) Lancement des enfants
   - Démarrer services d’infrastructure (transport, hotkeys, config_watch, subprocess…)
   - Démarrer services métiers (image_analyse, ocr, embed…)
   - Méthode recommandée : subprocess (isolement) + handshake health
3) Supervision
   - Heartbeats / health checks
   - Redémarrage contrôlé si crash
   - Arrêt propre (shutdown sequence)
4) Distribution de jobs
   - Sélection du service (capabilities + health + charge + policy)
   - Envoi via KernelBus
   - Collecte et enregistrement des résultats (registre + artefacts)
5) Observabilité
   - Logs unifiés + traces (request_id)
   - Exposition état global à l’IHM
6) Sécurité (évolution)
   - Authentification des services, signatures, ACL, isolation

Interfaces attendues
---------------------
- Contrats (masterstruct)
  - Request/Response versionnés (api_version)
  - Descripteurs de services (capabilities, endpoint)
  - JobSpec / JobResult (si utilisé)
- Services enfants (masterservice)
  - Fournissent health + capabilities
  - Acceptent des tasks via transport (socket, etc.)
  - Peuvent publier events vers le bus (logs, hotkeys, discovery…)

Cycle de vie (simplifié)
-------------------------
- start()
  - init registry
  - start bus thread/loop
  - start ihm thread/loop
  - launch essential services
  - enter supervision loop
- stop()
  - demander shutdown aux services
  - attendre arrêt confirmé
  - fermer bus/transports
  - flush logs
  - exit

Règles d’architecture
----------------------
- Le MasterKernel dépend de masterstruct (contrats) et d’utilitaires runtime,
  mais **n’importe pas** directement les implémentations de services.
- Les services communiquent avec le Kernel via le Bus/Transport (contrat commun),
  jamais par import Python du Kernel.
- Fractalisation : un nœud minimal peut ne lancer que registre+bus,
  un nœud riche peut lancer des workers GPU, DHT, etc.

Notes d’évolution
------------------
- Registry distribué (réplication DHT/LAN) tout en gardant un registre local “source”
- Routage multi-nœuds + choix du worker optimal
- Sandbox / permissions par service
"""

import logging
import time
import os
import threading
import sys
from pathlib import Path    
from masterkernel.system.system import System
from masterkernel.kernel.kernel_ihm import KernelIhm
from masterkernel.kernel.kernel_module import ModuleScanner
from masterkernel.kernel.kernel_bus import KernelBus


#CORE INTELIGENCE
class Kernel:
    def __init__(self, ctx) -> None:
        # Initialisation du noyau avec le contexte fourni.
        self.ctx = ctx

        #Initialise le noyau avec une instance du système.
        #chemin_absolu = Path(__file__).resolve().parent.parent
        #self.system = System(base_path=str(chemin_absolu))
        self.system = getattr(ctx, "system", None)
        if self.system is None and isinstance(ctx, dict):
            self.system = ctx.get("system")

        if self.system is None:
            raise RuntimeError("ctx.system manquant : runtime doit fournir System")
        
        # Permet au clavier (System) de demander un shutdown propre au Kernel
        self.system.shutdown_cb = self.stop

        self.logger = getattr(self.system, "logger", logging.getLogger("Kernel"))

        #Variable de status
        self.live_mode = True
        self.status_update_config = "None"
        self.running = False
        self.stopping = False

        # ------------------------------------------------------------------
        # BUS (v1) — in-process, sans transport pour l’instant
        # ------------------------------------------------------------------
        self.bus = KernelBus(system=self.system, registre=getattr(self.system, "registre", None))

        # Handlers "core" (toujours présents)
        self.bus.register_handler("kernel.ping", lambda msg: {"pong": True})

        def _h_shutdown(msg):
            reason = (msg.get("data") or {}).get("reason", "bus_shutdown")
            self.stop(reason=reason)
            return {"shutdown": "ok"}

        self.bus.register_handler("kernel.shutdown", _h_shutdown)

        # Démarre le bus (même si aucun transport n’est branché)
        self.bus.start()


        #Socket du noyau pour les processus enfants de MAsterApp
        self.socket_interface = None
        try:
            from MasterLib.src.masterservice.transport.ipc.transport_ipc import TransportIpc
            self.socket_interface = TransportIpc(self)
        except ImportError as e:
            self.logger.error(f"❌ Impossible d’importer TransportIpc : {e}")
                
        #Gestion des modules
        #self.module = ModuleBase()
                
        self.logger.info(" Noyau - Initialisation ")
        

    def run(self):
        self.running = True
        #controle de l'environnement graphique, l'interception du clavier fonctionne que sous x11
        self.system.verifier_environnement_graphique()
            
        try:
            self.logger.info("✅ Noyau ===> running, démmarrage de la boucle.")

            while self.running:

                # ------------------------------------------------------------------------
                # -- NOYAU MANAGER                               
                if not self.system.thread_manager.is_alive("noyau_manager"):
                    self.logger.warning("🛠️ Thread 'noyau_manager' inactif — redémarrage")
                    try:  
                        self.logger.warning("🛠️ Le thread 'noyau_manager' est mort — relance en cours")
                        self.system.thread_manager.run("noyau_manager", lambda: KernelIhm(self, live_mode = self.live_mode).run())
                    except Exception as e  :
                        self.logger.error(f"❌ Impossible de relancer noyau_manager : {e}")
                ###########################################################################

                # ------------------------------------------------------------------------
                # -- SOCKET UNIX
                if not self.system.thread_manager.is_alive("noyau_socket"):
                    self.logger.warning("🛠️ Thread 'noyau_socket' inactif — redémarrage")                 
                    try:
                        self.system.thread_manager.run("noyau_socket", self.socket_interface.start_threadable)   
                        self.logger.warning("🛠️ Thread 'noyau_socket' inactif — redémarrage")
                    except Exception as e   :
                        self.logger.error(f"❌ Impossible de relancer noyau_socket : {e}")
                ###########################################################################

                # ------------------------------------------------------------------------
                # --WATCH CONFIG config.ini
                if not self.system.thread_manager.is_alive("watch_config"):
                    self.logger.warning("🛠️ Thread 'watch_config' inactif — redémarrage")
                    try:
                        self.system.thread_manager.run("watch_config", lambda: self.system.config_manager.controle_maj_configuration(self))
                        self.logger.warning("✅ Thread 'module_scanner' relancé proprement.")
                    except Exception as e   :
                        self.logger.error(f"❌ Impossible de relancer watch_config : {e}")
                ###########################################################################

                # ------------------------------------------------------------------------
                # --CLAVIER
                if (not self.stopping) and self.system.en_cours_clavier:
                    if not self.system.thread_manager.is_alive("lancer_ecoute_clavier"):
                        self.logger.warning("🛠️ Thread 'lancer_ecoute_clavier' inactif — redémarrage")
                        try:
                            self.system.thread_manager.run("lancer_ecoute_clavier", self.system.lancer_ecoute_clavier)
                            self.logger.warning("✅ Thread 'lancer_ecoute_clavier' relancé proprement.")
                        except Exception as e  :
                            self.logger.error(f"❌ Impossible de relancer lancer_ecoute_clavier : {e}")
                ###########################################################################
                """
                # ------------------------------------------------------------------------
                # -- MODULE SCANNER (scan le dossier "modules")               
                if not self.system.thread_manager.is_alive("module_scanner"):
                    self.logger.warning("🛠️ Thread 'module_scanner' inactif — redémarrage en cours")

                    try:
                        #creation du ModuleScanner , une seul fois.
                        if not hasattr(self.system, "module_scanner"):
                            self.system.module_scanner = ModuleScanner(self.system)

                        self.system.thread_manager.run("module_scanner", lambda: self.system.module_scanner.run())    

                        self.logger.warning("✅ Thread 'module_scanner' relancé proprement.")

                    except Exception as e:
                        self.logger.error(f"❌ Impossible de relancer ModuleScanner : {e}")
                """
                ###########################################################################


                """
                # ------------------------------------------------------------------------
                # 🔍 Vérifier les threads vivants
                for nom, etat in self.system.lister_threads_actifs():
                    if etat == "terminé ❌":
                        self.logger.warning(f"⚠️ Thread '{nom}' s’est terminé.")
                ###########################################################################
                """


                ###########################################################################
                        
        
                time.sleep(3) #on evite la charge GPU

        except KeyboardInterrupt:
            self.logger.info("🛑 Arrêt manuel de MasterApp en cours.")
            self.stop()
                
    def stop(self, reason: str = "requested"):
        #Fermeture du programme:

        # Mettre self.running = False (arrête la boucle while).

        # Logger l’arrêt.

        # Stopper les subprocess : self.system.process_manager.stop_all()

        # Fermer la socket UNIX : self.socket_interface.arreter()

        # Stopper l’écoute clavier : self.system.en_cours_clavier = False

        # Attendre la fin des threads (join) pour ne pas tuer brutalement.

        # Logger la fermeture terminée.

        # Terminer le programme avec os._exit(0)

        self.stopping = True
        self.logger.info(f"🛑 Arrêt de MasterApp via stop() — reason={reason}")

        #.0. Sauvegadre du registre
        try:
            self.system.registre.sauvegarder_json(self.system.chemin_absolu("registre_json"))    
            self.logger.info(f"📦 Registre système (ID): {id(self.system.registre)}")
            self.logger.info(f"📦 Entrées dans le registre : {len(self.system.registre.tous())}")
        except Exception as e:
            self.logger.error(f"❌ Erreur de sauvegarde du registre: {e}")        

        #.1. Signaux d'interruption de la boucle principale et du clavier
        self.running = False  # stoppe la boucle while principale
        self.system.en_cours_clavier = False  # stoppe l’écoute clavier

        if hasattr(self.system, "module_scanner"):
            try:
                self.system.logger.info("🛑 Arrêt demandé au ModuleScanner...")
                self.system.module_scanner.stop() #signal de stop à ModuleScanner pour pas qu'il redemarre les subprocss
            except Exception as e:
                self.logger.warning(f"⚠️ Impossible d’arrêter ModuleScanner : {e}")

        #.2. Arrêt des subprocess
        self.logger.info("🛑 Arrêt des modules externes (subprocess)...")
        try:
            self.system.process_manager.stop_all()
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'arrêt des processus : {e}")

         # 3. Fermeture de la socket UNIX
        self.logger.info("🛑 Fermeture de la socket UNIX...")
        try:
            self.socket_interface.arreter()
        except Exception as e:
            self.logger.error(f"❌ Erreur socket : {e}")

        # 4. Attente des threads
        self.logger.info("⏳ Attente de l'arrêt des threads...")
        for nom, thread in self.system.threads.items():
            if thread.is_alive():
                self.logger.info(f"🕓 Attente thread : {nom}")
                thread.join(timeout=5)
                self.logger.info(f"✅ Thread terminé : {nom}")


        # 5. Nettoyagesocket file (si besoin)
        try:
            chemin_socket = "/tmp/masterapp.sock"
            if os.path.exists(chemin_socket):
                os.remove(chemin_socket)
                self.logger.info(f"🧹 Fichier socket supprimé : {chemin_socket}")
        except Exception as e:
            self.logger.warning(f"⚠️ Échec suppression fichier socket : {e}")

        # 6. Sortie
        self.logger.info("✅ MasterApp arrêté proprement.")
        os._exit(0)
