# Threat Model

## Assets
- Stored memories
- Retrieval output
- Approval history
- Operator trust in adaptation

## Trust boundaries
- User prompts
- Persisted memory text
- Optional future embedding or distributed-memory adapters

## Main threats and mitigations
- Prompt injection -> blocked at intake.
- Memory poisoning -> approval gates plus reviewable explicit store calls.
- Sensitive data retention -> regex rejection and retention cleanup.
- Stale guidance -> expiration and reflection notes.
