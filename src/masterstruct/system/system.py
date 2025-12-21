#!/usr/bin/env python3


import logging
import os
import threading
import subprocess
import sys
import time
import uuid
import shutil
import traceback
import pkgutil
import select

if os.name != "nt":
    import tty
    import termios
else:
    tty = None
    termios = None

import re
import importlib



from configparser import ConfigParser

from typing import Callable

from masterstruct.system.system_subprocess import ManagerSubprocess
from masterstruct.system.system_registre import (SystemEntry, KernelEntry, ConfigEntry, EntryState, DesiredState, ManagerRegistre)
from masterstruct.system.system_thread import ManagerThread
from masterstruct.system.system_config import ManagerConfig

class System:
    def __init__(self, base_path: str = None, app_name: str = None, paths=None, shutdown_cb=None) -> None:
        self.shutdown_cb = shutdown_cb
        #1. initialise les attributs de base
        self.app_name = app_name or "App"
        self.paths = paths
        if base_path is None:
            base_path = str(self.paths.app_root) if self.paths else os.getcwd()
        self.base_path = base_path
        
        #2. initialise le logger
        self.logger = self.setup_logger()
        self.logger.info(f"🔧 Noyau - base_path :  {self.base_path}")
        self.logger.info(f"📂 base_path (pré-config) : {self.base_path}")
        
        #3. initialise la configuration
        self.config_manager = ManagerConfig(base_path=self.base_path, logger=self.logger)
        self.python_path = self.config_manager.get_python_path()

        self.uuid_noeud = self.config_manager.uuid_noeud
    
        # .initialisatoion du registre
        self.registre = ManagerRegistre(system =self)
        try:
            # 1) SYSTEM
            sys_entry = SystemEntry("system")
            sys_entry.source = self.app_name
            sys_entry.os_name = os.name
            sys_entry.os_version = os.uname().release if hasattr(os, "uname") else "unknown"
            sys_entry.architecture = os.uname().machine if hasattr(os, "uname") else "unknown"
            sys_entry.meta.update({
                "base_path": self.base_path,
                "python_path": self.python_path,
            })
            sys_entry.set_desired(DesiredState.RUNNING)
            sys_entry.set_state(EntryState.RUNNING)
            self.registre.ajouter(sys_entry)

            # 2) KERNEL (placeholder, complété par Kernel ensuite)
            kernel_entry = KernelEntry("kernel")
            kernel_entry.source = self.app_name
            kernel_entry.pid = os.getpid()
            kernel_entry.meta.update({
                "running": True,
                "stopping": False
            })
            kernel_entry.set_desired(DesiredState.RUNNING)
            kernel_entry.set_state(EntryState.STARTING)
            self.registre.ajouter(kernel_entry)

            # 3) CONFIG (snapshot logique, pas le contenu complet)
            cfg_entry = ConfigEntry("config", config={})
            cfg_entry.source = self.app_name
            cfg_entry.meta.update({
                "path": self.config_manager.chemin_absolu("config_ini"),
                "status": "RAS",
            })
            cfg_entry.set_desired(DesiredState.RUNNING)
            cfg_entry.set_state(EntryState.RUNNING)
            self.registre.ajouter(cfg_entry)
            
        except Exception as e:
            self.logger.error(f"❌ Impossible d'initialiser l'entrée système du registre : {e}")

        #. les threads
        self.threads: dict = {}
        self.en_cours_clavier = True 
    
        #. subprocess externe
        self.process_manager = ManagerSubprocess(self)

        #. Manager de thread
        self.thread_manager = ManagerThread(self)
        
        self.running = True
        #Initialisation du système terminé
        self.logger.info("🔧 Noyau - Initialisation...")

    def request_shutdown(self, reason: str = "requested"):
        self.logger.info(f"🛑 Shutdown demandé: {reason}")
        if callable(self.shutdown_cb):
            self.shutdown_cb(reason)
        else:
            # fallback si pas branché (ne crash pas)
            self.logger.warning("shutdown_cb non défini -> arrêt local clavier seulement")
            self.en_cours_clavier = False

    
    def chemin_absolu(self, element: str) -> str:
        return self.config_manager.chemin_absolu(element)

    ##########################################################################
    #GESTION DU LOGGER
    def setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.app_name)
        logger.setLevel(logging.INFO)

        # évite doublons si ré-init
        if logger.handlers:
            return logger

        formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")

        # console
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)

        # fichier
        if self.paths:
            log_file = str(self.paths.log_file)
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
        else:
            log_dir = os.path.join(self.base_path, "data", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{self.app_name}.log")

        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        logger.propagate = False
        return logger
    
            
    ###########################################################################  
    # GESTION DU  CLAVIER
    def lancer_ecoute_clavier(self):
        self.logger.info("⌨️ Détection clavier activée (pynput -> fallback TTY)")

        # --- Mode 1 : pynput (global hotkeys) ---
        try:
            from pynput import keyboard
            pressed_keys = set()

            def on_press(key):
                pressed_keys.add(key)

                if (keyboard.Key.ctrl_l in pressed_keys or keyboard.Key.ctrl_r in pressed_keys):
                    if key == keyboard.KeyCode.from_char('m'):
                        self.logger.info("🎹 CTRL+M détecté → (todo) sélecteur utilisateur.")
                    elif key == keyboard.KeyCode.from_char('q'):
                        self.logger.info("🎹 CTRL+Q détecté → shutdown")
                        if hasattr(self, "noyau") and self.noyau:
                            self.request_shutdown("CTRL+Q")
                        else:
                            self.en_cours_clavier = False

            def on_release(key):
                pressed_keys.discard(key)

            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()

            self.logger.info("⌨️ Surveillance clavier active (pynput)")
            while self.en_cours_clavier:
                time.sleep(0.5)

            listener.stop()
            self.logger.info("⌨️ Écoute clavier arrêtée (pynput)")
            return

        except Exception as e:
            self.logger.warning(f"⚠️ pynput indisponible/KO ({e}) -> fallback TTY")

        # --- Mode 2 : fallback TTY (CTRL+Q) ---
        self._ecoute_clavier_tty()


    def _ecoute_clavier_tty(self):
        """
        Fallback console: lit stdin en mode raw, détecte CTRL+Q.
        Fonctionne en SSH/Termux/headless. Doit être lancée en thread.
        """
        if not sys.stdin.isatty():
            self.logger.warning("stdin n'est pas un TTY -> pas de fallback clavier possible")
            return

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)

        CTRL_Q = 17  # ASCII DC1

        try:
            tty.setraw(fd)
            self.logger.info("⌨️ Surveillance clavier active (TTY) : CTRL+Q pour quitter")

            while self.en_cours_clavier:
                r, _, _ = select.select([fd], [], [], 0.25)  # timeout pour vérifier le flag
                if not r:
                    continue

                b = sys.stdin.buffer.read(1)
                if not b:
                    continue

                if b[0] == CTRL_Q:
                    self.logger.info("🎹 CTRL+Q détecté (TTY) → shutdown")
                    if hasattr(self, "noyau") and self.noyau:
                        self.request_shutdown("CTRL+Q")
                    else:
                        self.en_cours_clavier = False
                    break

        except Exception as e:
            self.logger.error(f"❌ Erreur fallback clavier TTY : {e}")

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            self.logger.info("⌨️ Écoute clavier arrêtée (TTY)")    
    
    ##########################################################################
    # INSTALL DEPENDANCES 
    def verifier_et_installer_toutes_dependances(self, dossier_base=None):
            if not dossier_base:
                dossier_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            
            modules_requis = set()
            regex_import = re.compile(r'^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)')

            for root, dirs, files in os.walk(dossier_base):
                for fichier in files:
                    if fichier.endswith(".py"):
                        chemin = os.path.join(root, fichier)
                        with open(chemin, "r", encoding="utf-8", errors="ignore") as f:
                            for ligne in f:
                                match = regex_import.match(ligne)
                                if match:
                                    nom_module = match.group(1).split('.')[0]
                                    modules_requis.add(nom_module)

            modules_installes = {pkg.name for pkg in pkgutil.iter_modules()}

            for module in sorted(modules_requis):
                if module not in modules_installes:
                    try:
                        importlib.import_module(module)
                    except ImportError:
                        try:
                            self.logger.warning(f"📦 Module manquant : {module} → installation en cours...")
                            subprocess.check_call([sys.executable, "-m", "pip", "install", module])
                            self.logger.info(f"✅ Module '{module}' installé.")
                        except Exception as e:
                            self.logger.error(f"❌ Échec de l'installation du module '{module}' : {e}")    
        
    def verifier_environnement_graphique(self):
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session_type == "wayland":
            self.logger.warning("⚠️ Environnement Wayland détecté.")
            self.logger.warning("❌ pynput risque de ne pas fonctionner correctement (CTRL+N, etc.).")
            self.logger.warning("💡 Recommandé : se connecter à une session X11 (GNOME on Xorg).")
            print("⚠️ [WARN] Vous êtes sous Wayland. Certains raccourcis clavier (comme CTRL+N) peuvent ne pas être détectés.")
            print("💡 Conseil : déconnectez-vous et reconnectez-vous en mode GNOME sur Xorg.")
        else:
            self.logger.info(f"✅ Session graphique : {session_type.upper()} (OK)")






    """
    def check_for_updates(self) -> bool:
        
        #Vérifie s'il y a une mise à jour disponible du système.
        
        pass

    def perform_update(self) -> None:
        
        #Exécute la mise à jour du système (via git ou autre mécanisme).
        
        pass


    def get_system_status(self) -> dict:
        
        #Retourne l’état du système (mémoires, threads, version, etc.).
        
        pass
        
    #PARTIE NOEUD , execution et decouverte
    def decouvrir_autres_noeuds(self) -> list:
        #Découvre et retourne une liste de nœuds accessibles.
        pass

    def connecter_aux_noeuds(self, liste_noeuds: list) -> None:
        #Établit les connexions réseau aux autres nœuds.
        pass

    def envoyer_message(self, noeud_cible: str, message: dict) -> None:
        #Envoie un message structuré à un autre nœud.
        pass

    def recevoir_messages(self) -> None:
        #Écoute les messages entrants sur un port dédié.
        pass
"""
