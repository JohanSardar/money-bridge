# Core and executor are separate processes; the executor owns all action authority

Core (agent-facing, read-only credentials) can be reached by agents, so it never holds money-capable credentials or the action journal. The executor owns intents, approvals, limits, reservations and attempts in its own SQLCipher journal and exposes no execute or mark-approved call. A compromised core can relay proposals but cannot forge approval or rewrite limits.
