# Money Bridge design debate: resolution (2026-10-17)

Inputs: astra/DESIGN-astra.md, claude/DESIGN-claude.md, debate/claude-r1.md, astra-r1.md, claude-r2.md, FABLE-M13.md.
**Base design for the merge: Astra's**, with Claude's accepted changes below. Every point is resolved; nothing is waiting on Fable.

## Shared from the start
Python; FastMCP embedded (no gateway) for the MCP door and for running official provider MCPs privately; FastAPI + Typer; SQLite evidence store (observations → revisions → projections → events) kept forever; two trusted processes (Core with no money credentials, executor alone with money-capable credentials); frozen intent → reused approval → executor submits; scoped per-agent keys and audit; fake providers as real processes, then sandboxes, then owner-approved real accounts; build order SimpleFIN → history → Plaid → Teller → action rehearsal → first live action → more.

## Resolved in round 1–2
| Topic | Resolution | Won by |
|---|---|---|
| Encryption | SQLCipher + encrypted blobs + protected keys, AND an encrypted volume required (owner attests if detection is inconclusive) | Astra |
| Webhooks at home | Polling by default; optional Tailscale Funnel to an isolated webhook receiver; frp as an advanced alternative; no Cloudflare Tunnel | Claude (Funnel) |
| Standing approvals | None in v1; every money move needs fresh approval | Astra (Johan may change) |
| Packaging | `uv tool install` for early read-only releases; signed native packages before public or live-money releases | Claude (sequencing) |
| Executor isolation | Mandatory separate OS identity, proven per OS, before live actions | Astra |
| High-impact non-money actions | Cancel, dispute, beneficiaries, virtual cards, account changes: separate capabilities, off until qualified, approval required | Astra |
| M1–M12, M14–M20 | All per astra-r1.md (read adapters in Core; executor owns the action journal; A→B→A revisions; no heuristic merges; atomic cursors; honest backfill; full data semantics; full approval verification; Link qualified like others; no exactly-once promise; atomic limits; audited streams; safe restore; locked-down proxy; SSE/pull only; no Docker yet; Plaid Hosted Link via SDK; Astra's acceptance cases and 6.2k–10.2k line estimate) | Astra |
| M13 key scopes | v1 = operations (data kind in the name) + account + connection allowlists + expiry; `read:raw` separate and off by default; `fields`/`date_range` reserved for later | Fable (Claude's position, with Astra's raw-scope safeguard) |

## For Johan
1. Standing approvals: keep "none" or allow a narrow rule later?
2. Does any agent (Toy) have sudo/admin on the machine running Money Bridge?
3. First live pilot: which account/route, per-action and daily limits, trading limited to cash long-only limit orders?
4. Enable Tailscale Funnel for live bank updates, or poll?
