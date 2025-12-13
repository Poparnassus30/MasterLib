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
import psutil


from configparser import ConfigParser
from pynput import keyboard
from typing import Callable

from masterstruct.system.system_manager_subprocess import ManagerSubprocess
from masterstruct.system.system_registre import ManagerRegistre
from masterstruct.system.system_manager_thread import ManagerThread
from masterstruct.system.system_manager_config import ManagerConfig

class System:
    def __init__(self, base_path: str = None) -> None:
        #1. init des variables environnements
        if base_path is None:
            base_path = os.getcwd()  # fallback sûr
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
    
    
    def chemin_absolu(self, element: str) -> str:
        return self.config_manager.chemin_absolu(element)

    ##########################################################################
    #GESTION DU LOGGER
    def setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("MasterApp")
        logger.setLevel(logging.INFO)
        # Vérifie s’il n’a pas déjà des handlers pour éviter les doublons
        if not logger.handlers:
            formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
            # Handler fichier
            log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "MasterApp.log")
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        return logger
    
            
    ###########################################################################  
    # GESTION DU  CLAVIER
    def lancer_ecoute_clavier(self):
        self.logger.info(" Détection clavier activé")

        pressed_keys = set()

        def on_press(key):
            # Log toutes les touches pressées (optionnel pour debug)
            #self.logger.debug(f"Touche pressée : {key}")

            pressed_keys.add(key)

            if (keyboard.Key.ctrl_l in pressed_keys or keyboard.Key.ctrl_r in pressed_keys):
                if key == keyboard.KeyCode.from_char('m'):
                    self.logger.info("🎹 CTRL+M détecté → Lancement du sélecteur utilisateur.")
                    #self.demarrer_selecteur_utilisateur()
                if key == keyboard.KeyCode.from_char('q'):
                    self.logger.info(' CTRL+P détecté → Fermeture de MasterApp')
                    self.noyau.stop()
                """
                elif key == keyboard.KeyCode.from_char('k'):
                    
                    self.logger.info("🎹 CTRL+N détecté → Lancement de la console de management.")
                    # Détection automatique du terminal
                    terminal_cmd = shutil.which("gnome-terminal") or shutil.which("x-terminal-emulator")
                    chemin_console = self.chemin_absolu("console_management")

                    # Lancement si terminal dispo
                    if terminal_cmd:
                        self.logger.warning(f"🛠️ TEST : chemin_console = {chemin_console}")
                        self.logger.warning(f"🛠️ TEST : fichier existe ? {os.path.exists(chemin_console)}")

                        subprocess.Popen([
                            terminal_cmd,
                            '--',
                            'bash', '-c',
                            f' {self.python_path} "{chemin_console}"; exec bash'
                        ])
                        self.logger.info("📟 Manager lancé dans un terminal.")
                        self.logger.info(f"🧪 Commande exécutée : {terminal_cmd} -- bash -c '{self.python_path} {chemin_console}; exec bash'")
                        self.logger.info(f"[DEBUG] Python utilisé : {self.python_path}")
                        self.logger.info(f"[DEBUG] Script console_management : {chemin_console}")
                        self.logger.info(f"[DEBUG] Commande bash : {self.python_path} \"{chemin_console}\"; exec bash")
                    else:
                        self.logger.error("❌ Aucun terminal graphique trouvé pour lancer le manager.")
                    """
                    
        def on_release(key):
            if key in pressed_keys:
                pressed_keys.remove(key)

        try:
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()

            self.logger.info("⌨️ Surveillance clavier active")
            while self.en_cours_clavier:
                time.sleep(0.5)

            listener.stop()
            self.logger.info("⌨️ Écoute clavier arrêtée.")
        except Exception as e:
            self.logger.error(f"❌ Erreur d’écoute clavier : {e}")        

    
    
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
