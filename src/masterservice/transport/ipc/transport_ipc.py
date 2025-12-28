#!/usr/bin/env python3
# network_ipc.py


import os
import socket 
import json

class TransportIpc:
    def __init__(self, kernel, chemin_socket="/tmp/masterapp.sock"):
        self.kernel = kernel
        self.chemin_socket = chemin_socket
        self.socket = None
        self.en_cours = True
        
    def start_threadable(self):
        self.demarrer()
        
    def demarrer(self):
        if os.path.exists(self.chemin_socket):
            os.remove(self.chemin_socket)

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.chemin_socket)
        self.socket.listen(1)

        self.kernel.logger.info(f"📡 Socket UNIX démarrée sur {self.chemin_socket}")
        self._ecouter()

    def _ecouter(self):
        while self.en_cours:
            conn, _ = self.socket.accept()
            with conn:
                data = conn.recv(1024).decode()
                response = self._traiter_commande(data)
                conn.sendall(response.encode())

    def _traiter_commande(self, message):
        message = message.strip().lower()
        if message == "status":
            return "Noyau online"
        elif message == "stop":
            self.kernel.en_cours = False
            return "Arrêt du noyau demandé."
        elif message == "threads":
            return json.dumps(self.kernel.system.lister_threads_actifs())
        elif message == "config_status": #status du fichier de config.ni
            return self.kernel.status_update_config
        elif message.startswith("log:"): #envoie d'un message à faire logger par le noyau
            log_message = message[4:].strip()
            self.kernel.logger.info(f"[MANAGER] {log_message}")
            return "Log reçu."   
        elif message == "uuid":
            return self.kernel.system.config_manager.get_or_create_uuid()
         
        return "Commande inconnue."

    def arreter(self):
        self.en_cours = False
        if self.socket:
            self.socket.close()
        if os.path.exists(self.chemin_socket):
            os.remove(self.chemin_socket)
        self.kernel.logger.info("🛑 Socket UNIX fermée.")

