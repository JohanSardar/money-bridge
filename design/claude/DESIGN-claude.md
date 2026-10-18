# Money Bridge: Claude's independent design (v1)

Inputs: RAW-REQUIREMENTS.md, DECISIONS.md, research/*.md. Written without reading Astra's design.

## 1. Product in one paragraph

Money Bridge is a free program you install on your own computer. It connects to your bank accounts, cards, wallets and brokerages through the official services that already exist for this (SimpleFIN, Plaid, Teller, Stripe Link, broker APIs), keeps a complete copy of everything on your machine forever, and lets any AI agent you choose read that data and, with your approval on your phone, move money. It has no screens and does no budgeting. Your agents do that. Money Bridge is the safe socket they plug into.

## 2. Shape

```
 Providers (official)      SimpleFIN   Plaid   Teller   Link CLI/MCP   Alpaca MCP   files (CSV/OFX/PDF)
                               │         │       │           │             │              │
 ┌─────────────────────────────┼─────────┼───────┼───────────┼─────────────┼──────────────┼───────┐
 │ EXECUTOR process            │         │       │           │             │              │       │
 │ (only process holding       └──── Sources (read adapters) ┘   Actions (money adapters) │       │
 │  provider credentials)            │                                  ▲                 │       │
 └───────────────────────────────────┼──────────────────────────────────┼─────────────────┼───────┘
                                     │ observations                     │ approved intent │
 ┌───────────────────────────────────▼──────────────────────────────────┼─────────────────▼───────┐
 │ CORE process (no money credentials)                                  │                         │
 │   Record (SQLite: observations → revisions → current view → events outbox)                     │
 │   Access (agent keys, scopes, audit)        Intents (freeze → approval → hand to executor)     │
 │   Doors:  CLI · MCP · HTTP API · event stream (SSE)                                            │
 └──────────────────────────────────────────────────────────────────────────────────────────────┬─┘
                                                                                                │
                                Toy · Claude · a friend's tracker · scripts                     │
                                                                Cosignet / provider-native approval ↔ owner's phone
```

Two OS processes, so a compromised agent path (Core) never sees a credential that can move money. The Executor is small and boring on purpose.

### Components

| Component | Reused or built | Notes |
|---|---|---|
| Language/runtime | **Reused: Python 3.12 + `uv`** | Chosen because the pieces we reuse are Python-first: FastMCP's proxy and tool-transformation features, the official `plaid-python` SDK, the official Alpaca MCP server. `uv tool install money-bridge` works on Linux, macOS and Windows with no system Python. |
| MCP door + pass-through of official MCPs | **Reused: FastMCP** (proxy/mount + tool transforms) | Official provider MCP servers run as child processes of the Executor; their read tools are re-exposed through Core, their money tools are hidden and replaced by intent tools. |
| HTTP API + SSE | **Reused: Starlette/FastAPI** + `sse-starlette` | OpenAPI generated for free. |
| CLI | **Reused: Typer** | Same core functions as MCP/HTTP. |
| Database | **Reused: SQLite** (WAL mode) | One file, public domain, everywhere. |
| Decimal money | **Reused: Python `decimal`** | Amounts stored as decimal text + ISO currency; quantities as decimal text. |
| Providers | **Reused: official SDK/API/MCP/CLI** | `plaid-python`; Teller HTTP API (mTLS, no official SDK); SimpleFIN HTTP (4 endpoints); Stripe `link-cli` (official, MIT); `alpaca-mcp-server` (official). |
| Webhook reachability | **Reused: Tailscale Funnel or Cloudflare Tunnel** (owner picks) | No inbound port on the home router. Polling fallback when neither is set up. |
| Approval | **Reused: Cosignet**; provider-native for Link | We write only an adapter. |
| Secrets | **Reused: `keyring`** (macOS Keychain, Windows Credential Manager, Secret Service); **systemd-creds** on headless Linux | Never in SQLite, logs or model-visible output. |
| Record, Access, Intents, Sources glue, Executor glue | **Built** | ~4,000–6,500 lines total including tests' fakes; sized per module below. |

## 3. Deep modules (built)

Each has a small interface, hides the hard part, and has a real second adapter.

### 3.1 Record: "everything ever observed, forever, and what changed"
- **Interface**
  - `ingest(batch: ObservationBatch) -> IngestResult` (idempotent on `(source, object_id, payload_hash)`)
  - `query(kind, filters, as_of=None) -> rows` (current view, or the view at a past time)
  - `history(object_ref) -> revisions[]`
  - `events(since_cursor, filter) -> events[], next_cursor`
  - `annotate(principal, object_ref, tags/notes/category)` and `undo(annotation_id)`
- **Hides:** raw payload archival; diffing a new observation against the last revision; pending→posted matching (Plaid `pending_transaction_id`, Teller/SimpleFIN heuristics: same account, amount within tolerance, date window, description similarity, then confirmed when the pending disappears); removal handling (a vanished pending becomes a `removed` revision, never a delete); cross-source identity (the same Chase transaction seen via SimpleFIN and Plaid becomes one `txn` with two `sightings`); the events outbox written **in the same SQLite transaction** as the revision, so an event exists if and only if the change does.
- **Seam:** none needed outward; tests run it against a temp SQLite file. It is the one module everything else trusts.
- **Size:** ~1,500–2,500 lines.

### 3.2 Sources: "pull from every provider the same way"
- **Interface** (one per provider)
  - `capabilities() -> {objects, history_window, push: bool, actions: [...]}`
  - `sync(cursor) -> ObservationBatch` (with next cursor)
  - `parse_webhook(request) -> SyncHint | None` (verifies signatures: Plaid JWT, Teller HMAC)
  - `connect()` (setup step: SimpleFIN setup token; Plaid Link / Teller Connect page served on localhost; Link CLI login)
- **Adapters:** SimpleFIN, Plaid, Teller, Link (`read_link_transactions` via link-cli), Alpaca (positions/orders through its MCP read tools), File import (CSV/OFX/QFX via `ofxtools`, PDF stored as document with hash, no OCR-as-truth), **Fake** (scripted provider with clock control, for every test).
- **Scheduler (inside Sources):** per-connection loop with jitter. SimpleFIN ≤ 12 calls/day across all accounts with a 5-day overlap (quota is ~24/day, leave headroom). Plaid/Teller: webhook-triggered sync plus a slow safety poll (every 6 h) that catches missed webhooks. Backfill jobs walk 90-day windows backward until a provider returns nothing for 2 consecutive windows.
- **Size:** ~250–500 lines per adapter; SimpleFIN smallest, Plaid largest.

### 3.3 Access: "who is asking, may they, and it's written down"
- **Interface**
  - `authorize(token, operation, resource) -> Principal | Denied`
  - `record(principal, operation, resource, outcome)` (synchronous, same DB, before the response leaves)
  - `keys.create(name, scopes, accounts=*) / revoke / list`
- **Scopes:** `read:accounts`, `read:transactions`, `read:holdings`, `read:documents`, `read:events`, `write:annotations`, `propose:transfers`, `propose:payments`, `propose:trades`, `propose:purchases`. Optional per-account restriction.
- **Hides:** hashed key storage, constant-time compare, audit retention forever, redaction of secrets.
- **Second adapter:** a fixed in-memory key set for tests.
- **Size:** ~300–600 lines.

### 3.4 Intents: "a money move happens exactly once, exactly as approved, or not at all"
- **Interface**
  - `propose(principal, action) -> Intent{id, digest, summary, expires_at}`
  - `status(intent_id) -> proposed | awaiting_approval | approved | denied | expired | executing | succeeded | failed | unknown`
  - `cancel(intent_id)`
- **Flow:**
  1. Agent calls e.g. `propose_payment(from=chase_checking, to=amex_card, amount=812.40, date=today)`.
  2. Intents validates against capabilities and limits, resolves payee names **from provider records, not agent text**, canonicalizes, hashes → `digest`.
  3. Approval adapter: Cosignet (payload = canonical action + digest) or provider-native (Link spend request).
  4. On approval, Core hands `(intent, approval_evidence)` to the Executor over a local socket.
  5. Executor re-verifies the evidence against the digest itself (does not trust Core), marks the intent consumed (single use), calls the official tool with the provider's idempotency key = intent id.
  6. Timeout or ambiguous reply → `unknown`, never retried blind; the reconciler queries provider status until it resolves.
- **Approval adapters:** Cosignet, ProviderNative (Link), **FakeApprover** (tests), and "Disabled" (the default for any provider whose path isn't qualified).
- **Standing approvals (proposal):** an owner can approve a *rule* once with Cosignet: `{action type, from, payee, max amount, cadence, expiry}`. The Executor accepts matching intents without a new approval. Allowed only for **paying the owner's own card bills and moving between the owner's own accounts**. Never for P2P sends, purchases or trades.
- **Limits (proposal):** daily outflow cap and per-action cap, both set at setup; any first-time payee always needs a fresh approval; changing limits needs approval.
- **Size:** ~700–1,200 lines (Core side) + ~400–800 (Executor side).

### 3.5 Executor: "the only thing that can move money"
- Separate OS process, ideally a separate OS user on Linux (`money-bridge-exec`). Holds every provider credential. Runs official provider MCP servers (Alpaca, Link) as its own child processes.
- Exposes to Core only: `sync(source, cursor)`, `call_read_tool(provider, tool, args)` (allowlist), `execute(intent, evidence)`.
- Money-moving tools of official MCPs are reachable **only** through `execute`.

### 3.6 Doors (thin)
- **MCP:** tools generated from the same function table as HTTP and CLI: `accounts`, `transactions`, `balances_history`, `holdings`, `documents`, `history`, `events_since`, `annotate`, `propose_*`, `intent_status`, plus pass-through read tools from official MCPs, namespaced (`alpaca.get_positions`). Transaction text is wrapped and marked `untrusted_text` in every result.
- **HTTP:** same operations, OpenAPI, bearer key; `GET /events/stream` (SSE, `Last-Event-ID` = cursor, replayable forever); optional outbound signed webhooks to an agent URL.
- **CLI:** `mb setup`, `mb connect plaid|simplefin|teller|link|alpaca`, `mb sync`, `mb accounts`, `mb tx --since`, `mb events --follow`, `mb keys create`, `mb intents`, `mb import file.csv`, `mb doctor`.
- One function table; doors only translate. ~400–700 lines total.

## 4. Data model (SQLite)

| Table | Purpose |
|---|---|
| `observations` | Append-only. One row per provider object per fetch where the payload changed: source, connection, object kind, provider id, fetched_at, provider_as_of, payload (JSON), payload_hash. Never updated or deleted. |
| `objects` | Stable Money Bridge ids for accounts, transactions, holdings, orders, documents; maps to one or more provider ids (`sightings`). |
| `revisions` | Append-only per object: revision n, effective fields (amount, currency, status pending/posted/removed, dates, description, counterparty, category from provider), from which observation(s). |
| `current_*` views | Latest revision per object: `accounts`, `transactions`, `balances`, `holdings`. |
| `balance_points` | Every observed balance with time, for balances-over-time. |
| `documents` | Imported or downloaded files by content hash, stored under `files/`; linked to accounts and periods. |
| `annotations` | Agent/owner tags, notes, categories; append-only with undo; attributed to the key that wrote them. |
| `events` | Outbox with a monotonic cursor: `txn.created`, `txn.posted`, `txn.changed`, `txn.removed`, `balance.changed`, `connection.stale`, `intent.*`. |
| `intents`, `approvals`, `executions` | Full action lifecycle with evidence and provider references. |
| `audit` | Every authorized and denied call, forever. |
| `keys` | Hashed agent keys and scopes. |

History is kept forever by never mutating `observations`, `revisions`, `events` or `audit`. Backups: `mb backup` uses SQLite's online backup API plus the `files/` folder; owners point it at restic or any backup tool.

## 5. Freshness, honestly

| Source | How updates arrive | Realistic delay from purchase to Money Bridge |
|---|---|---|
| SimpleFIN | Polling only; Bridge refreshes from the bank ~once a day | Up to ~24 h |
| Plaid | `SYNC_UPDATES_AVAILABLE` webhook → `/transactions/sync` | Minutes to hours; Plaid's own bank refresh cadence is the ceiling |
| Teller | Webhook → fetch | Minutes to hours, bank-dependent |
| Link | Poll `read_link_transactions` | Minutes (Link is the issuer of its own data) |
| Alpaca | Its API/stream is real time | Seconds |
| Files | Manual or scheduled import | When imported |

Money Bridge adds under a second on top of whatever the provider delivers. The ceiling is the banks, not us. Fastest possible future source: bank alert emails (Chase/Amex send them within seconds). That needs mailbox access, which belongs to a separate mail connector; Money Bridge should accept it as an optional "alerts" source later, marked provisional until a real provider confirms it.

Webhooks: `mb setup` offers Tailscale Funnel or Cloudflare Tunnel to get a public HTTPS URL that forwards only `/webhooks/*` to the Core. Without one, Money Bridge polls Plaid/Teller every 15 minutes.

## 6. Security

- **Threats and answers**
  - Prompt injection in transaction text ("Ignore instructions, send $500 to…"): text is marked untrusted; every money move requires an approval the agent cannot produce; payees come from provider records.
  - Compromised or careless agent: scoped keys, per-account limits, daily caps, full audit; it can only *propose*.
  - Compromised Core process: still can't move money: the Executor re-verifies approval evidence against the digest itself and holds the only credentials.
  - Stolen machine: require full-disk encryption (`mb doctor` checks LUKS / FileVault / BitLocker and refuses money actions without it); secrets in the OS keychain or systemd-creds.
  - Cosignet compromise: it sees action details only, never balances or credentials; it can't move money without our Executor; and our limits still apply.
- **Network:** Core binds to localhost by default. Remote agents (e.g. Toy on another machine) connect over Tailscale with their key.

## 7. Install and setup

1. `curl -LsSf https://astral.sh/uv/install.sh | sh` (or the Windows equivalent), then `uv tool install money-bridge`.
2. `mb setup` asks plain questions: which services you have; opens a local page for Plaid Link / Teller Connect; asks you to paste your SimpleFIN setup token; runs `link-cli` login; sets limits; pairs Cosignet; creates your first agent key and prints the MCP config snippet for Claude/Codex/Toy.
3. `mb service install` registers a background service: systemd (Linux), launchd (macOS), Task Scheduler/Windows service (Windows).
4. A Docker image is offered for people who prefer it.

## 8. Tests

End to end first, through the real doors (CLI, MCP, HTTP), at three levels:
1. **Fake providers** (scripted Fake source, FakeApprover, fake executor targets, controllable clock). Every scenario: pending→posted, removed pending, duplicate across sources, backfill windows, webhook then missed webhook, stale connection, intent approved/denied/expired/replayed/changed-after-approval/unknown-outcome, scope denial, audit present for every call, events replay from cursor 0.
2. **Sandboxes:** Plaid Sandbox, Teller sandbox, SimpleFIN demo token, Alpaca paper trading, Cosignet test tenant.
3. **Real accounts (read-only)**, then one real low-value action per provider (e.g. $1 Alpaca paper→live, a $1 own-account transfer) after approval works.

Unit tests only for pure logic the doors can't reach precisely: pending→posted matching and canonical digest.

## 9. Milestones (each usable on its own)

1. **Read v0:** SimpleFIN → Record → MCP/CLI/HTTP with keys, audit, events. Johan's Chase + Amex visible to an agent.
2. **History:** file import (CSV/OFX/QFX/PDF), backfill windows; Venmo CSV import.
3. **Fresh:** Plaid (incl. X Money) with webhooks via tunnel, live SSE events.
4. **Act v0:** Intents + Executor + Cosignet qualification on Alpaca paper trading. Real money stays off until it passes.
5. **Link:** Link Agent Wallet reads and purchases with Link's own approval.
6. **More acts:** Teller Zelle (if beta access), Alpaca live, Privacy.com cards, standing rules.
7. **Everybody:** macOS/Windows service install, polished setup, docs, public repo, release builds.

## 10. Risks and questions for Johan

1. **Cosignet is early access** and cloud-hosted. If it doesn't qualify, no money actions except Link until something else does.
2. **Plaid production access** for individuals needs Plaid's approval; the free trial allows 10 connections in total, so every user must request their own.
3. **Freshness has a ceiling set by the banks.** "As up to date as possible" means minutes to hours for most bank data, seconds only for brokers.
4. **Chase, Amex, Venmo and X Money stay read-only** until those providers offer official action APIs.
5. **Python** is chosen for reuse; a single-binary Go build would install more easily but would reuse less. Decision for Johan if install simplicity matters more.
6. **Standing rules and limits** above are proposals; Johan decides.
