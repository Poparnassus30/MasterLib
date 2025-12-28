#!/usr/bin/env python3
""" 
FrameService standard pour tous les service de la lib MasterLib.
Structure : ModuleNoyau hérite de ModuleSystem, qui hérite de :
- ManagerThread : gestion des threads
- ManagerConfig : gestion config INI et logs
Objectif : fournir un noyau modulaire, extensible et autonome à chaque service.
"""

import threading
import configparser
import os, sys
import logging
import time
import traceback

# --------------------------- THREAD MANAGER ---------------------------
class ManagerThread:
    def __init__(self):
        self.threads = {}

    def lancer_thread(self, nom: str, cible):
        if nom in self.threads and self.threads[nom].is_alive():
            print(f"[⚠️] Thread '{nom}' déjà actif.")
            return

        def wrapper():
            try:
                cible()
            except Exception as e:
                print(f"[💥] Erreur dans le thread '{nom}' : {e}")

        t = threading.Thread(target=wrapper, name=nom, daemon=True)
        t.start()
        self.threads[nom] = t
        print(f"[✅] Thread '{nom}' lancé.")

    def stop_all(self):
        for nom, t in self.threads.items():
            print(f"[🛑] Thread '{nom}' signalé pour arrêt.")
        self.threads.clear()


# --------------------------- CONFIG MANAGER ---------------------------
class ManagerConfig:
    def __init__(self, base_path, nom_module):
        self.base_path = base_path
        self.nom_module = nom_module
        self.config_path = os.path.join(base_path, "config.ini")
        self.log_path = os.path.join(base_path, f"{nom_module}.log")
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

        if "module" not in self.config:
            self.config["module"] = {"actif": "true"}
            self.save_config()

    def save_config(self):
        with open(self.config_path, "w") as f:
            self.config.write(f)

    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)

    def set(self, section, key, value):
        self.config.set(section, key, value)
        self.save_config()

# --------------------------- SOCKET MANAGER ---------------------------
import socket

class ManagerSocket:
    def __init__(self, nom_module):
        self.nom_module = nom_module
        self.socket_path = f"/tmp/masterapp_{nom_module}.sock"
        self._stop_socket = False

    def lancer_socket(self):
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        def boucle_socket():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as serveur:
                serveur.bind(self.socket_path)
                serveur.listen()
                print(f"[{self.nom_module}] 📡 Socket UNIX en écoute : {self.socket_path}")

                while not self._stop_socket:
                    try:
                        serveur.settimeout(1)
                        conn, _ = serveur.accept()
                        with conn:
                            data = conn.recv(1024).decode().strip()
                            if data == "status":
                                conn.sendall(b"Module en cours d'execution")
                            elif data == "pid":
                                pid = str(os.getpid())
                                conn.sendall(pid.encode())
                            elif data == "shutdown":
                                conn.sendall(b"Arret en cours")
                                self._stop_socket = True
                            else:
                                conn.sendall(b"Commande inconnue")
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"[{self.nom_module}] ❌ Erreur socket : {e}")

        self.socket_thread = threading.Thread(target=boucle_socket, daemon=True)
        self.socket_thread.start()

    def arreter_socket(self):
        self._stop_socket = True
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

# --------------------------- SYSTEM MODULE ---------------------------
class ModuleSystem(ManagerConfig, ManagerThread, ManagerSocket ):
    def __init__(self, nom_module):
        self.nom_module = nom_module
        self.base_path = os.path.dirname(os.path.abspath(__file__))

        super().__init__(self.base_path, nom_module)
        ManagerThread.__init__(self)
        ManagerSocket.__init__(self, nom_module)

        self.logger = self._setup_logger()

    def _setup_logger(self):
        logger = logging.getLogger(self.nom_module)
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(self.log_path)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)
        return logger

    def get_pid(self):
        return os.getpid()

    def arreter_module(self):
        self.logger.info(f"[{self.nom_module}] 🛑 Arrêt demandé.")
        self.stop_all()
        self.arreter_socket()


# --------------------------- NOYAU DE MODULE ---------------------------
class ModuleNoyau(ModuleSystem):
    def __init__(self, nom_module):
        super().__init__(nom_module)
        
    def initialiser(self):
        self.logger.info(f"[{self.nom_module}] 🔧 Initialisation du module...")

    def boucle_principale(self):
        while True:
            self.logger.info(f"[{self.nom_module}] ✅ En cours d'exécution")
            time.sleep(3)

    def run(self):
        self.initialiser()
        try:
            self.lancer_socket()
            self.boucle_principale()
        except KeyboardInterrupt:
            self.logger.warning(f"[{self.nom_module}] ⛔ Interruption manuelle")
        except Exception as e:
            self.logger.error(f"[{self.nom_module}] 💥 Erreur dans la boucle : {e}")
            self.logger.error(f"[{self.nom_module}] 📋 Traceback :\n{traceback.format_exc()}")
        
        finally:
            self.arreter_module()
