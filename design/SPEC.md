# Money Bridge build spec

Status: binding build spec, written 2026-10-17 by the build leader from DECISIONS.md, debate/RESOLUTION.md, debate/FABLE-M13.md, astra/DESIGN-astra.md (as amended by debate/astra-r1.md M1–M20 and §3 and debate/claude-r2.md). Where this spec and DECISIONS.md conflict, DECISIONS.md wins; fix this spec. `PRINCIPLES.md` governs how code is written. `features.yaml` is the live list of features, scenarios and statuses.

## 1. Product in one paragraph

Money Bridge is an open-source (MIT), self-hosted program, one owner per install, that runs on Linux, macOS and Windows. It gives AI agents scoped, audited access to the owner's finances through a CLI, an MCP server, an HTTP API and a live event feed. It reads accounts through official aggregators and provider tools (SimpleFIN, Plaid, Teller, Stripe Link CLI, Alpaca MCP, file imports), keeps every observed fact forever in an encrypted local store, stays as fresh as providers allow, and takes money actions only through official APIs, each approved by the owner (provider-native approval or Cosignet). No UI, no tracking or advice logic, not hosted, never automates bank websites.

## 2. Processes and runtime

```
 agent (any OS user)                     owner (OS-authenticated)
  CLI / stdio MCP / HTTP / SSE  + key     moneybridge owner commands
        |                                        |
        v  127.0.0.1:<port>  (bearer key)        v  owner.sock (0600 + peer-uid check)
 +------------------------ core: moneybridge daemon --------------------------+
 | Access boundary -> operation registry -> Evidence store (SQLCipher main db)  |
 | Source host (scheduler, jobs, SimpleFIN/Plaid/Teller adapters, imports)     |
 +-------------------------------|--------------------------------------------+
                                 | exec.sock (peer-uid check: core uid / owner uids)
 +---------------- executor: moneybridge executor ----------------------------+
 | frozen intents, approval adapters, limits, attempts, reconciliation          |
 | private SQLCipher journal; money-capable credentials; official Alpaca MCP    |
 | and Link CLI as private stdio children                                       |
 +-----------------------------------------------------------------------------+
```

- **One console script**, `moneybridge`. Subcommands start the core (`moneybridge daemon`) and the executor (`moneybridge executor`); everything else is a thin client.
- **Language:** Python ≥ 3.12 (`.python-version` 3.13), managed with `uv`. Distribution for M1–M6: `uv tool install git+https://github.com/JohanSardar/money-bridge`. M7 adds PyInstaller bundles and native packages.
- **Reused libraries (pin in `uv.lock`):** FastAPI + Uvicorn (HTTP, SSE via `sse-starlette`, Unix-socket servers), FastMCP (MCP server, Streamable HTTP, stdio proxy, private provider-MCP client), Typer (CLI), Pydantic v2 (all boundary types), `sqlcipher3` (SQLCipher with bundled wheels for all three OSes), `cryptography` (AES-GCM blobs), `httpx` (provider HTTP, mTLS for Teller), `plaid-python` (Plaid), `ofxtools` (OFX/QFX), `webauthn` (py_webauthn, approval verification), `keyring` (macOS/Windows/Secret Service secret adapter), `platformdirs`. Tests: `pytest`, `hypothesis` (unit invariants only).
- **Data directory:** `platformdirs.user_data_dir("money-bridge")` in user mode, `/var/lib/money-bridge` (Linux service mode). Overridable with `--data-dir` / `MONEYBRIDGE_DATA_DIR`. Layout: `core.db` (SQLCipher), `blobs/` (AES-GCM files named by keyed hash), `run/owner.sock`, `run/exec.sock`, `run/daemon.json` (port, pid; no secrets), `executor/journal.db` (SQLCipher, executor-owned, separate key), `config.toml` (non-secret settings).
- **Profiles:** `MONEYBRIDGE_PROFILE` is `production` (default) or `test`. Only `test` may load test-only things: the file secret store, the controllable clock, fake approval trust roots, the FaultyBroker adapter and non-HTTPS provider URLs pointing at loopback. `production` refuses all of them at startup. Test fakes live under `tests/fakes/` and are not part of the installed package.

## 3. Modules and interfaces

Deep modules, small interfaces (Pocock/Ousterhout). Python package `money_bridge` (src layout). A module imports only another module's public interface (its `__init__.py` exports); `tests/unit/test_repo_rules.py` enforces the import boundaries below.

| Package | Module | May import |
|---|---|---|
| `money_bridge.kernel` | shared value types: `Money`, ids, `Clock`, errors, canonical JSON, digests | nothing internal |
| `money_bridge.evidence` | Evidence store | kernel |
| `money_bridge.sources` | Source host and provider read adapters, imports | kernel, evidence |
| `money_bridge.access` | Access boundary: keys, grants, operation registry, doors | kernel, evidence, sources, host, executor (client only) |
| `money_bridge.executor` | Action executor (its own process) | kernel, host |
| `money_bridge.host` | Installation/host adapter: secrets, paths, volume check, service install, setup wizard | kernel |
| `money_bridge.app` | process composition (daemon, executor entry, CLI root) | everything |

### 3.1 Evidence store (`money_bridge.evidence`)

```python
class EvidenceStore:
    def open(path, key: bytes, blobs: BlobStore, clock: Clock) -> EvidenceStore
    def append(batch: ObservationBatch) -> Commit
    def query(spec: Query, grant: Grant) -> Page
    def history(entity_id: str, grant: Grant) -> Page
    def events(after: Cursor | None, grant: Grant, limit: int) -> EventPage
    def annotate(change: AnnotationChange, actor: Actor) -> Revision
    def audit(record: AuditRecord) -> AuditReceipt
    def jobs() -> JobQueue
    def snapshot(destination: Path) -> SnapshotManifest
```

Hides SQL layout, revision identity, atomic checkpoint advance, current projections, blob encryption, migrations, event sequencing and the audit hash chain. `append` commits observations, revisions, projections, relations, coverage, the provider checkpoint and events in **one SQLite transaction**; nothing about a batch is visible until commit. A `Grant` is mandatory on every read; there is no raw connection accessor. Audit append fails closed: if it cannot commit, the caller must not disclose.

Second adapter: same code against a plain-SQLite temp file only in unit tests of pure logic; every E2E runs SQLCipher. `BlobStore` has an encrypted-directory adapter and an in-memory adapter with corruption injection for unit tests.

### 3.2 Source host (`money_bridge.sources`)

```python
class SourceHost:
    def capabilities(connection_id) -> CapabilityReport
    def connect(request: ConnectRequest) -> ConnectProgress        # owner only
    def refresh(connection_id, reason: RefreshReason) -> JobRef     # coalesced, budgeted
    def backfill(connection_id, interval: DateRange) -> JobRef
    def import_file(document: Path, mapping: ImportMapping, account: str) -> JobRef  # owner only
    def run(stop: Event) -> None                                    # scheduler + job worker loop
```

Provider adapter seam (one per provider, inside `sources`):

```python
class ReadAdapter(Protocol):
    provider: str
    def discover(ctx) -> CapabilityReport
    def fetch(ctx, checkpoint: Checkpoint | None, window: Window | None) -> ObservationBatch
    def schedule() -> SchedulePolicy
```

`ObservationBatch` = raw payload bytes (redacted of credentials), retrieval operation, request fingerprint without secrets, observed_at, normalized entity facts, explicit removals (only where the provider states them), coverage claim (`complete_snapshot` | `window` | `partial`) and the next opaque checkpoint. Adapters never write to the store directly and have no money entry point. Real adapters: SimpleFIN (M1), file imports (M2), Plaid (M3), Teller (M4); Link and Alpaca reads arrive as `CapturedResult`s from the executor (M5/M6) and are normalized here.

### 3.3 Action executor (`money_bridge.executor`)

Separate process with its own SQLCipher journal and secret role. Core talks to it only through `exec.sock`.

```python
prepare(agent: AgentRef, proposal: Proposal, request_key: str) -> IntentStatus
status(agent: AgentRef, intent_id: str) -> IntentStatus
abandon(agent: AgentRef, intent_id: str) -> IntentStatus
read_owned_provider(agent: AgentRef, call: ApprovedRead) -> CapturedResult
owner: set_policy, enroll_approver, sync_agent_grants, enable_provider, recover_epoch
```

No public execute, no "mark approved". An internal worker submits only executor-owned, approved, frozen intents. Seams: `ApprovalAdapter.request(frozen) -> ApprovalRef; inspect(ref) -> ApprovalEvidence` and `ExecutionAdapter.prepare(frozen) -> ProviderRequest; submit(req, attempt) -> SubmitOutcome; lookup(attempt) -> LookupOutcome`. Approval adapters: `fake` (test profile; FakeApprovalService), `cosignet`, `link_native`. Execution adapters: `faulty_broker` (test profile), `alpaca_mcp`, `link_cli`, `teller_payments`.

### 3.4 Access boundary (`money_bridge.access`)

```python
invoke(identity: Identity, operation: str, args: dict) -> Result
subscribe(identity: Identity, after: Cursor | None) -> AsyncIterator[Event]
```

Hides key authentication, grant evaluation, audit-before-disclosure, error mapping, pagination and output redaction. **Operation registry:** every operation is declared once (`Operation(name, audience, scope, input_model, output_model, handler, http=(method, path), cli=(group, command))`) and the four doors are generated from it:

- **HTTP:** FastAPI on `127.0.0.1` (default port 8737), `Authorization: Bearer <key>`, JSON, OpenAPI generated. Host/Origin checks reject browser cross-site requests.
- **SSE:** `GET /v1/events/stream`, `Last-Event-ID` resume, bounded per-subscriber queue (1000), slow consumers disconnected with a resumable cursor, key re-validated at least every second and before each released event.
- **MCP:** Streamable HTTP at `/mcp` on the same listener with the same bearer key; tool name = operation name with `.` → `_`. `moneybridge mcp` is a stdio door: a FastMCP proxy to the daemon's `/mcp` using the key from `MONEYBRIDGE_KEY` (or `--key-file`). No database or provider keys in that process.
- **CLI:** Typer, `moneybridge <group> <command> [--json]`, talks HTTP to the daemon with the agent key; human output escapes terminal control characters in all provider text.
- **Owner door:** the same registry's `audience="owner"` operations, served on `run/owner.sock` (Unix socket mode 0600, `SO_PEERCRED`/`LOCAL_PEERCRED` uid ∈ owner uids from config). Owner commands: `moneybridge keys …`, `connect …`, `import …`, `backfill …`, `policy …`, `backup …`, `restore …`, `audit …`, `doctor`, `setup`, `service …`. Windows named-pipe ACL variant is M7.

Error model (stable codes, same on every door): `unauthenticated` (401), `scope_denied` (403), `not_found` (404), `invalid_request` (422), `conflict` (409), `capability_unavailable` (409), `rate_limited` (429, `retry_at`), `freshness_unmet` (warning field, not an error), `approval_pending`, `approval_expired`, `outcome_unknown` (status values, not errors), `locked` (503), `storage_failure` (503), `read_only` (409, restored install). CLI exit codes: 0 ok, 2 invalid, 3 unauthenticated, 4 denied, 5 not found, 6 unavailable/rate limited, 1 other. MCP returns tool errors whose structured content carries the same `{code, message}`.

### 3.5 Installation/host adapter (`money_bridge.host`)

```python
paths(profile) -> Paths
secrets(role: Role) -> SecretStore          # get/put/delete by SecretRef
volume_status(path) -> VolumeStatus         # encrypted | unencrypted | unknown (+ attestation)
service_install(kind, profile) -> InstallReport
setup(wizard_io) -> SetupResult
```

Secret store adapters: `systemd-creds` (Linux; `systemd-creds --user encrypt/decrypt` in user mode, `LoadCredentialEncrypted` + `$CREDENTIALS_DIRECTORY` in service mode), `keyring` (macOS Keychain, Windows Credential Manager, Linux Secret Service; refuses plaintext/null/fail backends), `file` (test profile only, refuses otherwise). Roles: `core` (data key, blob key, read-only source credentials such as the SimpleFIN access URL and Plaid read items), `executor` (journal key, money-capable credentials, approval credentials). No plaintext fallback anywhere; if no adapter works the daemon reports `locked`.

Volume encryption: Linux checks the device-mapper chain of the data dir's filesystem for a `CRYPT-LUKS` target; macOS `fdesetup status`; Windows `manage-bde -status`. Unencrypted → refuse to initialize. Unknown → owner must run `moneybridge owner attest-volume` (recorded in config and audit). Trusted-agent-host opt-in (`moneybridge owner attest-trusted-agent-host`) records that agents run with admin rights on this machine; `doctor` displays it.

## 4. Data model

All amounts are decimal strings with an explicit currency/unit; never floats. Dates that are date-only stay dates. Instants are UTC ISO-8601 with `Z`. IDs are deterministic: `acc_` / `txn_` / `hld_` / `doc_` + base32(sha256(connection_id, provider kind, provider id, generation))[:26], so a re-ingest or restore yields the same IDs.

Core tables (`core.db`):

| Table | Contents |
|---|---|
| `connection` | id, provider, environment (`sandbox`/`production`/`sim`), display name, secret_ref (never the secret), state (`active`/`needs_reauth`/`disconnected`/`error`), capability snapshot, created/disconnected times. Disconnected connections are kept. |
| `source_account` | id, connection_id, provider_account_id, generation, raw type, currency, masked display name, first/last seen. |
| `account`, `account_link` | owner-facing account id and versioned links to source accounts (owner-confirmed cross-provider equivalence only). |
| `observation` | id, connection_id, run id, operation, request fingerprint, observed_at, provider time, payload blob ref + content hash, parser version, coverage claim, error. Immutable. |
| `revision` | id, entity_id, entity_kind (`account`, `balance`, `transaction`, `holding`, `security`, `liability`, `document`, `fact`), observation_id, recorded_at (knowledge time), effective date/time, normalized payload (canonical JSON), payload_hash, supersedes, status (`active`/`removed`), removal reason. Immutable. |
| `sighting` | observation_id, entity_id, revision_id: every time an entity was seen, including identical re-fetches. |
| `current_*` projections | latest active revision per entity plus `presence` (`seen`/`not_seen_in_latest_window`) and `last_seen_at`; rebuildable from revisions. |
| `relation` | kind (`pending_became_posted`, `reversal_of`, `transfer_pair`, `same_transaction`, `possible_match`), from/to entity, evidence, creator (`provider`/`heuristic`/`owner`), state (`proposed`/`confirmed`/`rejected`), revisions. |
| `annotation_revision` | entity_id, namespace, tags, category, note, label (`business`/`personal`), author key id, prior revision, undo-of. |
| `coverage`, `checkpoint` | per connection/account/product: requested and observed interval, completeness claim, gaps, committed provider cursor, last attempt/success, source_updated_at, next eligible refresh, request budget used. |
| `document`, `import_run` | content hash, blob ref, media type, original name, period, mapping id + version, row/page provenance. |
| `job` | durable queue (refresh, backfill, import), coalescing key, attempts, next run. |
| `event` | seq, event id, type, entity ref, account_id, connection_id, data scope, recorded_at, payload. |
| `audit` | seq, at, actor (key id / owner uid / service), operation, decision, params digest, selection manifest (revision ids or high-water mark), result count, response digest, correlation id, prev_hash, hash. |
| `agent_key` | key id, name, secret hash, grant document, created/expires/revoked times. |

Executor journal (`executor/journal.db`): `intent` (frozen canonical bytes, digest, request key, agent, state), `transition` (append-only), `approval` (request id, evidence, verified result), `attempt` (provider idempotency/client id, submitted_at, outcome), `reservation`, `policy_revision`, `agent_grant`, `approver` (pinned credential id + public key), `epoch`.

**Revision rules (core invariants):**
1. A fetched entity whose normalized payload hash equals the **current** revision's hash creates a `sighting`, not a revision. A different hash creates a new revision superseding the current one. A→B→A therefore yields three revisions.
2. Removal only from an explicit provider removal or an owner-confirmed complete snapshot. Absence from a rolling window sets `presence=not_seen_in_latest_window` and emits `transaction.unconfirmed`; it never creates a removal and never claims posting or cancellation.
3. No heuristic merge. Similarity creates a `possible_match` relation (state `proposed`) that the owner can confirm or reject. Provider-supplied links (Plaid `pending_transaction_id`) create `pending_became_posted` relations with creator `provider`.
4. Rows, projections, relations, coverage, events and the provider checkpoint commit together. Plaid pagination restarts from the original cursor on `TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION`; staged pages are discarded.
5. Knowledge time vs effective time: `as_of=<instant>` answers "what did we know at T" using `recorded_at`; `since/until` filter effective dates.
6. Unknown is not zero: missing balances, holdings or limits are `null` with a reason, never `0`.

## 5. Freshness contract

Every account/product item carries:

```
observed_at        when we last received data for it
source_updated_at  when the source says it refreshed (SimpleFIN balance-date, Plaid last_updated), null if unknown
effective_at       date/time of the fact
last_attempt / last_success   health of our connection
coverage           interval and completeness actually returned
freshness_state    current_to_source | stale | offline | unknown
next_refresh_at    our next eligible attempt
```

`freshness_state`: `unknown` before the first success; `offline` when the connection is in an error/needs_reauth state or the last two attempts failed; `stale` when `last_success` is older than 1.5× the schedule interval; otherwise `current_to_source`. Reads accept `max_age_seconds`: if unmet, a refresh is queued, the call waits up to 10 s, then returns existing data with `freshness_unmet: true`.

Schedules (local defaults, all honour provider back-off): SimpleFIN 4×/day (every 6 h ± 20 min jitter) inside a shared budget of 24 requests/rolling 24 h per connection, of which scheduled + backfill use at most 16, manual refresh may use the rest; Plaid and Teller every 2 minutes, doubling on rate-limit/5xx up to 30 minutes and resetting after a success; Link every 5 minutes while connected; Alpaca reconcile every 5 minutes while orders are open. After sleep/resume the scheduler runs one catch-up per connection, not every missed tick. Manual "refresh now" (`sync.request`) is coalesced with any queued job and returns `rate_limited` with `retry_at` when the budget is spent. Plaid webhooks are an optional switch (off by default) that only wake a sync.

## 6. Keys, scopes and audit (FABLE-M13)

Key format `mbk_<key_id>_<secret>` (secret ≥ 256 bits). Store key id + SHA-256 of the secret; constant-time compare. Created only on the owner door; shown once or written straight to a file with mode 0600 (`--out`).

Grant document (versioned, closed set of dimensions; unknown dimensions are rejected so a downgraded binary fails closed):

```json
{"version": 1, "operations": ["read:accounts", "read:transactions"], "accounts": "*", "connections": ["con_..."], "expires_at": "2027-01-01T00:00:00Z"}
```

Operation scopes: `read:accounts`, `read:transactions`, `read:holdings`, `read:documents`, `read:raw` (default off, never implied), `read:events`, `write:annotations`, `propose:transfers`, `propose:payments`, `propose:trades`, `propose:purchases`. Authorization = operation scope ∧ resource account allowed ∧ resource connection allowed, applied identically to lists, single gets, history, counts, events, exports, raw payloads and pass-through. A resource outside the allowlists behaves as `not_found`; a missing operation scope is `scope_denied`. `fields` and `date_range` are reserved and not built.

Operation → scope map: `capabilities.list` any valid key (filtered to allowed connections); `accounts.list`, `balances.list`, `liabilities.list` → `read:accounts`; `transactions.list`, `relations.list` → `read:transactions`; `holdings.list` → `read:holdings`; `documents.list`, `documents.get` → `read:documents`; `entity.history` → scope of the entity kind; `raw.get`, `passthrough.call` → `read:raw` plus the data-kind scope; `events.list`, `events.stream` → `read:events` intersected with the key's data scopes; `sync.request` → any `read:*` on that connection; `annotations.set`, `annotations.undo` → `write:annotations`; `annotations.list` → read scope of the entity; `actions.propose` → `propose:<kind>`; `actions.status`, `actions.list`, `actions.abandon` → the key's own intents only.

Audit: before any disclosure, one durable audit row records actor, operation, decision, params digest, selection manifest, result count, response digest and correlation id; denied and unauthenticated calls are recorded too (unauthenticated floods as bounded per-interval counters). SSE writes one row per released batch before sending it. Rows form a SHA-256 hash chain; `moneybridge audit verify` checks it, and backups include the head. Audit never contains secrets, keys or provider credentials.

## 7. Provider adapters

| Provider | Route | Credentials (role) | Levels |
|---|---|---|---|
| SimpleFIN | protocol over `httpx`: claim setup token → access URL (secret, core role); `GET /accounts?version=2&pending=1&start-date&end-date`; 90-day windows with 5-day overlap; holdings extension captured as holding snapshots when present; `errlist` mapped to connection state | core | sim: ScriptedBank; sandbox: public demo token fetched from the developer page at test time; real: needs owner's token |
| Files | CSV with saved mappings (presets: `generic`, `venmo`, `chase`, `amex`), OFX/QFX via `ofxtools`, PDF archived as document only; file hash + mapping version + row index make re-import idempotent | none | sim |
| Plaid | `plaid-python`: Hosted Link (`/link/token/create` with `hosted_link`, poll `/link/token/get`, exchange public token), `/transactions/sync` cursor loop, `/accounts/balance/get` where enabled, `/investments/holdings/get`, `/liabilities/get` when the Item has the product; errors → connection state; optional webhook receiver with JWT verification | core (read-only Items) | sim: ScriptedBank Plaid API; sandbox: needs owner's Plaid keys |
| Teller | REST over `httpx` with mTLS client cert; Teller Connect enrollment token captured by a local one-shot page serving Teller's official Connect script; accounts/balances/transactions with 10-day overlap; capability discovery from account `links` (payments → Zelle) with exact blockers | core for read-only enrollments; executor when the enrollment carries payments | sim: ScriptedBank Teller API with mTLS; sandbox: needs owner's Teller app |
| Alpaca | official `alpaca-mcp-server` as a private stdio child of the executor, pinned version and tool manifest; reads pass through with filtering, order tools become intents; `alpaca-py` only for gaps (client_order_id lookup, trade_updates) | executor | sim: official server against a fake Alpaca REST server where the server allows a base-URL override, otherwise FaultyBroker MCP with the pinned manifest; paper: needs owner's keys |
| Stripe Link | official `link-cli` (pinned) as a private child of the executor: auth status, accounts/transactions list, spend requests with Link's native approval, MPP merchant payment | executor | sim: contract-tested against the pinned CLI manifest plus a fake Link API or fake executable; real: needs owner's Link account |

Pinned tool manifests (`src/money_bridge/executor/manifests/*.json`): tool name, input schema digest, classification (`read`, `money`, `high_impact`, `denied`), account argument, recovery support. Unknown or changed tools are denied until the manifest is updated. FastMCP proxy settings: no incoming-header forwarding, sampling/roots/elicitation/logging disabled.

## 8. Actions (M5/M6)

Lifecycle: `proposed → frozen → awaiting_approval → approved → submitting → accepted → settled`, with terminal `denied`, `expired`, `abandoned`, `rejected`, and `outcome_unknown → reconciling`. Rules:
- Proposal carries an agent request key; same key + same canonical proposal returns the original intent; same key + different proposal → `conflict`.
- Frozen intent: install id + epoch, intent id, agent, provider, environment, operation + schema version, manifest digest, policy version, exact source account, resolved destination (versioned), amount/currency, fee ceiling, max total, expiry, provider idempotency/client id; trades: symbol/asset id, side, qty or notional, order type (v1: limit only), limit price, time in force. Canonical JSON (sorted keys, no floats, NFC strings, duplicate keys rejected) → SHA-256 digest.
- Approval card (to Cosignet or the fake): action, amount/currency or trade bounds, payee/instrument, account display name, environment, expiry, intent id, digest. Never balances, history, account numbers or rationale.
- Evidence is verified locally with py_webauthn against the **pinned** approver credential (enrolled on the owner door), checking RP ID/origin, user verification, challenge = digest-bound nonce, and expiry. An API "approved: true" is never sufficient.
- Submit: one executor SQLite transaction rechecks grant, policy version, expiry, epoch; reserves limits; consumes the approval; creates the attempt; marks `submitting`; commits; then calls the provider with the frozen arguments and the stable idempotency/client id. Timeout/5xx/crash after send → `outcome_unknown`; reconciliation looks up by client id; an empty lookup never authorizes a resend.
- Limits: owner-set per-action and rolling-24h ceilings per source account and currency; gross exposure including fees, pending, unknown and open orders; atomic reservations; reductions immediate, increases owner-only. No standing approvals.
- High-impact actions (cancel subscription, dispute, beneficiaries, virtual cards, account settings) are listed in capabilities as `disabled` with reason `not_qualified`.
- Restored backups start read-only; actions resume only after `moneybridge owner recover` reconciles and opens a new epoch.

## 9. Test harness

Levels: **sim** (fake providers, approver and broker as real processes), **sandbox** (public sandboxes: SimpleFIN demo; Plaid/Teller sandbox and Alpaca paper once the owner supplies keys), **real** (owner's accounts, read-only). Tests carry `@pytest.mark.sim`, `sandbox` or `real`; `sandbox`/`real` skip with an explicit reason when their credentials are absent.

- `tests/harness/stack.py`: `Stack` starts real processes in a temp data dir with `MONEYBRIDGE_PROFILE=test`: daemon, executor, fakes. Provides `owner(...)` (runs owner CLI), `agent_key(grant)`, and door drivers.
- `tests/harness/doors.py`: `Door` implementations `CliDoor` (subprocess `moneybridge … --json`), `HttpDoor` (httpx), `McpDoor` (FastMCP client over stdio `moneybridge mcp`), each exposing `call(operation, **args) -> Result` with identical semantics. Scenarios that say "every door" are parametrized over all three.
- `tests/harness/clock.py`: controllable clock; the test profile's `Clock` reads an offset from `MONEYBRIDGE_TEST_CLOCK_FILE`; the scheduler ticks every 100 ms in test profile.
- `tests/fakes/scripted_bank/`: one loopback HTTP process (`python -m tests.fakes.scripted_bank --port N --state DIR`) serving SimpleFIN (claim, accounts), Plaid (link token, hosted link, sync, accounts, holdings, liabilities, webhooks) and Teller (mTLS, accounts, balances, transactions, payments) from a scenario script; a control endpoint lets tests change state (add/modify/remove transactions, pending→posted with new id, rate limits, errors, pagination mutation, drop-after-execute). It keeps its own request log as an independent oracle.
- `tests/fakes/fake_approval/`: Cosignet-shaped HTTP service with a software WebAuthn authenticator; control endpoint to approve/deny/expire, replay, or sign with the wrong credential.
- `tests/fakes/faulty_broker/`: broker with an independent effect log; accepts client ids; can execute then drop the response, delay lookup visibility, expire idempotency.
- Crash points: the daemon and executor honour `MONEYBRIDGE_TEST_CRASH_AT=<point>` (test profile only) to `os._exit` at named points (`ingest.before_commit`, `ingest.after_commit`, `submit.before_send`, `submit.after_send`, `submit.after_response`).

Unit tests only for: canonical JSON/digests, revision identity, decimal parsing, grant evaluation, schedule/back-off time math, CSV mapping edge cases.

**Core scenarios that must always hold** (run on every commit): no lost observation; A→B→A revisions; atomic cursor + rows; no heuristic merge; no double submission; unknown never resent; scope denial on every door; audit for every disclosure.

## 10. E2E scenario catalogue

Scenario ids are pytest node ids; `features.yaml` maps them to features and statuses. Files: `tests/e2e/test_<family>.py`, `tests/sandbox/…`, `tests/real/…`, `tests/unit/…`.

**M1 read bridge**
- `e2e/test_store.py`: `test_core_db_is_encrypted_at_rest`, `test_wrong_key_cannot_open`, `test_data_survives_restart`, `test_blob_tamper_is_detected`
- `e2e/test_simplefin.py`: `test_connect_with_setup_token_claims_once`, `test_access_url_never_leaves_secret_store`, `test_accounts_balances_transactions_ingested`, `test_pending_transactions_included`, `test_holdings_extension_captured`, `test_errlist_marks_connection_state`
- `e2e/test_revisions.py`: `test_identical_refetch_records_sighting_not_revision`, `test_a_b_a_creates_three_revisions`, `test_as_of_returns_knowledge_at_time`, `test_pending_absent_from_window_is_unconfirmed_not_removed`, `test_no_heuristic_merge_of_identical_purchases`
- `e2e/test_atomic_ingest.py`: `test_crash_before_commit_leaves_no_rows_or_cursor`, `test_crash_after_commit_has_rows_cursor_and_events`, `test_no_lost_observation_across_restart`
- `e2e/test_doors.py`: `test_same_results_on_every_door[cli|http|mcp]`, `test_error_codes_identical_on_every_door`, `test_openapi_and_mcp_tools_generated_from_registry`
- `e2e/test_keys.py`: `test_owner_creates_key_shown_once`, `test_agent_key_cannot_administer`, `test_expired_key_rejected`, `test_revoked_key_rejected_immediately`, `test_unknown_grant_dimension_rejected`
- `e2e/test_scopes.py`: `test_scope_denial_on_every_door`, `test_account_allowlist_filters_lists_history_counts_events`, `test_connection_allowlist_enforced`, `test_raw_requires_read_raw`
- `e2e/test_audit.py`: `test_every_disclosure_audited_before_response`, `test_denied_and_unauthenticated_calls_audited`, `test_audit_chain_verifies_and_detects_tamper`, `test_audit_never_contains_secrets`
- `e2e/test_events.py`: `test_sse_replay_from_cursor`, `test_last_event_id_resume`, `test_events_filtered_by_grant`, `test_revocation_closes_open_stream`, `test_slow_consumer_disconnected_with_cursor`, `test_pull_pages_on_every_door`
- `e2e/test_refresh.py`: `test_manual_refresh_within_budget`, `test_refresh_beyond_budget_rate_limited`, `test_freshness_fields_present`, `test_max_age_unmet_flag`
- `e2e/test_untrusted_text.py`: `test_injection_text_returned_as_data`, `test_terminal_escapes_neutralized_in_cli`
- `e2e/test_capabilities.py`: `test_capabilities_report_reasons`
- `e2e/test_host.py`: `test_unencrypted_volume_refused`, `test_unknown_volume_requires_attestation`, `test_production_profile_refuses_test_adapters`, `test_no_plaintext_secret_fallback`
- `sandbox/test_simplefin_demo.py`: `test_demo_token_end_to_end`
- `real/test_simplefin_owner.py`: `test_owner_accounts_read_only`
- `e2e/test_packaging.py`: `test_uv_tool_install_from_checkout_runs_demo`

**M2 history**
- `e2e/test_schedule.py`: `test_simplefin_four_times_a_day_with_jitter`, `test_budget_shared_with_backfill`, `test_resume_after_sleep_runs_one_catchup`
- `e2e/test_backfill.py`: `test_backfill_walks_90_day_windows`, `test_gaps_recorded_not_claimed_complete`, `test_backfill_resumes_after_restart`
- `e2e/test_imports.py`: `test_csv_import_with_mapping`, `test_reimport_same_file_is_idempotent`, `test_identical_rows_both_kept`, `test_mapping_change_creates_derived_revisions`, `test_venmo_csv_preset`, `test_ofx_and_qfx_import`, `test_pdf_archived_and_downloadable`, `test_malicious_csv_is_data_only`
- `e2e/test_annotations.py`: `test_annotate_and_undo`, `test_annotation_requires_scope`, `test_annotations_emit_events`
- `e2e/test_relations.py`: `test_possible_match_proposed_not_merged`, `test_owner_confirms_or_rejects_match`
- `e2e/test_backup.py`: `test_backup_restore_round_trip`, `test_restore_is_read_only`, `test_backup_is_encrypted`, `test_restore_detects_corrupt_blob`
- `e2e/test_disconnect.py`: `test_history_retained_after_disconnect`

**M3 Plaid**
- `e2e/test_plaid.py`: `test_hosted_link_enrollment`, `test_sync_cursor_pages_atomic`, `test_pagination_mutation_restarts_from_original_cursor`, `test_removed_transactions_tombstoned`, `test_pending_transaction_id_relation`, `test_polls_every_two_minutes`, `test_rate_limit_backoff_and_recovery`, `test_holdings_and_liabilities_when_entitled`, `test_product_not_entitled_reason`, `test_item_login_required_state`, `test_webhook_off_by_default`, `test_webhook_signature_verified_and_only_wakes_sync`
- `sandbox/test_plaid_sandbox.py`: `test_sandbox_item_sync`

**M4 Teller**
- `e2e/test_teller.py`: `test_connect_enrollment_captured`, `test_mtls_required`, `test_reads_with_ten_day_overlap`, `test_polls_every_two_minutes_with_backoff`, `test_capabilities_show_zelle_blockers`, `test_enrollment_disconnected_state`
- `sandbox/test_teller_sandbox.py`: `test_sandbox_reads`

**M5 actions rehearsal**
- `e2e/test_executor.py`: `test_executor_separate_process_and_journal`, `test_core_cannot_mark_approved`, `test_exec_socket_rejects_unknown_peer`
- `e2e/test_isolation.py` (Linux, needs sudo): `test_agent_user_cannot_read_journal_or_secrets`, `test_agent_user_cannot_reach_exec_or_owner_socket`
- `e2e/test_intents.py`: `test_propose_freezes_and_digests`, `test_request_key_dedupe_and_conflict`, `test_changed_terms_need_new_approval`, `test_approval_for_other_intent_rejected`, `test_unpinned_credential_rejected`, `test_expired_approval_rejected`, `test_denied_approval_terminal`, `test_pending_queue_limit`
- `e2e/test_limits.py`: `test_per_action_limit`, `test_rolling_daily_limit`, `test_concurrent_reservations_atomic`, `test_unknown_outcome_keeps_reservation`, `test_policy_change_while_awaiting_approval`
- `e2e/test_submission.py`: `test_no_double_submission_on_retry`, `test_crash_before_send_not_submitted`, `test_crash_after_send_outcome_unknown`, `test_unknown_never_resent`, `test_reconcile_resolves_by_client_id`, `test_empty_lookup_does_not_authorize_resend`
- `e2e/test_provider_tools.py`: `test_alpaca_manifest_pinned`, `test_alpaca_reads_pass_through_filtered`, `test_alpaca_order_tool_becomes_intent`, `test_hidden_tool_call_rejected`, `test_unknown_tool_denied`, `test_no_header_forwarding`, `test_link_cli_manifest_pinned`, `test_link_reads_archived`
- `e2e/test_approval_adapters.py`: `test_fake_cosignet_round_trip`, `test_link_native_approval_contract`, `test_unqualified_adapter_keeps_actions_off`
- `e2e/test_recovery.py`: `test_restored_backup_cannot_execute`, `test_new_epoch_after_recover`
- `e2e/test_high_impact.py`: `test_high_impact_actions_disabled_with_reason`
- `sandbox/test_alpaca_paper.py`: `test_paper_limit_order_with_fake_approval`

**M6 Link and more actions**
- `e2e/test_link_actions.py`: `test_link_purchase_via_mpp_merchant`, `test_payment_credentials_never_leave_executor`, `test_card_form_checkout_unavailable`
- `e2e/test_teller_zelle.py`: `test_zelle_payment_with_approval`, `test_zelle_idempotency_window`
- `e2e/test_alpaca_actions.py`: `test_limit_order_lifecycle`, `test_partial_fills_within_bounds`, `test_cancel_open_order_needs_approval`

**M7 everybody**
- `e2e/test_setup.py`: `test_setup_wizard_demo_path`, `test_setup_is_resumable`
- `e2e/test_service.py`: `test_systemd_user_service_install_and_restart`
- `e2e/test_second_install.py`: `test_two_installs_share_nothing`
- `e2e/test_packaging.py`: `test_pyinstaller_bundle_runs_without_python`, `test_deb_package_installs`
- macOS (Air, manual-run script `scripts/smoke_macos.sh`): uv install, demo, launchd user agent.
- Windows (GitHub Actions `windows-latest`): uv install, demo read smoke.

## 11. Milestones

Each milestone ends usable. Riskiest unknown first inside each.

| Milestone | Delivers | Riskiest unknown proven first |
|---|---|---|
| M1 read bridge | SimpleFIN → SQLCipher store → CLI/MCP/HTTP/SSE with keys, scopes, audit, replayable events, manual refresh; `uv tool install` | SQLCipher + secret store + three doors from one registry, all in one process start |
| M2 history | scheduler, backfill, CSV/Venmo/OFX/QFX/PDF imports, annotations + undo, possible-match relations, encrypted backup/restore | atomic backfill windows with honest coverage |
| M3 Plaid | Hosted Link enrollment, `/transactions/sync` polling every 2 min with back-off, holdings/liabilities, optional webhooks | sync pagination-mutation restart and atomic cursor |
| M4 Teller | mTLS reads, capability discovery, Zelle blockers, 2-min polling | mTLS client in sim and enrollment capture |
| M5 actions rehearsal | executor process, frozen intents, approval adapters, limits, reconciliation, private Alpaca MCP and Link CLI | WebAuthn verification against pinned credential; crash-safe submission |
| M6 Link and more actions | Link reads + approved MPP purchases, Teller Zelle, Alpaca limit orders | executor-held payment credentials |
| M7 everybody | setup wizard, services (systemd/launchd/Windows), packages, docs, release | per-OS service and packaging |

No live-money test at any milestone (DECISIONS.md). Anything needing the owner's identity (provider accounts, signing certificates, real accounts) is marked `limited` in `features.yaml` with the smallest step the owner needs to take.
