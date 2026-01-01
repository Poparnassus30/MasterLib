DESCRIPTEUR 3/3 : MODULE_REINEROUGE (PATRIOTE - INTEGRATION METIER)

FICHIER :
module_reinerouge.py (ou modules/reinerouge/module_reinerouge.py)

TYPE :
Module d integration metier (adapter patriote)

NIVEAU :
Niveau 3 - Integration / Patriote

OBJECTIF
Permettre a une application metier externe (ex: Jeux_echec_2026)
d activer une instance ReineRouge "patriote" qui se branche
au reseau ReineRouge mere pour :

recevoir un contexte metier local

demander des analyses et actions

publier traces et apprentissages

eviter toute duplication de base de donnees souveraine

ROLE DANS L ECOSYSTEME

Le patriote ne remplace pas la mere.

Il agit comme une sonde / interface locale.

Il exige un bail reseau valide (pas de mode utile hors ligne).

ENTITES PRINCIPALES (A CODER)

Classe ModuleReineRouge (facade pour l app hote)

Classe ClientReseauReineRouge (transport + API)

Classe GestionBail (lease manager)

Classe AdaptateurMetier (traduction contexte -> jobs)

FONCTIONS PRINCIPALES (MAPPABLES EN METHODES)

Jonction reseau obligatoire (join)

decouvrir le reseau (bootstrap / dht)

s authentifier (challenge signe)

obtenir un bail court (droits, session)

renouveler
METHODES ATTENDUES :

reseau_decouvrir()

auth_demarrer()

auth_repondre_challenge(challenge)

bail_obtenir()

bail_renouveler()

bail_expirer()

Verrouillage offline

si pas de bail : refuser execution

option : mettre en file tampon minimale
METHODES ATTENDUES :

verifier_bail_valide()

refuser_job(raison)

queue_tampon_ajouter(job)

queue_tampon_vidanger()

Adaptation metier (bridge)

recevoir etat local (ex: position echec)

construire une requete ReineRouge

envoyer et recevoir resultat
METHODES ATTENDUES :

contexte_metier_set(contexte)

requete_construire(action, contexte)

requete_envoyer(requete)

resultat_traduire(resultat)

Publication trace et evenements

publier actions locales, erreurs, metriques

garantir coherence avec la source de verite
METHODES ATTENDUES :

evenement_publier(type_evt, payload)

trace_publier(prompt_id, meta)

metriques_publier(data)

API simplifiee pour l app hote

fonctions courtes utilisables par l app metier
METHODES ATTENDUES :

rr_status()

rr_assister(message)

rr_analyser(objet_metier)

rr_jouer(action_metier)

rr_stop()

TON POINT SUR "LES NIVEAUX" (IMPORTANT)

Tu as raison : module_reinerouge et module_IA ne sont pas au meme niveau.

module_IA = capacite (organe), utilisable par ReineRouge ou par un patriote si autorise

module_reinerouge = integration metier (adapter patriote), doit dependre du reseau ReineRouge

Et surtout :

module_reinerouge NE DOIT PAS embarquer module_IA par defaut
(sinon tu recrées une "reinerouge bis" locale)

mais il peut EVENTUELLEMENT l appeler si :
a) le reseau RR lui donne le droit
b) il le trouve comme service sur le reseau (module_IA distant)