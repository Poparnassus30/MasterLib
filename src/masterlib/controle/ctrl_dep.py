
# Analyse tous le code du dossier racine de l'application métier qui utilise MasterStruct
# pour en extraire les dépendances externes (librairies tierces)
# et les enregistrer dans un fichier requirements.txt
import os
import re
from masterlib.controle.ctrl_fichier import CtrlFichier
from masterlib.outil.outil_fichier import OutilFichier
from masterlib.outil.outil_chaine import OutilChaine

