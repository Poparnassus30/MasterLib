# system/system_manager_thread.py

import threading
import traceback

from masterkernel.system.system_registre import DesiredState, EntryState, ThreadEntry


class ManagerThread:
    """Gestionnaire unique des threads démarrés par MasterLib."""

    def __init__(self, system_ref):
        self.system = system_ref
        self.registre = system_ref.registre
        self.threads = {}
        self.entries = {}
        self._launch_counts = {}
        self._lock = threading.RLock()

    def run(self, name: str, cible, *args, owner_name: str = "system",
            parent_entry_id: str | None = None, daemon: bool = True, **kwargs):
        """Enregistre puis démarre un thread et retourne son handle."""
        with self._lock:
            current = self.threads.get(name)
            if current is not None and current.is_alive():
                self.system.logger.warning(f"[⚠️] Thread '{name}' déjà actif.")
                return current

            entry = ThreadEntry(name)
            entry.source = owner_name
            entry.meta.update({"owner": owner_name, "thread_name": name})
            if parent_entry_id:
                entry.ajouter_relation(parent_entry_id)
            entry.restart_count = self._launch_counts.get(name, 0)
            self._launch_counts[name] = entry.restart_count + 1
            entry.set_desired(DesiredState.RUNNING)
            entry.set_state(EntryState.STARTING)
            self.registre.ajouter(entry)
            self.entries[name] = entry

            def wrapper():
                entry.ident = threading.get_native_id()
                entry.is_daemon = threading.current_thread().daemon
                entry.heartbeat()
                self.system.logger.info(
                    f"[🧵] Thread '{name}' actif (ID {entry.ident}, propriétaire {owner_name})."
                )
                try:
                    cible(*args, **kwargs)
                except Exception as exc:
                    entry.set_state(EntryState.CRASHED, error=str(exc))
                    self.system.logger.error(f"[💥] Thread '{name}' a échoué : {exc}")
                    self.system.logger.error(traceback.format_exc())
                else:
                    entry.set_state(EntryState.STOPPED)

            thread = threading.Thread(target=wrapper, name=name, daemon=daemon)
            try:
                thread.start()
            except Exception as exc:
                entry.set_state(EntryState.CRASHED, error=str(exc))
                raise
            self.threads[name] = thread
            entry.ident = thread.native_id
            self.system.logger.info(f"[🧵] Thread '{name}' démarré (TID {entry.ident}).")
            return thread

    def is_alive(self, name: str) -> bool:
        thread = self.threads.get(name)
        return bool(thread and thread.is_alive())

    def join(self, name: str, timeout: float | None = None) -> None:
        thread = self.threads.get(name)
        if thread and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def request_stop(self, name: str) -> None:
        """Signale l'arrêt souhaité; le worker doit sortir coopérativement."""
        entry = self.entries.get(name)
        thread = self.threads.get(name)
        if entry:
            entry.set_desired(DesiredState.STOPPED)
            if thread and thread.is_alive():
                entry.set_state(EntryState.STOPPING)

    def request_stop_owner(self, owner_name: str) -> None:
        with self._lock:
            names = [name for name, entry in self.entries.items()
                     if entry.source == owner_name]
        for name in names:
            self.request_stop(name)

    def join_all(self, timeout: float = 5) -> None:
        """Attend les threads connus sans tenter de joindre le thread appelant."""
        current = threading.current_thread()
        with self._lock:
            threads = list(self.threads.items())
        for name, thread in threads:
            if thread.is_alive() and thread is not current:
                self.system.logger.info(f"[🕓] Attente du thread : {name}")
                thread.join(timeout=timeout)

    def join_owner(self, owner_name: str, timeout: float = 5) -> None:
        """Attend les threads appartenant au composant demandé."""
        current = threading.current_thread()
        with self._lock:
            selected = [(name, thread) for name, thread in self.threads.items()
                        if self.entries.get(name)
                        and self.entries[name].source == owner_name]
        for _name, thread in selected:
            if thread.is_alive() and thread is not current:
                thread.join(timeout=timeout)

    def list(self):
        return {name: "✅ actif" if thread.is_alive() else "❌ terminé"
                for name, thread in self.threads.items()}
