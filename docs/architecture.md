# Architecture

```mermaid
flowchart LR
    Request --> Planner
    Planner --> Policy
    Policy --> Tools
    Tools --> SQLite[(SQLite memory store)]
    Tools --> Reflection[(Reflection heuristics)]
    Tools --> Retention[(Retention cleanup)]
    Tools --> Audit[(Audit events)]
    Audit --> Response
```

The planner routes prompts into one memory operation at a time. Persisted memory is stored under `runtime-output\memory-store.sqlite3`, while retrieval and reflection operate only on active, unexpired rows.
