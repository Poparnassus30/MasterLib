"""
masterboot/scripts/phase_tree.sh

RÔLE
----
Point d'entrée CLI officiel du socle (repo MasterLib).

Ce module expose la commande console `master` (définie dans pyproject.toml)
et sert d'interface humaine/OS vers le processus de contrôle `masterboot`.

RESPONSABILITÉS
---------------
- Parse les arguments CLI (via argparse).
- construire l'arborescence de tous les fichiers de MasterLib et MasterLib projets, une vue générale creer aprés la creation du workspace.


RÈGLES D'OR
-----------
- Ne pas inclure de logique métier ici. Toute logique métier vit dans masterboot/controller.py.
SÉQUENCE (résumé)
-----------------
Utilisateur -> `master ...` -> masterboot.cli ->  -> 
-> masterboot.controller.Controller -> masterboot.scripts.phase_tree.sh -> (bash: tree)

NOTES
-----
Ce fichier est volontairement simple. Construie un fichier de debug de l'arborescence du projet.
"""
