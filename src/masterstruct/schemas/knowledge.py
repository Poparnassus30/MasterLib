"""
Schéma des KnowledgePackets (partage fédéré).

Rôle :
- Définir le format d’un paquet de connaissance échangeable entre nœuds (PEER/WITNESS/GENESIS).
- Permettre validation : hash/CID, signatures, scores de confiance, sources et métadonnées.

Important :
- Aucune clé privée ici. On ne stocke que des identifiants, hashes, signatures publiques.
"""
