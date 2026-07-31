from __future__ import annotations

SAMPLE_MEMORY_GUIDANCE = {
    "purpose": (
        "Self Improving Memory Augmented Agent stores approved episodic and semantic memories, "
        "retrieves them for later answers, reflects on retained knowledge, applies retention "
        "policies with forgetting, and rejects sensitive data before persistence."
    ),
    "privacy": (
        "Sensitive data such as passwords, secrets, tokens, SSNs, and private keys must never be "
        "stored in memory."
    ),
}
