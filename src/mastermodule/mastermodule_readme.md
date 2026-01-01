------------------------------------------------------------
README - src/mastermodule/
------------------------------------------------------------

1) BUT DU DOSSIER
-----------------
Le dossier src/mastermodule/ contient l ensemble des "MasterModules"
de MasterLib.

Un MasterModule est un sous-programme executable, couplable, et standardise,
capable de fonctionner :
- en mode standalone (dev/test)
- en mode orchestre (par un hote : kernel/runtime)

Chaque MasterModule respecte le "Contrat MasterModule" :
- demarrage / arret propre
- IPC standard (messages JSON)
- handshake (HELLO/STATUS)
- execution de jobs (JOB_RUN/JOB_RESULT)
- publication d evenements (EVENT_PUBLISH)
- (optionnel) authentification et bail (lease)

Le detail technique (fonctions/methodes exactes) est decrit dans :
- le descripteur ASCII en tete de chaque fichier .py
- et dans le contrat universel MasterModule.

2) PHILOSOPHIE
--------------
MasterLib vise une architecture fractale :
- chaque module est un mini-systeme coherent,
- mais tous s imbriquent via une interface commune.

L objectif est d eviter :
- les dependances en spaghetti
- les modules qui ne savent pas qui est responsable de quoi
- les comportements non tracables

3) ORGANISATION DU DOSSIER
-------------------------

src/mastermodule/
  - contrat/               -> documents et base commune du contrat MasterModule
  - runtime/               -> outils hote (supervision, lancement, registre minimal)
  - capacite/              -> modules de capacite (organes reutilisables)
  - integration/           -> modules d integration metier (adapters, patriotes)
  - interfaces/            -> interfaces utilisateur ou interfaces systeme (optionnel)
  - exemples/              -> exemples de modules conformes (optionnel)
  - outils/                -> outils de dev/diagnostic (optionnel)

Note :
Les noms exacts des sous-dossiers peuvent evoluer, mais la logique reste :
- CAPACITE != INTEGRATION
- RUNTIME != MODULE

4) TYPES DE MODULES (NIVEAUX)
-----------------------------

NIVEAU 0 : RUNTIME (HOTE)
- lance, arrete, surveille
- handshake + registre minimal
- ne porte pas de metier

NIVEAU 1 : RESEAU / SOVEREINETE (si present dans MasterLib ou app mere)
- identite, bail, decouverte, preuve, memoire
- souvent porte par une application metier mere (ex: ReineRouge)

NIVEAU 2 : CAPACITE (ORGANE)
- une fonction reutilisable (IA, vision, analyse, etc.)
- peut tourner seul
- peut etre pilote par runtime ou par une app mere

NIVEAU 3 : INTEGRATION METIER (ADAPTER / PATRIOTE)
- pont entre une app metier locale et un reseau / une entite mere
- impose souvent une politique "pas de mode utile offline"
- traduit contexte local -> jobs standardises

5) EXEMPLES DE SOUS-DOSSIERS
---------------------------

A) src/mastermodule/capacite/module_ia/
- Module de capacite cognitive
- Connecte plusieurs IA externes (hemispheres) via des connecteurs
- Construit des packs memoire sous budget tokens
- Route vers le meilleur modele selon categories et performances
- Evalue les reponses et renvoie metriques

Le detail est dans les descripteurs des fichiers .py du module.

B) src/mastermodule/integration/module_reinerouge/
- Module d integration (patriote)
- Permet a une app metier externe (ex: jeux d echecs) de se brancher
  au reseau ReineRouge (mere)
- Authentification + bail reseau obligatoire
- Synchronisation des traces et evenements vers le reseau
- Refus d execution utile hors reseau

Le detail est dans les descripteurs des fichiers .py du module.

6) QUI APPELLE QUI (FLUX GENERAL)
--------------------------------

CAS 1 : MODE STANDALONE (DEV/TEST)
- l operateur lance un module dans un terminal
- le module charge config locale
- le module demarre IPC
- l operateur (ou un outil) envoie HELLO, STATUS, JOB_RUN
- le module renvoie JOB_RESULT
- STOP pour arret propre

CAS 2 : MODE ORCHESTRE (PROD)
- runtime/kernel lance le module (subprocess)
- runtime -> HELLO (handshake)
- module -> HELLO_ACK (READY)
- runtime enregistre module dans registre
- runtime envoie JOB_RUN
- module renvoie JOB_RESULT
- module publie EVENT_PUBLISH
- runtime peut envoyer STOP

CAS 3 : MODE RESEAU (EX: PATRIOTES)
- une app metier externe lance module_reinerouge
- module_reinerouge decouvre reseau (bootstrap)
- authentification + bail (lease)
- si bail valide : il devient operationnel
- il traduit contexte metier local en JOB_RUN vers l entite mere
- il publie evenements et traces vers le reseau
- si bail expire : mode verrouille (refus jobs)

7) LIMITES ET REGLES IMPORTANTES
-------------------------------

- Un module de capacite (ex: module_ia) n est pas une entite mere.
  Il ne doit pas devenir la memoire souveraine.
  Il renvoie des suggestions de memoire, mais la verite vit ailleurs.

- Un module d integration (ex: module_reinerouge) ne doit pas embarquer
  toute l entite mere en local.
  Il doit rester un pont, pas un clone.

- Tous les modules doivent etre observables :
  STATUS doit fonctionner, logs doivent etre clairs, erreurs normalisees.

8) DOCUMENTATION ET EXTRACTION AUTOMATIQUE
------------------------------------------

Chaque module et chaque fichier principal doit contenir un descripteur ASCII
en tete de fichier.

Objectif :
- un outil "manuel.py" peut parcourir MasterLib, extraire les descripteurs,
  et construire un manuel complet.
- l operateur et ReineRouge peuvent relire "a quoi ca sert" sans deviner.

Regle :
- le detail des methodes et responsabilites est dans les descripteurs .py
- le present README explique seulement :
  "structure / role / flux / regles"

9) CE QUI RESTE A DEFINIR (ROADMAP TECHNIQUE)
--------------------------------------------

- Base commune mastermodule_base.py :
  - parsing messages JSON
  - dispatch par type
  - etat interne
  - helpers logs/config
  - arret propre standard

- Spec "pack memoire" (format, budget, selection)
- Spec "registre" (format d enregistrement modules, timestamps, relations)
- Spec "transport reseau" (local UNIX puis reseau DHT)

------------------------------------------------------------
