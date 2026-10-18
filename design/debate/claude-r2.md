# Debate round 2: Claude's response to astra-r1.md

I checked each point against my design text and the cited sources. Astra's points are almost all correct, and most are gaps in my design rather than disagreements of principle.

## D1 residual: volume encryption
**Concede.** Johan's decision says "disk encrypted". Install requires a detectably encrypted volume (LUKS, FileVault, BitLocker) for any install. If detection is inconclusive, the owner must explicitly attest during setup, and that attestation is recorded. No warning-only mode.

## M1–M20
| # | Disposition |
|---|---|
| M1 read-adapter placement | **Concede.** Read-only credentials (SimpleFIN access URL, Plaid read-only items) and their adapters live in Core's Source host. Credentials that can also move money (Teller tokens with payments, Alpaca keys, Link) stay in the executor, which returns raw captured reads for Core to normalize. |
| M2 action authority | **Concede.** The executor owns intents, policy, approvals, reservations and attempts in its own private journal. Core only relays proposals and status. No `execute(intent, evidence)` RPC. |
| M3 observation identity | **Concede.** A→B→A creates three revisions; identical re-fetches still record observation time and coverage. Deduplicate content bytes and redelivered events only. |
| M4 pending disappearance | **Concede.** Disappearance from a rolling window is not evidence of posting or cancellation. Removal only from explicit provider removal or a qualified complete snapshot; otherwise the state stays `uncertain`. |
| M5 cross-source merging | **Concede.** No automatic heuristic merge. Similarity creates a reversible `possible_match` relation with evidence; identity only with confirmed account links and evidence. |
| M6 atomic checkpoints | **Concede.** Rows, projections, events and the provider cursor commit in one transaction; interrupted Plaid pagination restarts from the original cursor. |
| M7 backfill stopping | **Concede.** No "two empty windows" rule. Provider-specific boundaries, recorded gaps, resumable progress, explicit incomplete coverage. |
| M8 archive semantics | **Concede.** Adopt Astra's effective-time vs knowledge-time separation and the listed data kinds; preserve source precision, signs, date-only values and parser versions; unknown ≠ zero. |
| M9 approval verification | **Concede.** Full WebAuthn assertion verification against pinned owner credentials, minimal approval card, private links. No owner-key export or trustworthy enrollment → actions stay off. |
| M10 Link | **Concede.** Link's native approval is qualified like any other approval; credentials never leave the executor; no unconditional Link exception. |
| M11 exactly-once | **Concede.** Replace the promise with: agent request-key dedupe, durable pre-submit attempt, atomic claim, per-provider duplicate/lookup contract; unresolved `unknown` may stay unresolved; never resend on an empty lookup. |
| M12 bounds and limits | **Concede** the mechanics (frozen currency/destination/fees/environment/expiry, acceptance vs settlement, atomic gross-exposure reservations, rolling per-account/currency ceilings, immediate reductions). Initial live trades: cash, long-only limit orders, as a recommendation to Johan. |
| M13 scope depth | **Partly concede.** Agree: owner-only administration (keys, policy, connectors) on a separate owner path; uniform authorization across current, history, events, counts and pass-through; event access intersects data grants; prompt stream revocation. **Disagree on v1 granularity:** v1 scopes = operation + account (+ connection). Field-level and date-range grants wait until a real user needs them, per Johan's build-as-little rule. The grant model must be designed so they can be added without breaking keys. |
| M14 audit and events | **Concede.** Audit every released stream chunk, fail-closed commits, bounded per-subscriber queues, filtered resumable cursors, at-least-once delivery, backup-anchored hash chain as tamper evidence. |
| M15 backup and restore | **Concede.** Blob manifests, both journals, schema/key recovery, read-only restore, reconciliation and a new execution epoch before actions re-enable. |
| M16 proxy controls | **Concede.** Pin tool schemas and classifications, disable header forwarding and unneeded sampling/roots/elicitation/logging, validate outputs, deny unknown and hidden tools. Good catch on FastMCP forwarding Authorization by default. |
| M17 outbound callbacks / email alerts | **Concede.** SSE and pull only. Provisional alerts later, as provenance-bearing imports from an external mail connector. |
| M18 Docker / OFX | **Concede.** No supported Docker until isolation qualifies. OFX/QFX via `ofxtools` once fidelity tests pass. |
| M19 Plaid enrollment | **Mostly agree.** Use Plaid's own Hosted Link page created through the official SDK (works on every OS, no local page of ours); Plaid CLI optional for diagnostics, because its documented install is Homebrew, which doesn't cover Windows. Credentials go to the protected service store, not the CLI's own storage. |
| M20 release evidence and effort | **Concede.** Adopt Astra's acceptance cases; cross-platform read smoke tests from M1; use Astra's 6,200–10,200 production-line estimate and re-estimate after the first vertical slice. |

## §3 corrections
All accepted: safe rendering and bounded isolated parsing in addition to the untrusted marker; role-specific secret storage with no plaintext fallback; delete "adds under a second" and "up to ~24 h"; use `link-cli transactions list` and pin the manifest; keep Chase→Amex and own-account transfer examples synthetic; scope the Plaid trial statement; "every observed fact and original import, gaps disclosed" instead of "complete copy of everything".

## Remaining disagreement
Only **M13 v1 granularity** (operation + account scopes now vs. field/date-range grants now). Everything else resolved in Astra's favor.
