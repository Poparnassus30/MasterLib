"""
Rôles de nœuds ReineRouge.

Rôle :
- Définir les rôles réseau/support :
  - GENESIS : nœud maître (gouvernance + proposition d’events)
  - WITNESS : attestation + réplication (pas de gouvernance)
  - PEER : fédération / échange de KnowledgePackets (opt-in)

Utilisation :
- Sert au handshake réseau et au filtrage des permissions/politiques.
"""
