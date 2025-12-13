# system/manager_subprocess.py

import subprocess
import os
import signal
import psutil
import traceback
import socket
import time

from system.system_registre import SubprocessEntry


class ManagerSubprocess:
    def __init__(self, system_ref):
        self.system = system_ref
        self.process_registry = {}  # Clé : nom du module, Valeur : Popen

    def run(self, name: str, chemin_module: str = "modules", terminal_visible: bool = False):
        """
        Démarre un subprocess identifié par `name` (ex: vpn), dans le dossier modules/
        - chemin_module est résolu via system.chemin_absolu() sauf si None
        - terminal_visible permet d'ouvrir un terminal dédié pour le débogage
        """

        # ✅ Protection renforcée contre les doublons
        if name in self.process_registry:
            proc = self.process_registry[name]
            if proc and proc.poll() is None:
                self.system.logger.info(f"[⛔] Processus '{name}' déjà lancé (PID {proc.pid}) — lancement ignoré.")
                return
            else:
                self.system.logger.warning(f"[⚠️] Processus '{name}' enregistré mais terminé — relancement autorisé.")
        
        #chemin du script
        try:
            if os.path.isabs(chemin_module):
                base_path = chemin_module
            else:
                base_path = self.system.chemin_absolu(chemin_module)

            chemin_script = os.path.join(base_path, f"{name}.py")

            if not os.path.exists(chemin_script):
                self.system.logger.error(f"[❌] Fichier introuvable : {chemin_script}")
                return
            
            # Creation d'une entrée dans le registre global
            entry = self.system.registre.creer_subprocess(
                nom = name,
                chemin_exec = chemin_script,
                terminal = terminal_visible
            )
            
            # lancement du subprocess
            if terminal_visible:
                proc = subprocess.Popen([
                    "gnome-terminal", "--",
                    self.system.python_path, chemin_script
                ])
                self.system.logger.info(f"[🖥️] Processus '{name}' lancé dans un terminal visible.")
            else:
                proc = subprocess.Popen([self.system.python_path, chemin_script])
                self.system.logger.info(f"[🚀] Processus '{name}' lancé silencieusement.")
            

            # Mise à jour de l'entrée dans le registre
            entry.pid = proc.pid 
            entry.en_cours = True

            #Attente confirmation socket
            self.system.logger.info(f"[⏳] Attente de confirmation via socket pour '{name}'...")
            entry.en_ligne = self._verifier_socket_module(name)

            # 🆕 Récupération du vrai PID via socket
            true_pid = self._obtenir_pid_via_socket(name)
            if true_pid:
                entry.pid = int(true_pid)
                self.system.logger.info(f"[🔎] PID réel reçu via socket : {true_pid}")
            else:
                self.system.logger.warning(f"[❌] Impossible d’obtenir le PID réel de '{name}' via socket.")

            self.system.logger.info(f"🔗 Registre utilisé ici (ID): {id(self.system.registre)}")
     
            """
            if not self._verifier_socket_module(name):
                self.system.logger.error(f"[❌] Le module '{name}' n’a pas confirmé son démarrage via socket.")
                proc.terminate()
                return
            """

            # ✅ enregistrement du processus dans le registre
            self.process_registry[name] = proc
            self.system.logger.debug(f"[🧾] Processus '{name}' enregistré avec PID {proc.pid}")

        except Exception as e:
            self.system.logger.error(f"[❌] Erreur au lancement de '{name}' : {e}")
            self.system.logger.error(f"[📋] Trace complète :\n{traceback.format_exc()}")

    def stop(self, name: str):
        """Arrête un subprocess identifié par nom."""
        proc = self.process_registry.get(name)
        entry = self.system.registre.get_by_name(name, type_objet="subprocess")

        # Etape 1: Tuer le PID du module.py
        if entry:
            pid_reel = entry.meta.get("pid_module")
            if pid_reel:
                try:
                    os.kill(int(pid_reel), signal.SIGTERM)
                    self.system.logger.info(f"[🛑] Module '{name}' (PID {pid_reel}) arrêté proprement.")
                except Exception as e:
                    self.system.logger.warning(f"[❌] Échec arrêt PID réel {pid_reel} : {e}")

        # Etape 2: Tuer le PID du terminal qui execute le PID du module.py
        if proc and self.is_alive(name):
            try:
                proc.terminal()
                proc.wait(timeout=5)
                self.system.logger.info(f"[🛑] Processus '{name}' terminé proprement.")
            except subprocess.TimeoutExpired:
                proc.kill()
                self.system.logger.warning(f"[💀] Processus '{name}' tué brutalement.")
        else:
            self.system.logger.warning(f"[⚠️] Aucun processus actif nommé '{name}' à arrêter.")

        self.process_registry.pop(name, None)

        self.system.registre.supprimer(name)  # en plus du pop de process_registry


    def stop_all(self):
        """Arrête tous les subprocess gérés."""
        for name in list(self.process_registry.keys()):
            self.stop(name)

    def is_alive(self, name: str) -> bool:
        """
        Vérifie si le processus est encore actif.
        - Cas 1 : PID enregistré => contrôle standard
        - Cas 2 : terminal visible => vérifie si le script Python tourne via psutil
        """
        proc = self.process_registry.get(name)

        if proc:
            if proc.poll() is None:
                return True
            else:
                self.system.logger.warning(f"[⚠️] Processus '{name}' enregistré mais terminé — relancement autorisé.")

        # 💡 Vérification alternative via psutil
        for p in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmd = p.info['cmdline']
                if cmd and any(name in part for part in cmd):
                    if self.system.python_path in cmd[0] or "python" in cmd[0]:
                        self.system.logger.debug(f"[🔍] Processus Python '{name}' toujours actif via psutil (PID {p.pid})")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return False

    def est_enregistre_et_vivant(self, name: str) -> bool:
        """Retourne vrai si le processus est enregistré et actif."""
        return name in self.process_registry and self.is_alive(name)

    def list(self):
        """Retourne l’état de tous les subprocess enregistrés."""
        return {
            name: "✅ actif" if self.is_alive(name) else "❌ terminé"
            for name in self.process_registry
        }

    def _verifier_socket_module(self, module_name, timeout=5) -> bool:
        """Tente de se connecter à la socket du module pour vérifier qu’il répond"""
        socket_path = f"/tmp/masterapp_{module_name}.sock"
        debut = time.time()

        while time.time() - debut < timeout:
            if os.path.exists(socket_path):
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.connect(socket_path)
                        client.sendall(b"status")
                        reponse = client.recv(1024).decode().strip()
                        return "en cours" in reponse.lower()
                except Exception:
                    pass
            time.sleep(0.2)

        return False

    def _obtenir_pid_via_socket(self, module_name: str, timeout=5):
        """Demande le PID réel du module via sa socket UNIX"""
        socket_path = f"/tmp/masterapp_{module_name}.sock"
        debut = time.time()

        while time.time() - debut < timeout:
            if os.path.exists(socket_path):
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.connect(socket_path)
                        client.sendall(b"pid")
                        return client.recv(1024).decode().strip()
                except Exception:
                    pass
            time.sleep(0.2)

        return None
