# Safety

## Key controls
- Prompt injection checks on inbound requests.
- Approval required before any memory persistence.
- Sensitive data rejection before storage.
- Retention cleanup for expired memories.

## Failure modes covered by tests
- Sensitive data storage attempts.
- Retrieval with no matches.
- Timeout and forced tool failure.
- Approval denial for memory persistence.

## Residual risk
A production-grade memory layer would need stronger identity scoping, encryption at rest, and redaction-aware auditing.
