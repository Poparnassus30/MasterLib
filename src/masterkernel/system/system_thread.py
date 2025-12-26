# system/system_manager_thread.py

import threading
import time
import traceback
from datetime import datetime

from masterstruct.system.system_registre import *

class ManagerThread:
    def __init__(self, system_ref):
        self.system = system_ref
        self.registre = system_ref.registre  # Pour accès au registre global
        self.threads = {}  # nom: Thread

    def run(self, name: str, cible, *args, **kwargs):
        """Lance un thread avec enregistrement dans le registre."""
        if name in self.threads and self.threads[name].is_alive():
            self.system.logger.warning(f"[⚠️] Thread '{name}' déjà actif.")
            return

        def wrapper():
            thread_obj = threading.current_thread()

            # Création de l'entrée dans le registre
            thread_entry = ThreadEntry(name)
            thread_entry.ident = thread_obj.ident
            thread_entry.is_daemon = thread_obj.daemon
            thread_entry.timestamp = datetime.utcnow()
            thread_entry.actif = True
            self.registre.ajouter(thread_entry)

            self.system.logger.info(f"[🧵] Thread '{name}' lancé (ID {thread_entry.ident}).")


            try:
                cible(*args, **kwargs)
            except Exception as e:
                self.system.logger.error(f"[💥] Thread '{name}' a échoué : {e}")
                self.system.logger.error(traceback.format_exc())
            finally:
                # 🟡 Mise à jour de l'état du thread à la fin
                thread_entry.actif = False
                thread_entry.timestamp = datetime.utcnow()

        thread = threading.Thread(target=wrapper, name=name, daemon=True)
        thread.start()
        self.threads[name] = thread
        self.system.logger.info(f"[🧵] Thread '{name}' lancé.")

    def is_alive(self, name: str) -> bool:
        """Vérifie si un thread nommé est actif."""
        return name in self.threads and self.threads[name].is_alive()

    def join_all(self):
        """Attend la fin de tous les threads vivants."""
        for name, thread in self.threads.items():
            if thread.is_alive():
                self.system.logger.info(f"[🕓] Attente du thread : {name}")
                thread.join(timeout=5)
                self.system.logger.info(f"[✅] Thread '{name}' terminé.")

    def list(self):
        """Retourne un dict avec les statuts des threads."""
        return {
            name: "✅ actif" if t.is_alive() else "❌ terminé"
            for name, t in self.threads.items()
        }