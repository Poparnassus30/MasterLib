#

"""
main.py — Point d’entrée du module NetBox (ReineRouge / MasterLib-ready)

Rôle
----
Ce fichier est le point d’entrée minimal de l’application “netops/netbox”.
Il orchestre l’exécution sans contenir de logique métier :
- charge la configuration (URL NetBox, token, timeouts, options)
- initialise le runtime (logger, contexte, gestion d’erreurs)
- instancie le cœur NetBox (NetBoxCore)
- déclenche les actions demandées (CLI, scan, export, synchro, etc.)

Philosophie
-----------
- main.py ne fait PAS de requêtes NetBox directement.
- Toute interaction avec NetBox passe par NetBoxCore (netbox/netboxcore.py).
- main.py reste stable : l’évolution se fait via des modules/collectors/exporters.

Évolutivité (MasterLib / ReineRouge)
------------------------------------
Ce point d’entrée est pensé pour être encapsulé plus tard dans MasterKernel :
- exécution en thread/subprocess
- commandes reçues via kernel_bus
- état publié dans un registre (state / events)
- configuration lue depuis data/config et non plus en dur

Entrées / Sorties
-----------------
Entrées :
- variables d’environnement et/ou fichier de config (ex: data/config/netbox.ini)
- arguments CLI (ex: "sync", "dump", "health", "topology")

Sorties :
- logs structurés
- codes retour (0 ok, !=0 erreur)
- fichiers export (ex: data/export/topology.json) selon le mode

Règles de sécurité
------------------
- aucun secret (token NetBox) ne doit être loggé.
- les exports ne doivent jamais contenir de secrets (références Bitwarden uniquement).

"""
 

