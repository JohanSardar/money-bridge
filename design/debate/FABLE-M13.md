# Fable ruling — M13: per-agent key scope depth in v1

**Ruling:** v1 keys carry operation, data-kind, account and connection scopes only; field-level and date-range grants are deferred until a real user asks for them, and raw/pass-through access is a separate default-off scope rather than a grant dimension.

## Reasoning

Johan's binding rule is "build as little as possible," and the product is for everybody: a friend installing Money Bridge should be able to create a key by answering "which agent, which accounts, read or propose." Field-level and date-range grants add a filtering layer that must be applied identically across current views, history, events, counts, exports and pass-through, and tested for every one of those doors. That is real code and real test surface for a use case nobody has stated. Both designers' own example (an assistant that reads checking, annotates, proposes Zelle, and cannot see tax documents or brokerage) is fully expressible with operation + data-kind + account scopes.

Astra's substantive security points survive without the extra dimensions and are already agreed: owner-only administration, uniform authorization across every door, events intersecting data grants, prompt stream revocation. The one genuine risk Astra identifies, that a broad raw payload leaks fields or accounts the agent should not see, is closed by two rules already in Astra's text: provider-wide tools that cannot enforce account scope are filtered through a known schema or denied, and raw access is never implied by normalized access. Making raw access its own explicit scope, off by default, gives that protection without a field-filter engine.

Deferral must not become a breaking change later. The grant is a versioned document with a closed set of restriction dimensions. A dimension that is absent means "unrestricted within the other scopes." Adding `fields` or `date_range` later therefore leaves every existing key valid and unchanged. Unknown dimensions in a stored grant are rejected, so a downgraded binary fails closed instead of silently widening access.

Date-range needs become visible in the audit log (agents repeatedly querying old history they do not need). Add the dimension when that evidence or a user request appears.

## Exact v1 scope list

Every key is a grant document: `{version: 1, operations: [...], accounts: [...] | "*", connections: [...] | "*", expires_at}`. Authorization = operation allowed AND resource's account allowed AND resource's connection allowed. Same check on current, history, events, counts, exports and pass-through.

**Operation scopes (data kind is part of the operation name):**
- `read:accounts` — account list, balances, pending/available
- `read:transactions` — posted and pending transactions, recurring/bill detection inputs
- `read:holdings` — positions, orders, investment balances
- `read:documents` — statements, tax documents, imported files (normalized metadata + download)
- `read:raw` — original provider payloads and pass-through reads of owned provider tools; **default off**, never implied by any other scope, still filtered by account/connection allowlists or denied where the provider tool cannot be filtered
- `read:events` — live feed and replay, delivered as the intersection with the key's other read scopes
- `write:annotations` — categorize/tag/notes with undo (local organizing only)
- `propose:transfers`, `propose:payments`, `propose:trades`, `propose:purchases` — create intents only; approval always comes from the owner

**Resource allowlists (both required, `"*"` allowed):**
- `accounts` — list of Money Bridge account IDs
- `connections` — list of provider connection IDs (SimpleFIN, Plaid item, Teller enrollment, Link, Alpaca)

**Key attributes:** expiry, rotation, immediate revocation (including open streams), owner-only creation on the separate owner path.

**Reserved for later, not built in v1:** `fields` (per-data-kind field allowlist) and `date_range` (history bound). Both are optional restriction dimensions; absence means unrestricted. Added only when a real user needs them.
