"""
Schéma des événements (Event-Sourcing).

Rôle :
- Centraliser les types d’events (noms, versions, payload minimal).
- Offrir un format unique pour journaliser, répliquer, rejouer et auditer le système.

Contenu typique :
- Enum EventName (PROMPT_IN, CHILD_RESULT, ARTIFACT_READY, JOB_DONE, ERROR…)
- Dataclass/Event record : id, ts, job_id, type, payload, schema_version, signature (option).
"""
