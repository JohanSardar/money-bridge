# Debate round 1: Claude's position on the differences

Designs: astra/DESIGN-astra.md and claude/DESIGN-claude.md.

## Agreed (no debate needed)
- Python; FastMCP embedded (proxy) for the MCP door and for running official MCPs privately; FastAPI + Typer for the other doors.
- Two trusted processes: a data/agent-facing core with no money credentials, and an executor that alone holds credentials and runs official Alpaca/Link tools.
- Append-only observations → revisions → current projections → events outbox in one SQLite transaction; history never mutated.
- Frozen intent + digest → approval adapter (provider-native for Link, Cosignet otherwise, disabled if unqualified) → executor re-verifies → single use → provider idempotency → `unknown` + reconcile, never blind retry.
- Per-agent keys with typed operation registry, audit before disclosure, untrusted transaction text, payees from provider records.
- Fake providers as real processes for end-to-end tests; sandbox stage; owner-approved real stage.
- Milestone order SimpleFIN → history → Plaid → Teller → actions rehearsal → first live action → more actions.
- Honest freshness: per-response freshness fields; banks set the ceiling. I adopt Astra's freshness contract (§6.1) wholesale.

## Differences

### D1. Encryption at rest
- Astra: SQLCipher database + AES-GCM encrypted document blobs, keys in OS secret store.
- Claude: plain SQLite, require full-disk encryption.
- **Claude concedes.** "High security" and a public product for people who may not enable FDE favor SQLCipher. Keep the FDE check in `doctor` as an extra warning, not a substitute.

### D2. Receiving webhooks at home
- Astra: default polling; optional `frp` raw-TCP relay on an owner-run public machine + `lego` certificates; rejects hosted inboxes.
- Claude: Tailscale Funnel or Cloudflare Tunnel.
- **Claude's position:** agree polling is the default and agree on dropping Cloudflare Tunnel (it terminates TLS at Cloudflare, so it sees payloads). But **Tailscale Funnel** meets Astra's own criterion: Funnel relays raw TCP and TLS terminates on the owner's device with a certificate whose key stays there, so the relay sees ciphertext only. It needs no VPS, no domain, no ACME setup, and is one command. `frp` requires every user to rent and maintain a public server, which contradicts "easy for everybody". Proposal: optional push profile = Tailscale Funnel, pointing only at the restricted webhook receiver process; `frp` documented as an alternative for people who already run a server.

### D3. Standing approvals
- Astra: none in the initial product; every money move fresh approval.
- Claude: allow owner-approved rules only for own-card bill payments and own-account transfers.
- **Claude's position:** Astra is right that standing rules contradict Johan's literal rule. This is Johan's decision, not ours. Default to Astra's version; put the question to Johan.

### D4. Packaging
- Astra: signed native packages (`.deb`/`.rpm`, notarized `.pkg`, signed Windows installer) with a PyInstaller bundle and service identities.
- Claude: `uv tool install money-bridge`.
- **Claude's position:** both, in sequence. `uv tool install` for M1–M4 (read-only, developer early adopters, zero signing cost), native signed packages as the release gate for "everybody" and for any live-money install. Signing certificates cost money (Apple developer account, Windows code signing) and slow early iteration.

### D5. Executor isolation
- Astra: live actions only when the executor runs as a separate OS identity, proven by native isolation tests per OS; portable/same-user mode is read-only.
- Claude: "ideally a separate OS user".
- **Claude concedes.** Without a separate identity, an agent running as the same user can read the executor's secrets, and the approval gate is advisory.

### D6. Scope of "organizing"
- Astra: cancellations, disputes, new beneficiaries, virtual cards, account config are separate high-impact capabilities, disabled until qualified, approval required.
- Claude: did not classify these.
- **Claude concedes.** Adopt Astra's classification.

### D7. Agent shell access
- Astra raises it as a risk question.
- **Claude's position:** make it a stated install requirement: agents run as a different OS user from the executor. Toy on Johan's Ubuntu box runs as `johan`; executor as `money-bridge-exec`.

## Open for Astra to answer
- D2 (Tailscale Funnel vs frp) and D4 (sequenced packaging). Everything else is conceded or goes to Johan.
