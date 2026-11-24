#!/usr/bin/env python3
"""
FrameService des composants de MasterLib.
ModuleSystem délègue tous ses threads au gestionnaire unique fourni par System.
ManagerConfig gère la configuration INI et les logs du composant.
"""

import threading
import configparser
import os, sys
import logging
import time
import traceback

from masterkernel.system.system_registre import DesiredState, EntryState, RegistreEntry

# --------------------------- CONFIG MANAGER ---------------------------
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
    def __init__(self, nom_module, system_ref, parent_entry_id=None):
        self.nom_module = nom_module
        self.system = system_ref
        self.parent_entry_id = parent_entry_id
        self.owner_name = f"framework/{nom_module}"
        self.socket_path = f"/tmp/masterapp_{nom_module}.sock"
        self._stop_socket = threading.Event()

    def lancer_socket(self):
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        def boucle_socket():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as serveur:
                serveur.bind(self.socket_path)
                serveur.listen()
                print(f"[{self.nom_module}] 📡 Socket UNIX en écoute : {self.socket_path}")

                while not self._stop_socket.is_set():
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
                                self._stop_socket.set()
                            else:
                                conn.sendall(b"Commande inconnue")
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"[{self.nom_module}] ❌ Erreur socket : {e}")
                        raise

        self.socket_thread = self.system.thread_manager.run(
            f"{self.owner_name}/socket", boucle_socket,
            owner_name=self.owner_name,
            parent_entry_id=self.parent_entry_id,
        )

    def arreter_socket(self):
        self._stop_socket.set()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        self.system.thread_manager.join(f"{self.owner_name}/socket", timeout=2)

# --------------------------- SYSTEM MODULE ---------------------------
class ModuleSystem(ManagerConfig, ManagerSocket):
    def __init__(self, nom_module, system_ref, parent_entry_id=None):
        if system_ref is None or not hasattr(system_ref, "thread_manager"):
            raise ValueError("ModuleSystem doit recevoir le System MasterLib et son thread_manager")
        self.nom_module = nom_module
        self.system = system_ref
        self.thread_manager = system_ref.thread_manager
        self.owner_name = f"framework/{nom_module}"
        self.base_path = os.path.dirname(os.path.abspath(__file__))

        ManagerConfig.__init__(self, self.base_path, nom_module)
        self.framework_entry = RegistreEntry(nom_module, type_objet="framework")
        self.framework_entry.source = "system"
        self.framework_entry.meta.update({"owner": self.owner_name})
        self.framework_entry.set_desired(DesiredState.STOPPED)
        self.framework_entry.set_state(EntryState.STOPPED)
        if parent_entry_id:
            self.framework_entry.ajouter_relation(parent_entry_id)
        self.system.registre.ajouter(self.framework_entry)
        self.parent_entry_id = self.framework_entry.id
        ManagerSocket.__init__(self, nom_module, system_ref, self.parent_entry_id)

        self.logger = self._setup_logger()

    def lancer_thread(self, nom: str, cible, *args, **kwargs):
        return self.thread_manager.run(
            f"{self.owner_name}/{nom}", cible, *args,
            owner_name=self.owner_name,
            parent_entry_id=self.framework_entry.id,
            **kwargs,
        )

    def demarrer(self):
        self.framework_entry.set_desired(DesiredState.RUNNING)
        self.framework_entry.set_state(EntryState.STARTING)
        return self.thread_manager.run(
            self.owner_name, self.run,
            owner_name="system",
            parent_entry_id=self.framework_entry.id,
        )

    def stop_all(self):
        self.thread_manager.request_stop_owner(self.owner_name)
        self.thread_manager.join_owner(self.owner_name, timeout=5)

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
        self.framework_entry.set_desired(DesiredState.STOPPED)
        if self.framework_entry.state != EntryState.CRASHED.value:
            self.framework_entry.set_state(EntryState.STOPPING)
        self.thread_manager.request_stop(self.owner_name)
        self.arreter_socket()
        self.stop_all()


# --------------------------- NOYAU DE MODULE ---------------------------
class ModuleNoyau(ModuleSystem):
    def __init__(self, nom_module, system_ref, parent_entry_id=None):
        super().__init__(nom_module, system_ref, parent_entry_id)
        
    def initialiser(self):
        self.logger.info(f"[{self.nom_module}] 🔧 Initialisation du module...")

    def boucle_principale(self):
        while not self._stop_socket.is_set():
            self.logger.info(f"[{self.nom_module}] ✅ En cours d'exécution")
            time.sleep(3)

    def run(self):
        self.framework_entry.set_desired(DesiredState.RUNNING)
        self.framework_entry.set_state(EntryState.RUNNING)
        try:
            self.initialiser()
            self.lancer_socket()
            self.boucle_principale()
        except KeyboardInterrupt:
            self.logger.warning(f"[{self.nom_module}] ⛔ Interruption manuelle")
        except Exception as e:
            self.framework_entry.set_state(EntryState.CRASHED, error=str(e))
            self.logger.error(f"[{self.nom_module}] 💥 Erreur dans la boucle : {e}")
            self.logger.error(f"[{self.nom_module}] 📋 Traceback :\n{traceback.format_exc()}")
        finally:
            self.arreter_module()
            if self.framework_entry.state != EntryState.CRASHED.value:
                self.framework_entry.set_state(EntryState.STOPPED)
