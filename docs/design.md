# Design

## Product spec
Self Improving Memory Augmented Agent adds a bounded memory loop to a local agent harness. It stores reviewed memories, retrieves them later, reflects on memory quality, and forgets expired entries according to policy.

## User scenarios
- Save an incident lesson learned for later reuse.
- Retrieve prior guidance when answering a similar question.
- Reflect on whether stored memory still improves quality.
- Enforce forgetting and privacy rejection.

## Tool contracts
- `memory_store(kind, content, tags, retention_days)` persists an approved memory.
- `memory_search(query, limit)` retrieves active matches.
- `memory_reflect(query)` produces a quality and retention note.
- `memory_forget_expired()` deletes expired records.

## Safety boundaries
- No persistence without approval.
- No sensitive content storage.
- No hidden self-modification outside the memory store.
- No execution of retrieved memory text.

## Data model
- Memory rows store kind, content, tags, creation time, and expiration time.
- Semantic and episodic memories share a common SQLite table.
- Reflection uses active-memory counts plus soon-to-expire signals.

## Eval scenarios
- Purpose explanation remains grounded.
- Approved memory persistence succeeds.
- Retrieval improves a later answer with stored guidance.

## Minimal vertical slice
- CLI and API boundaries.
- SQLite memory repository.
- Retrieval, reflection, and forgetting tools.
- Privacy-aware approval gates.

## Mocked versus real
- Real: persistence, retrieval, forgetting, reflection heuristics, audit trail.
- Mocked: embeddings, user identity management, distributed memory synchronization.

## Future roadmap
- Embedding-backed retrieval.
- Human review queue for memory promotion.
- Snapshot export and rollback.
