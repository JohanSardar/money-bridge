# Money Bridge — independent Astra design

**Author:** Astra. **Date:** 2026-10-17. **Status:** proposed architecture, not an implementation or a security certification.

**Audience and purpose:** Johan and the implementation team; choose the smallest system that preserves financial evidence and makes approved actions enforceable. I read [RAW-REQUIREMENTS.md](../RAW-REQUIREMENTS.md) first, then [DECISIONS.md](../DECISIONS.md). Those decisions govern this design. I consulted selected research as leads and checked the primary sources linked below. I did not read the other designer's directory or the debate directory.

External capability claims are documentation findings as of this date, not tests against Johan's accounts. Polling intervals, interfaces, estimates, limits, and release gates below are **design choices** unless identified as provider facts. Exact dependency versions must be locked and tested before implementation releases; this document does not invent a tested version matrix.

## 1. Product definition

Money Bridge is a free, open-source program you run on your own computer to give the AI assistants you choose access to your finances. It connects to supported banks and financial services, saves the information it receives and the statements you import, and keeps that history even when the original service no longer has it. Your assistants can use it to organize records, build trackers, or help you make decisions. Where a service officially allows payments or trading, an assistant can prepare the action, but you approve each money move through an existing approval service before it happens. You choose what each assistant can see and request; Money Bridge keeps a record of their access.

The repository is standalone and MIT-licensed. One owner, one installation, one authoritative executor. The supported desktop/server targets are Linux, macOS, and Windows. No budgeting engine, investment advice, net-worth calculator, bank-site automation, hosted Money Bridge account, or separate agent gateway.

## 2. Decisions that shape the system

1. **Archive evidence, not just current rows.** An API response is an observation of a source at a time. Provider deletions and corrections never erase what Money Bridge already observed.
2. **Expose current facts and their uncertainty together.** Every response reports source, observation time, source update time when available, and coverage. A successful poll of yesterday's data is not a fresh balance.
3. **Reuse provider tools before wrapping their HTTP endpoints.** Official MCPs and CLIs remain unmodified subprocesses where they fit. Use official SDKs for missing ingestion/streaming contracts, and documented REST through an existing HTTP client when no suitable SDK exists. Build normalization, persistence, policy, and enforcement glue only.
4. **An approval must control the actual execution path.** A friendly MCP confirmation is insufficient when the caller can invoke a trading tool or read its secret directly.
5. **Capabilities are per connection and account.** An installed adapter does not imply provider admission, bank coverage, product entitlement, or a qualified approval flow. Return a reason for every unavailable capability.
6. **Keep the complete local data layer useful while actions are unavailable.** A failed Cosignet qualification, missing beta access, or offline executor must not block archival reads.

### Initial coverage

| Source/account | Read and archival route | Action policy |
| --- | --- | --- |
| Chase and Amex | SimpleFIN first; Plaid for eligible products; owner exports for missing history | Read-only by default. Chase Zelle is a separate, conditional Teller capability. |
| Venmo | Owner-exported CSV/statements; aggregator data only if the actual enrollment supports it | No personal payment API assumed; read-only. A bank's Venmo entry is not the wallet's complete ledger. |
| X Money | Plaid candidate per the binding decision; verify listing and product access during enrollment; otherwise imports | Read-only. Do not promise availability or complete history from an institution name alone. |
| Zelle | Activity of the originating bank, plus receipts/imports | Teller beta only after account-level discovery, admission, approval qualification, and reconciliation tests. Zelle is not another balance-bearing account. |
| Stripe Link | Official `stripe/link-cli` MCP/CLI; supported account/transaction reads | Provider-native approval first. Only complete a purchase over an official supported merchant API; keep payment credentials private. |
| Alpaca | Official `alpacahq/alpaca-mcp-server`; `alpaca-py` for stream/history gaps | Paper first; live orders require qualified Cosignet unless an adequate native approval becomes available. |
| Other brokers, including Schwab | An official API with owner-granted access, or imports | Capability stays disabled until the exact official endpoint, enrollment, approval, and recovery contract are qualified. No generic brokerage promise. |

Bills, due dates, recurring-payment descriptions, investments, credit scores, and tax documents are **data kinds**, not invented capabilities. Store them where a source or import supplies them. Missing is `unavailable` or `unknown`, never zero. In particular, liabilities are not a credit score, a recurring charge is not authority to cancel a subscription, and a merchant refund API is not automatically a consumer refund API.

## 3. Architecture and reuse inventory

```text
 UNTRUSTED AGENT OS USER                  OWNER
   CLI / stdio MCP / HTTP client          setup terminal; phone approval
          | scoped Money Bridge key              |
          v                                      | provider / Cosignet UI
 +---------------- moneybridged -----------------+-----------------------+
 | Access: authenticate -> authorize -> durable audit -> dispatch         |
 |                                                                       |
 | Archive queries <---- Evidence store <---- Source host                 |
 |        |              SQLCipher SQLite       |                        |
 |        |              encrypted documents    +-> official read tools   |
 |        +-> HTTP / MCP responses               +-> SDK / REST reads     |
 |        +-> persisted event feed               +-> imports              |
 |                                                                       |
 | Action proposal / status -------- private, authenticated IPC -----+    |
 +------------------------------------------------------------------|----+
             distinct service identity; no trading/payment keys      |
                                                                    v
 +---------------- moneybridge-executor -------------------------------+
 | Freeze intent -> enforce limits -> request/verify reused approval   |
 |                       -> durable submission record -> execute       |
 | Private SQLCipher journal, approval receipts, secret-store access   |
 | Official Alpaca/Link MCPs/CLIs with powerful credentials live HERE   |
 | Allowlisted reads with inseparable credentials also execute HERE   |
 +------------------+---------------------------------+----------------+
                    | outgoing official API           | outgoing poll
                    v                                 v
             bank / broker / merchant             Cosignet / provider

 OPTIONAL WEBHOOK TRANSPORT (financial TLS terminates at home):
 provider -> owner's public frps TCP relay -> outbound frpc connection
       -> restricted local HTTPS receiver -> verified wakeup -> Source host
       No route to CLI/MCP/HTTP data API, executor, or filesystem.
```

These are two trusted service processes, plus short-lived provider subprocesses. The optional webhook receiver is a separately restricted process; its code belongs to Source host. They are modes of one Money Bridge distribution, not independent products. The diagram's IPC uses a Unix-domain socket on Linux/macOS and an ACL-protected named pipe on Windows. Framework adapters hide the wire format. The services run without administrator privileges after installation.

Provider reads return through Source host into the Evidence store. Action-state events return from the executor into that store through an idempotent outbox. Requests and results over these internal links carry the originating identity and correlation ID; an unauthenticated local message cannot impersonate an owner or agent.

### Reused components

| Mark | Exact component | Purpose and boundary |
| --- | --- | --- |
| **REUSED** | [PrefectHQ/FastMCP](https://github.com/PrefectHQ/fastmcp), its [proxy provider](https://gofastmcp.com/servers/providers/proxy), and [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | MCP server/client, provider composition, transport handling. Embed the library; do not deploy a gateway. Policy wraps discovery and invocation. |
| **REUSED** | [stripe/link-cli](https://github.com/stripe/link-cli) | Link authentication, MCP/read commands, spend requests, approved API purchases. Run its locked official distribution privately. |
| **REUSED** | [alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server), [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py) | Official trading tools; SDK only for stream/backfill/recovery gaps the MCP does not expose adequately. |
| **REUSED** | [Plaid CLI](https://plaid.com/docs/resources/cli/), [plaid/plaid-python](https://github.com/plaid/plaid-python) | Official enrollment/diagnostic commands where supported; SDK for explicit cursor ownership and atomic archival ingestion. Do not assume the CLI's private cursor storage has our transaction contract. |
| **REUSED** | [SimpleFIN protocol](https://www.simplefin.org/protocol.html), [Teller API](https://teller.io/docs/api), `httpx` | No new aggregator client framework. Small protocol adapters over documented HTTPS. Teller mTLS uses the existing TLS stack. No suitable official Python SDK is assumed. |
| **REUSED** | SQLite through [SQLCipher Community Edition](https://www.zetetic.net/sqlcipher/) and [coleifer/sqlcipher3](https://github.com/coleifer/sqlcipher3) | Embedded transactions, indexes, backup API, database encryption. The Python binding is a small dependency, not a claim that it is a large foundational project. |
| **REUSED** | `cryptography` AES-GCM; OS secret stores; `keyring` where its backend fits | Encrypt document blobs and use OS-protected keys. No custom cipher or plaintext keyring fallback. |
| **REUSED** | [Cosignet REST API](https://cosignet.com/docs); [Duo Labs py_webauthn](https://github.com/duo-labs/py_webauthn) for receipt verification if qualified | Hosted approval ceremony and existing signature verification code. No Money Bridge passkey enrollment, approval page, push app, or WebAuthn ceremony. |
| **REUSED** | FastAPI, Pydantic, Uvicorn, Typer; Python `asyncio`, `csv`, `decimal` | HTTP schemas, validation, service runtime, terminal commands, parsing. Use SQLite-backed jobs, not a separate task broker. |
| **REUSED** | PyInstaller; systemd, launchd, Windows Service Control Manager; restic | Native distribution, process supervision, encrypted owner-controlled backups. |
| **REUSED**, optional | [fatedier/frp](https://github.com/fatedier/frp), [go-acme/lego](https://github.com/go-acme/lego) | Opaque TCP relay and local certificate issuance/renewal for private-data webhook transport. Not an agent gateway. |

Official CLI and SDK are alternatives for a given operation, not two competing authoritative sync loops. A provider manifest records which implementation owns that operation and why a lower-level API was necessary. Permit selective MIT code/test borrowing from the approved research candidates with attribution; do not adopt their application model. No Breadbox core, dlt, Postgres, Redis, Kafka, accounting engine, or plugin marketplace.

Money Bridge's own source is MIT. Preserve each reused dependency's license, notices, and redistribution conditions; bundling a tool does not relicense it. Audit the locked distribution, including native binaries, rather than relying on a repository's headline license.

### What we build

Estimates are hand-written production Python/SQL/configuration lines for the first useful set of adapters, excluding upstream code, tests, fixtures, and documentation. They are estimates, not a reason to omit a safety property.

| Mark | Module | Estimated size |
| --- | --- | --- |
| **BUILT** | Evidence store: observations, revisions, queries, provenance, event/audit persistence | 1,500–2,200 lines |
| **BUILT** | Source host: adapter contracts, scheduling, imports, normalization, webhook intake | 1,500–2,500 lines, including initial provider glue |
| **BUILT** | Action executor: frozen intents, approval adapters, limits, submission and recovery | 1,800–3,000 lines |
| **BUILT** | Access boundary: shared operations, scopes, audit interception, three transport adapters | 700–1,200 lines |
| **BUILT** | Installation/host adapter: wizard, secret-store binding, service identities, packaging configuration | 700–1,300 lines |

Approximately **6,200–10,200 production lines**, plus substantial integration tests. A SimpleFIN-only read release should be much smaller. Cross-platform credential isolation and action recovery account for real complexity; “mostly assembly” does not make them disappear. Provider SDKs, protocol stacks, approval UI, cryptography, database engine, and installers' machinery remain reused.

## 4. Deep modules and their seams

The public interfaces below are design pseudocode, not promises about a vendor SDK. A deep module hides a coherent source of complexity behind a small contract. Do not create a class per SQL table or a universal financial-operation DSL.

### 4.1 Evidence store

```python
append(batch: ObservationBatch, checkpoint: Checkpoint | None) -> Commit
query(spec: Query, access: DataGrant) -> Page
history(entity: EntityRef, access: DataGrant) -> Page
events(after: Cursor, access: DataGrant) -> EventPage
annotate(change: AnnotationChange, access: DataGrant) -> Revision
snapshot(destination: BackupSink) -> SnapshotManifest
```

**Hides:** SQL layout, atomic cursor advances, revision identity, raw-payload deduplication, current projections, blob encryption, migrations, and event sequencing. `append` commits observations, projections, a checkpoint, and their events together. Audit append is an internal variant of the same persistence primitive. A query grant is mandatory; adapters cannot hand out a database connection.

**Seam:** immutable observation batches in; scoped, paginated facts out. Financial calculations and provider networking stay outside. The small mutable projections are rebuildable from the immutable archive.

**Second adapter:** production SQLCipher and a stock SQLite temporary-file backend run the same schema/contract tests. The latter is only for synthetic fixtures. Real encryption, crash, and backup tests still run against SQLCipher; an in-memory mock cannot prove durability. Blob storage has an encrypted-directory implementation and an in-memory fixture implementation with corruption injection.

### 4.2 Source host

```python
capabilities(connection: ConnectionRef) -> CapabilityReport
connect(request: OwnerConnectRequest) -> ConnectProgress
refresh(connection: ConnectionRef, request: RefreshRequest) -> JobRef
backfill(connection: ConnectionRef, interval: DateRange) -> JobRef
import_file(document: DocumentRef, mapping: ImportMapping) -> JobRef
```

**Hides:** official-tool lifecycle, authentication handoffs, rate budgets, polling, webhooks, provider cursors, retries, field mapping, and history coverage. A refresh is asynchronous and may report “upstream data unchanged.” It never fabricates freshness.

**Seam:** each source implements `discover`, `fetch(checkpoint, window)`, and optional `watch`; it emits `ObservationBatch` with an opaque continuation, coverage evidence, and explicit removals where supported. It has no approval or money-execution entry point. Providers may decline streaming or backfill without pretending to support them.

**Real adapters:** SimpleFIN HTTPS, Plaid SDK, Teller HTTPS, official MCP read capture, and CSV import. **Second/test adapter:** `ScriptedBank`, a real loopback HTTP/MCP process with independent fixture state. It produces pending/posting ID changes, partial pages, historical corrections, disconnected accounts, duplicate webhooks, and configurable clock/rate-limit behavior. It is not a mock of internal functions.

### 4.3 Action executor

```python
prepare(grant: ActionGrant, proposal: Proposal, request_key: str) -> IntentStatus
status(grant: ActionGrant, intent_id: str) -> IntentStatus
abandon(grant: ActionGrant, intent_id: str) -> IntentStatus
reconcile(intent_id: str) -> IntentStatus       # internal worker only
read_owned_provider(grant: DataGrant, call: ApprovedRead) -> CapturedResult
```

**Hides:** privileged credentials, exact request serialization, approval state, receipts, policy reservations, durable submission attempts, and provider outcome lookup. There is deliberately no public `execute(arguments)` method and no public “mark approved” operation. Its internal worker submits only its own approved immutable intents. `abandon` withdraws an unsent proposal; cancelling an already placed order is a distinct provider action.

**Seams:** `ApprovalAdapter.request(frozen) / inspect(receipt_ref)` and `ExecutionAdapter.prepare / submit / lookup`. Provider-native Link and Cosignet are distinct approval adapters. Alpaca MCP and Link CLI are distinct execution adapters; Teller REST is another. `read_owned_provider` exists only for safe reads when the same provider credential can also move money. It does not accept arbitrary URLs or tool names.

**Second/test adapters:** a separate `FakeApprovalService` signs test receipts using a test credential; a `FaultyBroker` records independent effects, accepts idempotency keys, and can drop the response after executing. Production configuration cannot load these adapters or trust their test keys. Their contract tests prove behavior through real IPC/network boundaries.

### 4.4 Access boundary

```python
invoke(identity: AuthenticatedAgent, operation: Operation, args: object) -> Result
subscribe(identity: AuthenticatedAgent, after: Cursor, filter: Filter) -> Stream
```

**Hides:** key authentication, resource and field scopes, authorization at discovery and execution, request IDs, audit-before-disclosure, transport errors, pagination, and response redaction. Operations are a finite typed registry. No arbitrary SQL, shell, filesystem, credential, or HTTP-forwarding operation.

**Seam:** transport supplies authenticated identity and validated input; one dispatcher applies the policy and calls the other modules. CLI does not bypass the daemon to open SQLite. Audit hooks cover internal provider pass-through as well as normalized queries.

**Real adapters:** Typer CLI over the local API, FastMCP over stdio/Streamable HTTP, and FastAPI HTTP. Tests issue the same scenario through all three and compare semantic results. An in-process test caller exercises the same dispatcher, not a separate testing code path.

### 4.5 Installation and host adapter

```python
provision(profile: InstallProfile) -> HostReport
secret(ref: SecretRef, role: ServiceRole) -> SecretHandle
launch(component: LockedComponent, role: ServiceRole) -> ProcessHandle
health() -> HostReport
```

**Hides:** native secret stores, service users, private directories, sockets/pipes, process launch, locked dependency assets, and restart behavior. Thin platform code must not decide financial policy. Runtime secrets are passed through private handles or tightly scoped child environments only when an upstream tool requires them.

**Real adapters:** Linux systemd/credential store; macOS launchd/Keychain; Windows SCM/DPAPI. A temporary-directory host adapter with fake secret handles is the second adapter for setup tests; native VM tests prove ACL and identity isolation. Read-only portable mode is an explicit profile, not a silent fallback for live trading.

## 5. The local copy

Use **one main SQLCipher SQLite database**, an encrypted blob directory, and a **separate executor SQLCipher journal** owned by its service identity. The second journal is required to keep action authority outside the read daemon's write privileges. Copy redacted action events into the main archive using stable IDs; the executor journal remains authoritative for approval, spend reservations, and attempts.

### 5.1 Records

| Record | Important fields and semantics |
| --- | --- |
| `connection` | Local ID, provider, environment, institution, credential reference, consent/capability versions, state. Never a token. Keep disconnected connections. |
| `source_account` | Connection ID + provider account ID + identity generation; raw type/currency, masked display identity, first/last seen, closure evidence. Reconnection aliases are explicit. |
| `account` / `account_link` | Stable owner-facing account ID; versioned mappings to source accounts. The owner confirms cross-provider equivalence. Last four digits and a name alone cannot merge accounts. |
| `observation` | Source/run ID, retrieval operation, request fingerprint without secrets, observed time, provider time if supplied, payload hash, raw blob reference, parser/schema version, coverage/completeness, error details. Immutable. |
| `entity_revision` | Entity kind, source identity, revision ID, observation ID, provider version if any, effective time, recorded time, normalized payload, supersedes link, lifecycle/status, tombstone reason. Immutable. |
| `balance_observation` | Source account, balance kind (`ledger`, `available`, `credit_limit`, `buying_power`, etc.), exact decimal amount, unit/currency, source-as-of and observed-at, completeness. Equal amounts at different source times are still observations. |
| `transaction_revision` | Source transaction ID, account, pending/posted/removed status, exact amount and currency, debit/credit meaning, authorized/posted date, description, provider category, related pending ID and reversal references where supplied. Implemented as a typed projection of revisions. |
| `holding_snapshot` / `holding_line` | Account, security ID, quantity, cost basis and quote/value if supplied, currency, timestamps, completeness. A missing line means zero only for an explicitly complete snapshot. |
| `security_revision` | Provider IDs plus ISIN/CUSIP/ticker/exchange where supplied; asset class, contract details. Ticker alone is not identity. Keep corporate-action data as source facts. |
| `document` / `import_run` | Content hash, encrypted blob, original filename/media type, account/statement period, origin, import time, parser/mapping version, extraction status; per-row/page references. Preserve original CSV/PDF/OFX bytes. |
| `relation` | `supersedes`, `pending_became_posted`, `reversal_of`, `same_account`, `same_transaction`, and `possible_match`; source/evidence, confidence, creator, revisions. Hypotheses never silently delete evidence. |
| `annotation_revision` | Entity, namespace, tags/category/note/business-personal label, author, prior revision. Local overlay separate from provider facts. Undo appends a compensating revision. |
| `coverage` / `sync_checkpoint` | Per source/account/product and interval: requested range, observed bounds, completeness claim, unresolved gaps, committed cursor, last attempt/success/upstream update, next eligible refresh. |
| `job`, `event`, `audit` | Durable work queue, replayable notifications, every access and action record. No TTL for financial history or audit. |
| Executor `intent`, `approval`, `attempt`, `reservation`, `policy_revision` | Frozen payload and digest; trusted approval evidence; submission/recovery journal; reserved limits; owner-managed policy versions. Mutable status columns are projections of append-only transitions. |

Bills/due dates, liabilities, provider-supplied recurring series, credit-score reports, and tax metadata use typed `entity_revision` payloads and document links until dedicated query indexes are useful. Retain unsupported provider fields in the raw observation. This avoids pretending every institution has the same schema while keeping the common data usable.

**Numbers and dates:** preserve original decimal strings. Normalize money and security quantities with `Decimal`, never binary floating point. Monetary requests use explicit currency and its supported scale; reject rather than round an unrepresentable action. Read amounts retain source precision, including non-fiat units. Normalize account-value direction and retain original sign/type so liabilities and Plaid's sign conventions do not invert cash flow. Preserve date-only values as dates; do not invent midnight UTC. Record UTC instants and source timezone when actually known.

### 5.2 Revisions and reconciliation

Example, with illustrative values:

```text
10:00 observed P17 pending  -18.00
next day: provider removes P17 and adds T91 posted -21.00
later: T91 corrected to -20.00
later: provider explicitly removes T91

Stored: P17 revision 1; P17 removal; T91 revisions 1, 2, removal;
        explicit pending->posted relation; every supporting observation.
```

Plaid represents pending-to-posted transitions with a removal and addition, potentially on different pages, and may supply `pending_transaction_id`. Commit the complete sync update before projecting those relations. A missing match remains unresolved. [Plaid transaction states](https://plaid.com/docs/transactions/transactions-data/).

Teller can retain IDs across posting or issue a new one when matching fails; use its date-overlap guidance and preserve both records when uncertain. SimpleFIN has no universal deletion feed. **Disappearance from a rolling window is not a deletion.** Record absence/uncertainty; only emit a source tombstone from explicit removal or a qualified complete-snapshot contract. A disappeared pending charge can be marked unresolved or no longer observed without claiming it posted or was cancelled. [Teller transaction contract](https://teller.io/docs/api/account/transactions).

Repeated delivery of an identical payload does not create a new financial revision, but retains its fetch observation and audit trail. A later return to an old value is a new revision: deduplicate against the prior current state or stable provider event ID, not against every historical hash. Keep normalized parser corrections as new derived revisions linked to the original observation; never rewrite the original interpretation invisibly.

Current views select the latest authoritative source state, considering provider sequence/version where available. Late, old webhooks wake a fresh API fetch rather than replacing current facts directly. APIs expose both “effective on date D” and “what we knew at time T,” with explicit limitations where a source supplies no effective timestamp.

**Multiple feeds:** designate one primary transaction source per linked account and covered interval; retain every secondary source. Explicit gaps can be filled by another source or imports. Overlapping candidates require a source-provided relation or an owner-confirmed match; amount/date/merchant similarity only creates `possible_match`. The default combined view exposes unresolved overlaps and provenance instead of confidently double-counting or silently merging them. Do not blend balances from multiple feeds into a synthetic balance. Source precedence is a reversible, versioned choice, not evidence destruction.

Two legs of an own-account transfer remain separate account transactions linked by a transfer relation; they are not duplicate observations of one row. Likewise, orders, fills, cash movements, and holdings snapshots are distinct facts with references between them. Money Bridge supplies these links and raw amounts; agents decide how to calculate spending, performance, taxes, or net worth.

### 5.3 Atomic ingestion and backfill

1. A durable job fetches a page or complete snapshot with a recorded starting checkpoint. Each raw response is encrypted and content-addressed before its reference is committed.
2. For multi-page logical updates, stage pages until complete. On Plaid's pagination-mutation error, restart from the update's original cursor; do not advance halfway. A crash can replay the staged run without duplicate revisions. [Plaid sync errors](https://plaid.com/docs/errors/transactions/).
3. One SQLite transaction appends normalized revisions, updates current projections, advances the committed checkpoint, and creates events. Acknowledging completion before this commit is forbidden. Orphan blobs from a crash are safe to reclaim only if no immutable record references them.
4. Recent refresh has priority over historical work. Backfill uses the same adapter and archive contract with a separate range checkpoint and rate budget. Empty responses record uncertainty; they do not prove a lifetime ledger is complete.
5. SimpleFIN uses windows no larger than 90 days, with overlapping boundaries and a total request budget within its published limits. Walk older windows until the provider's stated limit, a confirmed boundary, or a configured stop condition; report any unproven gap. [SimpleFIN developer guide](https://beta-bridge.simplefin.org/info/developers).
6. Plaid requests the longest permitted history at enrollment and waits for historical readiness; the documented Transactions request maximum is 730 days, with institution-specific availability. Teller and broker history are paginated to their actual limits. “Requested two years” is not “received two years.” [Plaid Transactions API](https://plaid.com/docs/api/products/transactions/).
7. CSV imports use explicit saved mappings for account, sign, unit, date, and transaction ID. File hash plus mapping version plus row location makes re-import safe without merging two identical-looking purchases. Validate statement opening/closing totals when present and expose discrepancies as import warnings.
8. PDFs and tax documents are archived immediately. Initial releases do not build a statement OCR/LLM system. An agent or later reusable parser may submit extracted records with page/row evidence and extraction identity; these remain derived observations until confirmed. Imported data cannot generate executable instructions.

### 5.4 Keeping history forever

“Forever” means no automatic retention expiry and no loss through disconnect, provider correction, upgrade, or backfill. It cannot mean reconstructing revisions a provider never exposed between polls. Keep raw financial observations, imported originals, normalized revisions, approvals, and audit entries. Redact authentication material before archiving provider envelopes; record that redaction instead of calling such an envelope byte-for-byte original. Payment credentials are secrets, not archival financial records.

Use WAL, short transactions, one writer per database, integrity checks, and additive versioned migrations. Projections/indexes can be replaced; immutable evidence cannot. Compression and deduplicated encrypted blobs reduce space without dropping versions. Report disk pressure early; if durable storage fails, stop ingestion/disclosure/action submission rather than claiming to have logged it.

Use the SQLite backup API for consistent snapshots, with an immutable blob manifest, executor journal snapshot, schema versions, hashes, and restore instructions. Reuse restic to copy encrypted snapshots to an owner-controlled external disk or another owner computer; no cloud archive by default. Keep recovery material separately protected. A backup of ciphertext without a recoverable key is not a usable backup.

Restore starts **read-only with execution disabled**. Reconcile outstanding provider actions and establish a new installation epoch before live actions resume. Never replay pending submissions from an old backup. Reconnect expired tokens rather than embedding live provider secrets in routine backups. An explicit owner-only destructive export/delete/reset procedure may exist; ordinary agents cannot erase retained history or audit.

## 6. Freshness and home-machine webhooks

### 6.1 Freshness contract

Every account/product response includes:

```text
observed_at                 when we received the data
source_updated_at           when the source says it refreshed; null if unknown
effective_at                time/date of the particular financial fact
last_attempt / last_success health of our connection, not proof of new bank data
coverage / completeness     what interval and products were actually returned
freshness_state             current_to_source | stale | offline | unknown
next_refresh_at             our next eligible attempt
```

A requested `max_age` can trigger a job, wait briefly, or return `freshness_unmet` with the existing data. It cannot force a bank to update. Freshness is per product: a recent transaction sync does not make holdings or a credit report recent.

| Source | Arrival and proposed schedule | Realistic latency and limits |
| --- | --- | --- |
| **SimpleFIN** | Poll every six hours with jitter; reserve request capacity for manual refresh/backfill. All workers share one quota budget. Fetch pending if supported and overlap at least five days. | Bridge is intended for daily data, expects at most 24 requests/day, and limits each date window to 90 days. Practical bank-to-local delay is often hours to a day or longer; four daily local polls do not make upstream live. |
| **Plaid Transactions** | `SYNC_UPDATES_AVAILABLE` wakes `/transactions/sync`; initialize sync once after linking. With no webhook transport, check the cursor every 15 minutes, adapting to rate limits. `/transactions/refresh` only where enabled and within the owner's cost budget. | Official baseline is typically one to four upstream checks per day. A webhook can arrive quickly **after Plaid has the change**; bank-to-agent delay can still be hours. Optional refresh improves the opportunity, not a universal SLA. |
| **Teller** | `transactions.processed` and connection-state events wake an API fetch. A 15-minute fallback checks available state within account quotas; use a 10-day overlap and periodic deeper scans for old corrections. | Documented upstream checks occur multiple times per day, with at least one attempt every 24 hours. This is not a successful refresh guarantee. Enrichment events are not a live bank transaction bus. |
| **Link** | Poll supported read lists every five minutes while active, with backoff. During an approval/purchase, use the official CLI's status polling; archive resulting state. | Expect seconds-to-minutes for our own request-state observations and up to the chosen poll interval for newly available lists. Bank settlement and external-account refresh may take longer. A general consumer ledger webhook contract was not qualified here. |
| **Alpaca / brokers** | Alpaca's outgoing authenticated `trade_updates` stream for order events; REST/MCP reconcile on startup/reconnect and every few minutes while orders are open. Daily account/history backfill. Other brokers get only verified stream support, otherwise configurable polling. | Connected broker order/fill events can be observed within seconds; this is a target, not a measured guarantee. Statements, holdings from aggregators, and settlement remain slower. No latency claim for an unqualified Schwab adapter. |
| **Imports** | Immediate local archival after file submission. | The document's date determines financial freshness, not its import timestamp. |

Provider facts: [SimpleFIN limits and overlap](https://beta-bridge.simplefin.org/info/developers), [Plaid Transactions cadence](https://plaid.com/docs/transactions/), [Teller webhook behavior](https://teller.io/docs/api/webhooks), [Alpaca streaming](https://docs.alpaca.markets/us/docs/websocket-streaming). All minute intervals above are proposed local scheduling defaults, subject to tested quotas and cost controls.

When the owner selects Plaid as the primary feed, retain SimpleFIN as the daily-upstream safety net. Compare coverage and flag missing/conflicting evidence; an independent feed can catch some misses but cannot prove that nothing was missed. Do not silently sum both feeds.

Webhooks only schedule work or record authenticated provider events; they never directly authorize a money move. Deduplicate events, coalesce refresh jobs, honor `Retry-After`, use exponential backoff with jitter, and keep live refresh ahead of backfill. Do not replay every missed timer after sleep. On resume, perform one reconciliation and continue normally. A sleeping/offline computer cannot provide live data; expose that fact and catch up when it returns.

### 6.2 Receiving webhooks without exposing the financial API

**Default installation needs no inbound connection or hosted inbox.** Polling and broker streams work through ordinary outbound connections; Cosignet has outbound long-polling. This keeps SimpleFIN setup simple and preserves a working fallback for every push-enabled source.

**Optional push profile:** reuse `frp` in raw TCP mode. The owner runs `frps` on a small public machine with a domain; `frpc` on the home computer opens the outbound tunnel. The remote TCP port forwards the provider's original TLS connection to a local, restricted HTTPS webhook receiver. Terminate provider HTTPS locally with a certificate whose key remains at home. Reuse `lego` for certificate renewal; use a local ACME challenge path through the same relay where supported, or explicitly configured DNS validation. [frp TCP forwarding](https://gofrp.org/en/docs/features/tcp-udp/), [lego](https://github.com/go-acme/lego).

This is a design composition of existing tools, not a claim of a prequalified one-click relay service. The relay sees traffic metadata and ciphertext; it does not terminate financial TLS, log bodies, or store transaction payloads. Separate tunnel authentication protects relay administration. The receiver has no money credentials and accepts only bounded webhook POSTs for configured providers. Firewall it away from the data API, executor, and agent ports. Public callers can reach that restricted receiver; **a tunnel does not make it non-public**. It avoids opening a home router port or exposing the rest of Money Bridge.

Verify Plaid's signed request/JWT and body digest using its current documented verification flow; verify Teller's raw-body HMAC and timestamp, then deduplicate and durably spool locally before acknowledging. Do not trust relay-added headers. Reuse JOSE/cryptographic libraries for these checks. Teller's documented signature window is three minutes: stale replay does not become valid because a relay retained it. On reconnect, fetch authoritative source data to recover missed changes. [Plaid webhook verification](https://plaid.com/docs/api/webhooks/webhook-verification/), [Teller signing](https://teller.io/docs/api/webhooks).

A third-party webhook inbox that decrypts and retains Teller payloads would copy transaction history into another cloud. Do not make Hookdeck/Smee/another hosted inbox the default under the local-data decision. If the owner does not want a public receiver or relay setup, remain in polling mode. There is no honest design that accepts arbitrary provider webhooks with neither a reachable endpoint nor an intermediary.

The restricted receiver holds only webhook-verification material and its TLS key. Plaid verification-key retrieval goes through a narrow, rate-limited Source host operation; do not give an internet-facing receiver the general Plaid application secret. Reject oversized bodies and unknown connections before creating expensive refresh work. Local spooling has a quota and uses encrypted storage; overflow causes retry/reconciliation rather than unbounded disk use.

## 7. Actions: approval that actually controls execution

### 7.1 Freeze the actual intent

An agent proposes an operation, not a credentialed HTTP request. The executor checks the agent's grant and live provider capabilities, resolves stable account/payee/instrument IDs, and prepares a fully specified instruction. Store its canonical bytes, a digest, and the exact provider business arguments before requesting approval.

The frozen record includes:

- Installation ID/epoch, intent ID, originating agent, provider and sandbox/live environment, operation and schema version, adapter/tool manifest digest, policy version, creation/expiry, and stable provider idempotency/client-request ID.
- Exact source account and resolved destination; full Zelle address or verified beneficiary ID where relevant. Freeze identifier versions so changing a nickname or contact record cannot redirect an approved action.
- Exact amount/currency, fee ceiling and maximum total debit; transfer rail and execution date where supported. Missing provider defaults are resolved before approval.
- For a trade: account, security/contract ID, side, quantity or notional, order type, limit/stop conditions, time in force, trading session and permitted fees. Initial live support is cash, long-only limit orders; unsupported risk or execution constraints remain unavailable until their adapters are qualified.
- For a purchase: provider-verified merchant identity when available, destination origin, merchant challenge/order ID, method and business-body digest, line items, amount, taxes/shipping and maximum total. Do not approve only a friendly merchant label while leaving the destination mutable.

Use explicit decimal strings/integer minor units and a versioned deterministic serialization. Approval covers business effects, not transport headers, access tokens, a timestamped authentication signature, or a payment credential created later. The adapter may add those secret transport fields at submission; it cannot change business arguments. Unknown fields or implicit defaults fail closed.

The executor resolves grants from protected owner-managed policy, not from arbitrary scope strings supplied in an RPC request. Authenticate the calling service and bind the request to the agent identity. Apply revocations to the executor before acknowledging them to the owner; a policy-version mismatch blocks submission. Reject unsafe wall-clock drift and use elapsed-time expiry checks during a running session, so changing the local clock cannot extend an approval silently.

The owner approves this bounded instruction. A limit order may fill in pieces or at a better price; those fills belong to the one approved order and may not exceed its bounds. A broad “buy whatever looks good” or an uncapped market order is not an exact intent. Any semantic change, re-quote outside bounds, target substitution, or expired approval requires a new intent and fresh approval.

### 7.2 Approval selection

**Provider-native first.** Use the official flow if qualification demonstrates a fresh owner passkey confirmation for this exact request and enforcement of the approved destination/amount/order constraints. Preserve the provider request ID and evidence, and query the provider directly for status. Native approval of one provider's action cannot authorize another provider's operation. A provider's MFA or a logged-in session alone is not proof of the required per-action approval.

**Cosignet otherwise.** Its documented flow accepts an action payload, requests passkey verification, returns assertion material, and supports outbound long-polling. Its self-check explicitly distinguishes matching hashes from full signature verification. These are useful documented primitives; no authenticated qualification was performed in this design. [Cosignet API and verification caveat](https://cosignet.com/docs).

Send Cosignet a structured **approval card**, generated by the executor: action, exact amount/currency or trade bounds, payee/instrument, account display name, environment, expiry, intent ID, and the digest of the full frozen instruction. Include enough stable destination detail for meaningful review; a nickname alone is insufficient. Full bank account/routing numbers, credentials, balances, prior transactions, documents, and arbitrary agent rationale stay local. The digest binds the hidden local instruction while the display fields describe all its financial effects. Adding an extra financial effect not represented on the card is forbidden.

Set private link mode and `public:false`; do not enable public reveal or send payloads to notification channels. Cosignet stores payloads and assertion evidence; it is not a hash-only relay. Its retention and transparency metadata are an explicit privacy qualification item, even with private financial details. This is the limited cloud exception accepted in round 5, not permission to upload history. [Cosignet data and privacy model](https://cosignet.com/security).

**Qualification is an enablement gate, not a later TODO:**

1. Prove enrollment binds the approver to this owner. Obtain and pin credential IDs/public keys through an owner-authenticated enrollment/export process; do not trust a new public key returned beside an approval. Credential replacement requires owner administration and invalidates pending requests.
2. Demonstrate displayed values match our intended card and that the signed challenge binds its exact serialization. Reject ambiguous Unicode, duplicate JSON keys, unsupported numeric precision, changed currency, and misleading/truncated destination displays. Use a maintained canonicalization implementation where needed, not a handmade JSON-signature protocol.
3. With reused WebAuthn verification code, verify credential, signature, expected origin/RP ID, user verification, the full challenge and payload binding. Bind receipt to the stored request/nonce and local expiry; do not rely on a caller's `approved:true`. Handle synced-authenticator counters according to the library's protocol support, not a naive “counter must always increase” rule.
4. Prove expiry, rejection, replay, account recovery, stale sessions, missing evidence, cloud outage, and reused approvals all fail closed. Verify a second approver or copied request cannot satisfy this owner's intent.
5. Check actual account availability, retention, disclosure, and trust assumptions. If a safe independent receipt/key export cannot be obtained, Cosignet qualification fails; those providers remain read-only. No custom passkey UI is built to rescue it.

Provider-native approval gets equivalent tests for its enforceable contract, although its evidence may be provider-enforced status rather than a portable WebAuthn receipt. If native confirmation does not satisfy the passkey rule, keep mandatory native steps and add qualified Cosignet, or leave the action off. The executor trusts the approval display/service for truthful presentation; a valid signature alone does not protect against a malicious approval website.

### 7.3 Private official tools

Run the official Alpaca and Link MCP servers as private stdio children under the executor identity. They never listen on an agent-reachable port. If a read credential is genuinely restricted, a read-only instance may live under Source host; tool filtering alone does not turn a powerful API key into a read credential.

Use FastMCP's proxy/client plumbing with a pinned manifest of tool names, schemas, allowed account arguments, side effects, secret fields, and recovery support. Pass-through reads still pass authorization, archive capture, redaction, and audit. Public calls to money tools produce an intent; only the internal worker can invoke the underlying tool. Disable unknown/new tools until reviewed. Tool annotations such as `readOnlyHint` are not security classifications.

FastMCP documents automatic forwarding of incoming headers and protocol features. Configure `forward_incoming_headers=False`; disable upstream sampling, roots, unneeded elicitation, prompts/resources, and raw backend logs. Permit only deliberate, validated provider interaction URLs. Never forward an agent's bearer key to a provider or provider credentials to an agent. Use the library's switches/handlers, with integration tests that direct hidden-tool calls are rejected. [FastMCP forwarding behavior](https://gofastmcp.com/servers/providers/proxy).

For **Alpaca**, classify order placement, replacement, position liquidation, option exercise, and account risk-setting changes as protected. Broad “close all” tools are initially disabled because they expand against mutable holdings. Use a stable `client_order_id` and official order lookup where exposed; use the official API for a missing recovery field rather than pretending a raw MCP retry is safe. [Official Alpaca tool surface](https://docs.alpaca.markets/us/docs/trading-api-mcp).

For **Link**, approval can release a payment credential rather than complete a purchase. Keep that credential inside the executor. Prefer the official CLI's MPP payment flow for merchants exposing that API, freeze its destination/challenge/body, and execute there. Do not return virtual card numbers, CVCs, SPTs, LPTs, or credential file paths through any door. A card-form-only checkout remains unsupported. Link also documents approval policies allowing requests without manual approval; reject such bypasses unless an independent fresh Cosignet approval gates the exact action. Fresh passkey behavior and merchant constraint enforcement remain qualification questions. [Official Link CLI](https://github.com/stripe/link-cli).

Merchant URLs are untrusted inputs. Reject local/private/link-local destinations, unexpected ports and redirects; restrict egress to the qualified merchant origin and official provider hosts. Do not execute provider-returned shell strings or general “next command” instructions. Invoke a fixed executable with validated argument arrays. Store secret-bearing CLI output only in executor memory/private temporary storage, redact it before archive capture, and never forward its stderr verbatim.

For **Teller**, discover the account's `payments` link and supported schemes; obtain beta access rather than assuming every Chase account works. Its payment API may require Teller Connect MFA and currently documents `Idempotency-Key` retention for 72 hours. MFA is an additional provider step, not a replacement for qualified exact-intent approval. Use the documented payment lookup/listing for recovery. [Teller Payments](https://teller.io/docs/api/account/payments).

### 7.4 Durable state and ambiguous outcomes

```text
proposed -> frozen -> awaiting_approval -> approved -> submitting
                     | denied/expired                  |
                     v                                 +-> accepted -> settled
                   terminal                            |      | returned/reversed
                                                       +-> rejected
                                                       +-> outcome_unknown
                                                              |
                                                        reconcile/hold
```

`accepted` means the provider accepted an instruction, not that funds settled or a trade filled. Every transition is durable; payment/order facts and later returns are separately ingested.

1. Require an agent request key scoped to that agent and operation. Store a uniqueness constraint on it and the canonical proposal hash. Same key/same proposal returns the original intent; same key/different proposal is an error. Similar requests under different keys are flagged for the owner, not silently merged.
2. Persist the approval request ID before presenting its URL. Approval-service retries use that service's deduplication key. Receive evidence directly from the service/provider, never from the agent.
3. In one executor SQLite transaction, recheck grant/revocation, policy, expiry and account identity; reserve limits; consume the approval for this intent; allocate the attempt; mark `submitting`. Commit and fsync before the external call. Send exact frozen business arguments.
4. A single active executor and transactional claim prevent concurrent submissions. Every permitted retry uses the same provider operation ID/idempotency key and identical business arguments within the provider's retention contract. Do not enable generic SDK/HTTP retries for money POSTs without proving that contract.
5. Timeout, lost connection, uncertain 5xx, or a crash after submission yields `outcome_unknown`, not “failed.” Keep limits reserved. Query by provider/client ID and reconcile with order/payment/transaction evidence. Never automatically issue a new key or new payment because the first response was lost.
6. If the provider has no trustworthy duplicate-prevention or lookup contract, allow at most one local send attempt and freeze on uncertainty. For high-consequence routes, fail qualification entirely. Expired provider idempotency retention, including Teller's documented window, forbids blind resubmission. A negative eventually consistent lookup is not proof that execution never happened.
7. A definitive rejection releases the reservation; accepted/unsettled and unknown effects retain it conservatively. Return/reversal is a new fact. Recovery records the evidence supporting any release; an agent cannot set `settled` or clear an unknown outcome.

We guarantee durable local intent/attempt tracking and prevent deliberate duplicate submissions under the qualified contract. We do **not** promise universal exactly-once execution across arbitrary financial APIs. Preventing duplicate effects sometimes requires declining to retry.

### 7.5 Standing approvals and limits

**Decision: no standing money approvals in the initial product.** Every newly initiated transfer, payment, order, or material order replacement requires fresh owner approval. A scheduled task may prepare the next proposal and ask the owner then; it cannot mint an approval from yesterday's login. Partial fills under one approved order are the execution of that instruction, not a standing grant.

Local organizing can have standing scoped permission and undo. External cancellations, disputes, new beneficiaries, account configuration, virtual-card issuance, or credential/grant changes are explicitly classified capabilities, not swept into “organizing.” Until their semantics are qualified, they are disabled; enabled high-impact account actions require owner approval even where they do not immediately spend money.

Limits are **additional denials**, never an approval substitute. Proposed first policy: no money actions until the owner enables a provider and sets a per-action and rolling-24-hour ceiling for each source account/currency; no implicit currency conversion. Count gross outgoing exposure and fees, including unresolved attempts and open-order commitments. Reservations are atomic across concurrent agents. A sale does not replenish a buy limit, and refunds do not silently reset a daily ceiling.

Mark new/unrecognized payees and show stable destination identity on the approval card. Apply a proposal rate limit and a small owner-configured maximum pending queue to prevent approval spam. Agents may not raise limits or enroll beneficiaries as “trusted.” Owner administration can lower limits/revoke immediately; increases and trust changes require the owner management path. Unsent approvals are revalidated after policy changes.

Standing mandates would require an explicit change to Johan's per-move decision and a separate design for narrowly bounded schedules. Do not quietly enable them because Link or another provider offers an automatic-spending feature.

## 8. Three doors, one core, and a live event feed

All doors expose the same versioned operations and error model. The examples below specify Money Bridge's proposed interface, not existing commands.

| Capability | CLI example | HTTP operation | MCP tool |
| --- | --- | --- | --- |
| Available connections/products | `moneybridge capabilities` | `GET /v1/capabilities` | `capabilities` |
| Accounts and freshness | `moneybridge accounts list --json` | `GET /v1/accounts` | `accounts_list` |
| Transaction query | `moneybridge transactions list --account A --since 2026-01-01` | `GET /v1/transactions` | `transactions_list` |
| Original and revised facts | `moneybridge history transaction:T91` | `GET /v1/entities/{id}/history` | `entity_history` |
| Balances, holdings, documents, other facts | `moneybridge balances list --account A` | Typed `/v1/balances`, `/holdings`, `/documents`, `/facts` | Corresponding typed query tools |
| Refresh/backfill | `moneybridge sync --source C` | `POST /v1/jobs` with a typed job | `sync_request`, `backfill_request` |
| Organization with undo | `moneybridge annotate T91 --tag business` | `POST /v1/annotations` | `annotate`, `annotation_undo` |
| Prepare action | `moneybridge action propose --file intent.json --request-key K` | `POST /v1/actions` | `action_propose` |
| Action progress | `moneybridge action status I` | `GET /v1/actions/{id}` | `action_status` |
| Follow changes | `moneybridge events --after CURSOR` | `GET /v1/events` (SSE); `/v1/changes` for pages | `changes_since` for MCP clients without subscriptions |

HTTP action proposals return `202` plus intent ID, current state, a short owner-facing summary, and a validated provider/Cosignet approval URL if available. The URL is a route to the reused approval service, not authorization by itself. There is no Money Bridge `approve=true` endpoint. The command returns while awaiting approval; the feed reports progress. Do not hold an MCP tool call open for a phone interaction.

The CLI is a thin local client. `moneybridge mcp` is a stdio adapter to the same running daemon, with the connecting agent's credential; it does not create a second database or load provider keys. Streamable HTTP MCP is optional on the same protected local API listener. Generate JSON schemas/OpenAPI from shared Pydantic types, with stable error codes such as `scope_denied`, `capability_unavailable`, `freshness_unmet`, `approval_pending`, `approval_expired`, and `outcome_unknown`.

### Keys and authorization

Create an opaque, high-entropy key per agent and store only its digest and an identifier in the authority database. Display it once through owner setup or install it directly in that agent's local configuration; never through chat. Support expiry, rotation, and immediate revocation. Keys authorize *requests*, never owner approval.

Grants include operation, provider/connection/account allowlists, data kind and field restrictions, history/date bounds, document/raw-data access, and action types. Example: an assistant may read current balances and posted transactions for checking, annotate them, and propose Zelle payments, while having no access to tax documents or brokerage accounts. `actions:propose` does not imply `documents:read` or vice versa. Historical versions, event replay, pass-through reads, counts, and exports enforce the same restrictions as current views.

Provider-wide tools that cannot enforce a narrow account scope must either be filtered using a fully understood response schema or denied. Unknown raw fields cannot bypass field restrictions. Do not hand an agent broad raw payload access just because it may read normalized transactions. Authorization is checked at execution time as well as discovery; hidden tool names are not a boundary.

The owner management socket is separate from the agent API and guarded by OS administration. Agents cannot issue keys, expand grants, install connectors, change approval identities, reset the database, or alter executor policy. On Unix require peer-credential checks and socket permissions; on Windows use named-pipe ACLs and authenticated service identity. Normal loopback HTTP still requires a key; reject unexpected Host/Origin and cross-site browser requests. No public API binding by default. Remote agent access is an explicit private-network/TLS deployment, not the webhook tunnel.

### Audit

Before disclosing data, durably record actor/key ID, operation, authorization decision, allowed query parameters or their protected representation, snapshot/high-water mark, selected revision IDs or a reproducible selection manifest, result count, request correlation ID, and response digest. Record attempted disclosures and denied calls too. Never log bearer tokens, provider credentials, PAN/CVC, or plaintext secret-bearing responses. Audit data is itself sensitive and scoped.

For long streams or downloads, log the start and each released batch/chunk before emission, then completion/disconnection. This proves what the server released, not that the remote client read every byte. Pass-through reads archive their financial response and audit its redacted disclosure before returning. Internal sync reads are attributed to service identities. Actions record proposal, approval request, decision, exact digest, attempt, outcome, and reconciliation evidence. Executor records are mirrored idempotently so a main-daemon outage does not lose action history.

Use a sequence/hash chain for tamper detection and include its head in encrypted owner backups. This makes accidental or partial edits detectable; it does not make a local log immutable against a machine administrator who can rewrite both data and keys. No blockchain or external audit SaaS is necessary. A failed audit commit blocks new disclosure or submission; recovery/status work records to the executor's durable journal where applicable.

Rate-limit invalid clients before database work. For an unauthenticated request flood, persist bounded interval records containing exact request counts, reason and transport metadata rather than allowing log volume to exhaust the financial store. Authenticated reads and actions retain individual records; they are never sampled. Do not claim to identify an agent before its key authenticates.

### Event feed

Commit data and its events in the same transaction. Events carry a stable event ID, type/version, entity/revision reference, recorded time, source time if known, and correlation ID. Types include `transaction.revised`, `balance.observed`, `source.stale`, `sync.completed`, `document.imported`, and `action.state_changed`. They describe facts; they do not tell an agent what financial decision to make.

Reuse HTTP Server-Sent Events rather than building a message broker. Support reconnect with `Last-Event-ID`, plus bounded pull pages through every door. Delivery is at least once: consumers deduplicate IDs. There is no global financial ordering across providers; sequence reflects local commits, with source/effective times retained. Use opaque cursors bound to the caller/query and a stable snapshot for ordinary pagination so newly arriving rows do not skip results.

Filter before delivery; recheck revocation and scope changes throughout an open stream. Cursor encoding must not reveal restricted account IDs or event contents. Bound buffers; disconnect slow clients with a resumable cursor instead of exhausting memory. No automatic event expiry. Audit-feed reads do not recursively generate an unbounded stream of their own audit events; audit is a separate owner-facing query surface.

## 9. Security and data locality

### 9.1 Threat model

| Threat | Enforced boundary | Remaining limit |
| --- | --- | --- |
| Prompt injection in transaction descriptions, PDFs, merchant responses, or provider errors | Treat all financial text as data; escape terminal control sequences and markup; never execute text, fetch embedded links, accept account aliases as commands, or let data choose tools/approval policy. Only structured validated operations reach the executor. | An agent may still believe a malicious description. Scope limits and independently displayed approval details contain consequences; Money Bridge cannot make the agent's reasoning trustworthy. |
| Compromised agent or stolen agent key | Per-agent scopes; separate OS users; no archive/secret/config file access; mandatory executor gate; authenticated IPC; proposal limits and revocation. | The agent can copy and exfiltrate information legitimately returned within its grant. Revocation cannot retract data already disclosed. |
| Agent with a shell on the owner's desktop | Services and configuration owned by separate non-login service identities; binaries/policy protected from the agent; management requires an owner-controlled OS elevation step. | If the agent has root/admin, can control the owner's approval browser, or can rewrite the executor, local protection fails. “Separate process, same writable user” is not sufficient isolation. |
| Stolen powered-off machine or copied backup | Full-volume encryption, SQLCipher, encrypted blobs, OS-protected keys, independently protected recovery material. | An unlocked running machine/admin compromise can access decrypted data and credentials. No promise of cryptographic protection from a fully compromised host. |
| Compromised upstream provider tool or malicious package | Locked versions/hashes, reviewed capability manifests, private subprocesses, minimum credentials, fixed executable paths, restricted egress, no automatic tool-surface expansion. | The official MCP handling a powerful credential is trusted code. The OS boundary does not stop a malicious credential holder from using that credential directly; upstream supply-chain trust remains a live-action risk. |
| Forged/replayed webhook | Verify raw-body signatures, timestamp and event ID; bounded parser; isolated intake; fresh authoritative fetch; no approval authority. | Attackers can attempt denial of service. Poll reconciliation provides continuity. |
| Approval-service compromise or owner deceived by misleading details | Frozen intent, private receipts, pinned owner credentials, qualified display, exact-effect card, local limits, no secrets/history sent to service. | Display honesty, owner attention, provider enforcement, and credential recovery remain trust assumptions. |

Imported files are untrusted: enforce size/type limits, parse out of process without network access, reject archive traversal, never invoke a spreadsheet macro, and keep originals encrypted. Agent-selected paths cannot read arbitrary local files; uploads/owner-selected import paths are explicit. For provider connection tokens and URLs, validate HTTPS and permitted hosts; block SSRF and credential-bearing redirects. Custom SimpleFIN servers require owner configuration, not an agent-supplied arbitrary URL.

### 9.2 Secrets by operating system

- **Linux:** production services use separate fixed, non-login users and systemd credentials. Prefer `LoadCredentialEncrypted`/`systemd-creds`, with TPM-backed protection where available and encrypted storage underneath. A supported desktop Secret Service backend is suitable for interactive read-only mode. Headless machines without a safe auto-unlock path require owner unlock after boot; never write the decryption secret beside the ciphertext. [systemd credential tooling](https://www.freedesktop.org/software/systemd/man/latest/systemd-creds.html).
- **macOS:** use Keychain items with access restricted to the signed Money Bridge service/helper and the appropriate service identity; launchd starts the service. Test unattended unlock rather than assuming a login keychain is available to a daemon. If it is locked, report `locked` and wait for owner interaction. [Apple Keychain services](https://developer.apple.com/documentation/security/keychain-services).
- **Windows:** use DPAPI under the dedicated service identity and ACL-protected storage, with a loaded service profile as required; use Credential Manager through `keyring` where that backend fits. Do not rely on machine-wide DPAPI alone as an account-isolation boundary. Run the executor with its own restricted service SID/account and private named pipe. [Microsoft DPAPI contract](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).

`keyring` is an adapter, not a guarantee of isolation: validate its selected backend and deny plaintext/null fallbacks. Native store access and key retrieval are role-specific. Powerful bank/broker tokens, Teller certificates/private keys, Link sessions, and Cosignet API credentials belong to the executor where they can authorize money. Read-only source tokens belong to Source host. The agent-facing CLI never retrieves them. [Python keyring backends](https://keyring.readthedocs.io/en/latest/).

When an official tool insists on environment variables or local token files, give it a private service home/config directory on encrypted storage, strict ACLs, and a minimal child environment. Intercept credential persistence during enrollment; never leave tokens in the owner's general CLI config. If the upstream tool cannot meet this without invasive patching, use its official SDK/API for that operation and document the exception. Disable core dumps and sensitive subprocess logging; prevent same-user debug access through the service-user boundary.

### 9.3 Encryption and operations

Require an encrypted data volume: Linux LUKS or an equivalent encrypted volume, macOS FileVault, Windows BitLocker/device encryption. The wizard checks what it can and explains unknown status; it does not repartition a disk automatically. Store the database with SQLCipher as defense for copied files and backups, including encrypted journals under a tested configuration. Build the SQLCipher binding in CI for each supported platform; do not substitute plaintext SQLite if packaging fails. [SQLCipher](https://www.zetetic.net/sqlcipher/), [Python binding](https://github.com/coleifer/sqlcipher3).

Encrypt each document/raw-payload blob using the existing `cryptography` AES-GCM implementation with a fresh nonce and associated data binding blob identity/version. Store content hashes inside encrypted metadata; avoid sensitive filenames in the filesystem. Keep different data and executor keys, record key versions, and retain old key material until migration/backups no longer need it. Test nonce generation and damaged-ciphertext rejection; do not design a new encryption format without using the library's authenticated primitive. [cryptography AEAD](https://cryptography.io/en/latest/hazmat/primitives/aead/).

Use memory or encrypted locations for temporary data; cover swap, crash dumps, and exports with volume encryption. Explicit exports warn where plaintext will be written and require the appropriate grant. Nothing silently uploads crash reports, source payloads, logs, or telemetry. Dependency updates and OS installers are owner-managed, signed/hash-checked, and cannot be triggered by an ordinary agent operation.

Self-hosting means Money Bridge's archive and execution are local. Banks and selected aggregators still process data upstream, approval providers see the allowed action details, and an external AI may receive whatever the owner authorizes. Do not describe that as a wholly offline or cloud-free financial system.

## 10. Installation and connection setup

### Runtime and packages

**Choose Python for the application**, because it lets us embed FastMCP's proxy and the official Alpaca and Plaid Python libraries with little glue. Use a supported CPython minor selected against the locked dependency matrix at release. Type-check public contracts; use Pydantic at trust boundaries. A Go/Rust rewrite for a single-file aesthetic would duplicate integration work without removing provider-tool runtimes.

Ship **native signed installation packages containing a PyInstaller directory bundle**, not a requirement to install Python, pip, Docker, Node, or a compiler. PyInstaller supports the three target OS families but builds must run on the corresponding OS. Include signed/version-locked provider assets only as needed; Link's own native binary is preferred where available, otherwise package its required runtime privately. Do not run `npx ...@latest` or `uvx ...` with an unpinned package in production. [PyInstaller packaging constraints](https://pyinstaller.org/en/latest/).

Target Linux x86-64/ARM64, macOS Apple Silicon/Intel where tested, and Windows x86-64 initially; explicitly label other architectures unsupported until CI proves them. Provide `.deb`/`.rpm` plus a tarball for Linux, a notarized `.pkg` for macOS, and a signed Windows installer. Reuse native service managers. Updates take a consistent backup, quiesce submissions, migrate, verify, then resume; rollback restores a compatible snapshot in read-only mode, not a guessed downgrade of a mutated database.

The full installer needs one ordinary OS administrator approval to create service identities and protected directories. That is installation authorization, not financial approval. Portable user mode can provide a read-only experience; it must not claim to isolate live money credentials from agents running as that user. No platform gets live actions until its isolation tests pass.

### Text setup wizard

`moneybridge setup` is a plain terminal wizard, usable by a non-expert with short prompts and provider-owned browser handoffs. It is not a tracking UI. A temporary local callback page may host an official connection widget when the provider requires it; no custom bank login or approval screen is built.

1. **Prepare local storage.** Explain where history will live, check volume encryption and free space, provision keys/services, and confirm a local encrypted backup destination or clearly mark backup incomplete. Offer a synthetic demo without any provider account.
2. **Connect SimpleFIN first.** Open its official token-creation page. Accept the one-time setup token in a hidden terminal prompt, validate and claim it, store the resulting secret Access URL securely, and show discovered accounts. Negotiate the actual protocol version: the published v2 page is a draft and cannot establish a universal deployed version. [SimpleFIN protocol](https://www.simplefin.org/protocol.html).
3. **Choose account identity and data access.** Let the owner give account aliases, confirm any duplicate-source links, and choose primary sources. Show history bounds and unsupported products. Initial sync runs immediately and historical work continues with progress and gaps.
4. **Add Plaid if wanted.** Walk the owner through their own developer account and Production/Trial entitlement. Reuse the official CLI/Hosted Link if the platform and protected credential handoff pass qualification. Otherwise use the official SDK and Hosted Link flow; the owner still uses Plaid's connection UI. Capture Item tokens into the service store. Entitlement denial leaves SimpleFIN/imports usable. The documented CLI installation is Homebrew; Windows parity must be verified rather than assumed. [Plaid CLI and enrollment](https://plaid.com/docs/resources/cli/).
5. **Add Teller after Plaid.** Configure the owner's application certificate, key, token, and official Teller Connect. Show actual account capabilities; Zelle remains off until beta admission, native steps, Cosignet and outcome recovery are qualified. Do not imply Teller onboarding is effortless for every individual.
6. **Add Link or a broker.** Launch official authentication under the correct service identity; paper/test environment by default where offered. Show read capabilities immediately. For money, enroll/qualify existing native approval or the owner's Cosignet account, bind the owner identity, set ceilings, and perform a harmless approval drill. A successful drill does not itself enable a real payment.
7. **Connect an agent.** Select accounts, fields, documents, action proposals and expiry. Write that agent's scoped key and CLI/MCP configuration locally. Demonstrate a read and show its audit entry. Never ask the owner to paste provider secrets into an agent chat.
8. **Optional live push.** Explain the advanced relay requirement and privacy boundary. Configure and test it only if wanted; otherwise use polling and display the expected freshness. Finish with `moneybridge doctor`, last observed times, source gaps, backup health, and each action's enablement reason.

Every setup step is resumable. Credentials are entered once through hidden prompts or provider flows, failures have plain-language recovery, and one unavailable provider does not undo other connections. An always-on Linux machine gives Johan better continuous coverage; a laptop still works but cannot refresh while asleep.

## 11. Tests: observable workflows before isolated functions

### Stage A — complete system with fake providers

Build a runnable vertical slice first: packaged service + real database + CLI/MCP/HTTP clients + `ScriptedBank` + fake approval/execution services. The fakes run separately and maintain independent effect logs, so the oracle is not another call to our own normalization or state transition function.

Required scenarios:

- Connect, backfill, restart, disconnect the source, and query retained history through every door. Check pending-to-posted changes across pages, modified amounts, explicit removal, absence without removal, stale events, repeated data, reversal, and a value that changes back to an earlier value.
- Import overlapping CSVs, import the same file twice, retain two identical-looking purchases, change a parsing map, undo a tag, and preserve every original/derived record and provenance link. Corrupt a blob and confirm a clear integrity failure.
- Kill the daemon at page staging, before/after SQLite commit, and after commit but before event publication. Assert no skipped cursor, phantom event, or duplicate financial revision; event replay may duplicate delivery with the same ID.
- Run concurrent scoped clients against every transport, direct hidden-tool invocation, raw source reads, history, document downloads, count queries, and an open SSE stream. Revoke a key midstream. Assert denied data never leaves the service, and every permitted disclosure has a prior durable audit record.
- Prepare a transfer and change amount/payee/currency/environment afterward; replay an approval for another intent; use an unpinned credential; change provider schemas; expire approval; fill the pending queue. Confirm the fake bank effect log remains empty.
- Crash before submit, after external acceptance but before response, and after receipt before local persistence. Restart with the same key; simulate provider idempotency expiration and delayed lookup visibility. Assert exactly the allowed effect count, a durable unknown state when required, and no fresh-key resubmission.
- Reserve limits concurrently across agents; account for partial fills, pending exposure and unknown outcomes. Change policy while awaiting approval. Confirm stale approval cannot overrun new limits.
- Restore an older backup while the original has submitted a payment. Confirm the restored copy is read-only and cannot execute replayed intents or run alongside the active executor without owner recovery.
- Put shell metacharacters, terminal escapes, instructions, URLs to localhost, and credential-shaped strings in descriptions/provider results. Confirm no execution/network side effects and no secret leakage into outputs/logs.

Use pytest for integration orchestration and Hypothesis only for concentrated invariants such as decimal conversion, revision identity, canonical intent serialization, scope intersection, and state-machine transitions. Unit tests are useful there; do not create hundreds of mocks that merely restate adapter code.

### Stage B — provider test environments

Use SimpleFIN's demo protocol response; Plaid Sandbox and its sync/webhook scenarios; Teller Sandbox; Alpaca paper trading; Link's documented test capability only for credential types it supports. Run the exact official MCP/CLI releases the product will package. Test real Cosignet enrollment/receipt behavior with synthetic non-financial payloads in an owner-controlled test account. A fake native-approval response cannot qualify a real provider flow.

Prove end-to-end field fidelity, authentication handoff, webhook signatures, schema drift behavior, rate limits, reconnect, and outcome lookup. Run the tunnel against test webhooks and inspect the remote relay to verify financial TLS does not terminate there. Inspect packets/logs for token/transaction leakage. Sandbox success does not prove Production eligibility or exact bank behavior.

### Stage C — owner-approved real accounts

Start with Johan's SimpleFIN read-only connection and compare a sample to statements, including account balances, pending items, signs, dates, and known historical gaps. Add an independent second install to demonstrate no hard-coded accounts or shared maintainer credentials. Observe several normal refresh cycles and account reauthentication before enabling actions.

Only then perform explicitly approved, small real actions with a known destination, qualified approval, configured caps, a recorded intent digest, and post-execution reconciliation. Never put live credentials or automatic real payments in CI. Test safe order cancellation and returned/failed payment states only when the provider and owner permit them; absence of such evidence limits the capability claim.

### Release proof

Linux/macOS/Windows VM tests must install, reboot, unlock, launch official tools, deny access from the agent OS identity, enforce socket/pipe ACLs, and restore an encrypted backup. The bundled application must work without development runtimes. Pin a compatibility manifest containing dependency/tool digests and tested capabilities. New upstream tool schemas default to disabled. No money-capable release before an independent security review of the executor, secret isolation, and approval qualification evidence. This document requests no live connection or action itself.

## 12. Milestones in build order

Each milestone leaves a usable installed product. Cross-platform smoke tests begin with the first package; live actions are qualified separately per OS. Aggregator build order stays **SimpleFIN → Plaid → Teller**.

| Milestone | Usable result | Exit evidence |
| --- | --- | --- |
| **M1 — local read bridge** | SimpleFIN + encrypted SQLite + current/revision reads through CLI, MCP and HTTP; per-agent keys, audit, manual refresh, replayable events. Native read-only packages and a demo. | ScriptedBank end-to-end suite and an owner-approved SimpleFIN read pilot. Survives restart; no secrets in output. |
| **M2 — lasting history** | Scheduled refresh, historical backfill, CSV/document import, source coverage, annotation undo, encrypted backup/restore. | Pending/posting/correction/removal fixtures, overlap tests, restore drill, real statement comparison. Still useful after source disconnect. |
| **M3 — broader, fresher reads** | Plaid products and cursor sync, official enrollment, optional encrypted webhook tunnel, source linking and freshness. | Sandbox cursor/webhook failures and production read qualification; no unsupported real-time promise. |
| **M4 — third aggregator** | Teller reads and capability discovery; official Connect handoffs; conditional Zelle shown with exact blockers. | Sandbox and owner read tests, quota behavior and webhook validation. Money actions remain off. |
| **M5 — private official-tool reads and action rehearsal** | Link and Alpaca read tools; separate executor; fake/paper actions; frozen intent, approvals, limits, unknown-outcome recovery. | Native OS isolation, official-tool contract tests, receipt qualification results. Failed Cosignet qualification leaves reads fully usable. |
| **M6 — first live action** | One narrow qualified route: Link official merchant API purchase if native approval qualifies; otherwise one Alpaca limit-order route if Cosignet qualifies. | Fresh owner approval, private credential handling, reliable correlation/recovery, security review, explicitly approved small real pilot. If neither qualifies, do not claim a money-capable release. |
| **M7 — additional qualified actions** | Teller/Chase Zelle if admitted; additional official broker/provider actions; richer documents/data kinds. | Separate capability contract, approval, idempotency and recovery proof for each new action and account. No website automation fallback. |

Do not delay M1 to design a universal trade engine. Do not ship M6 by relabeling a generic confirmation or by removing executor isolation. A missing provider remains a clear unavailable capability in a useful data product.

## 13. Challenges to binding decisions

These are explicit disagreements or feasibility tensions. The design still follows the decisions.

1. **“Plaid/Teller push means seconds to minutes” overstates freshness.** Their published transaction schedules include upstream polling only a few times per day. Push improves delivery after discovery. Keep both providers and push support, but describe bank freshness honestly and expose timestamps. This changes the expectation, not the chosen aggregator order.
2. **Cosignet is a chosen candidate, not yet a proven universal approval backend.** The public docs provide useful binding evidence but do not establish this installation's owner-key enrollment/export, all failure cases, or an independently tested display. Its availability and retention need qualification. Follow the decision: use it if qualified; otherwise money actions stay off. Do not build a replacement passkey system.
3. **Strict local storage and easy hosted webhook inboxes conflict.** Teller can include transaction bodies. The opaque TCP tunnel preserves local financial TLS but requires an advanced relay setup and still exposes a restricted receiver. Polling is the default when that burden is unacceptable; do not weaken the locality promise silently.
4. **Official MCP reuse does not itself enforce approval.** Some tools execute directly and their keys are powerful. Reuse them privately behind a small executor; do not expose their money tools unchanged to agents. If a tool cannot support bounded arguments/recovery, use the official API for that gap.
5. **“Everybody” cannot mean every individual automatically gets every financial API.** Bring-your-own provider accounts, jurisdiction, app review, beta access and bank contracts remain external constraints. Ship portable software and graceful capability discovery, not fictitious universal bank entitlement.
6. **“Keep everything” cannot include unseen intermediate provider states or loose payment secrets.** Retain every observed financial revision and original import indefinitely. Protect credentials separately and discard transient payment capabilities when no longer needed. Report acquisition gaps rather than implying completeness.
7. **No UI plus non-expert onboarding still needs provider browser screens and OS setup.** A text wizard with official connection/approval flows meets the intended product boundary. Implementing custom authentication screens to hide provider complexity would violate reuse and increase scope.
8. **Every money move needs approval, so standing spending grants are inconsistent with the present rule.** Keep standing grants for reversible local organization only. Any relaxation should be an explicit future owner decision.

## 14. Risks and questions for Johan

The following questions do not block the read-only milestones; their proposed defaults are already reflected above.

| Question / risk | Proposed answer or release consequence |
| --- | --- |
| Will agents have unrestricted shell/admin access on the same machine? | Give them ordinary scoped access and a separate OS identity from services. If they retain administrator control, state that local approval enforcement cannot protect against them; do not claim otherwise. |
| Can the Linux host remain on, and are delayed updates while laptops sleep acceptable? | Prefer Johan's always-on Linux host; expose offline/stale state on other machines and catch up after wake. |
| Is an optional owner-controlled relay/domain worth maintaining for push? | Start with polling. Add the TCP tunnel only when measured freshness and convenience justify it. Do not operate a central Money Bridge relay. |
| What exact details may Cosignet retain, and can its owner-key/receipt contract qualify? | Show an example synthetic approval card and verify private-mode retention/transparency behavior before live enablement. Any unacceptable disclosure or missing verification keeps affected actions off. |
| What ceilings and accounts should the first live pilot use? | Owner chooses per-action and per-currency rolling ceilings; default is disabled until configured. Use one narrowly scoped route and a known destination. |
| Does “Link actions” mean purchases at supported API merchants or arbitrary checkout pages? | Support official API merchants. Arbitrary card-form checkout is outside this design and remains unavailable. |
| Does Teller actually admit Johan's app and expose Chase Zelle? | Test account capability and admission; keep the account read-only until proven. Do not spend the first milestones assuming beta access. |
| How much historical CSV/PDF material already exists, and what backup device is available? | Import originals immediately, extract structured rows with provenance, and perform a restore drill. Never label missing years complete. |
| Cross-platform packaging, signing, encrypted SQLite, and service-key unlock may exceed the line estimate. | Treat those as release gates; keep portable mode read-only. Avoid a rushed same-user money executor to simplify installation. |
| Upstream adapters, approval services, or access terms can change. | Lock components, record qualification evidence and dates, rerun contract tests on updates, and disable only the affected capability when assumptions break. |
| Provider subscriptions, paid refresh, signing certificates and optional relay hosting can cost money. | Show current provider terms during owner setup, require explicit refresh budgets, and distinguish free MIT software from third-party service fees. No maintainer account or shared production secret subsidizes access implicitly. |

