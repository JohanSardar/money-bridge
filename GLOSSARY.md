# Money Bridge

A self-hosted program that gives the owner's AI agents scoped, audited access to the owner's finances and lets them propose money actions that the owner approves.

## People and principals

**Owner**:
The one person whose finances an install holds and who alone administers it.
_Avoid_: user, admin, customer

**Agent**:
A program that uses Money Bridge on the owner's behalf through an agent key.
_Avoid_: client, bot, assistant

**Agent key**:
An opaque secret identifying one agent and carrying one grant.
_Avoid_: token, API key

**Grant**:
The versioned document on an agent key listing allowed operation scopes, accounts, connections and expiry.
_Avoid_: permissions, policy, role

**Scope**:
One named operation permission inside a grant, such as `read:transactions` or `propose:trades`.
_Avoid_: permission, right

**Trusted agent host**:
An install where the owner has recorded that agents run with administrator rights on the same machine.

## Sources and evidence

**Provider**:
An external service Money Bridge reads from or acts through, such as SimpleFIN, Plaid, Teller, Stripe Link or Alpaca.
_Avoid_: integration, vendor

**Connection**:
One owner enrollment with one provider, holding a reference to its credential.
_Avoid_: link, item, enrollment (except when quoting a provider)

**Source account**:
An account exactly as one connection reports it.

**Account**:
The owner-facing account identity, linked to one or more source accounts only by owner confirmation.

**Observation**:
One immutable record that a provider returned a particular payload at a particular time.
_Avoid_: fetch, snapshot, sync result

**Revision**:
One immutable version of an entity's normalized facts, created only when its content differs from the current revision.
_Avoid_: update, version, change

**Sighting**:
The record that an observation saw an entity, whether or not it produced a new revision.

**Relation**:
A typed, evidence-backed link between two entities, such as pending-became-posted or possible-match.
_Avoid_: merge, dedupe

**Possible match**:
A proposed relation created from similarity alone, never treated as identity until the owner confirms it.

**Coverage**:
The interval and completeness a source actually returned for an account and product.
_Avoid_: history window, range

**Checkpoint**:
The provider cursor or window position committed together with the rows it produced.
_Avoid_: cursor (except when quoting a provider), bookmark

**Knowledge time**:
When Money Bridge learned a fact.

**Effective time**:
When a financial fact happened according to its source.

**Freshness state**:
Whether data for an account and product is current to its source, stale, offline or unknown.

**Annotation**:
An owner- or agent-authored tag, category, note or business/personal label layered over provider facts, undoable.
_Avoid_: metadata, label (alone)

**Import**:
An original file the owner supplied, archived with the rows extracted from it.

## Doors and records

**Door**:
One way agents reach Money Bridge: CLI, MCP, HTTP API or event feed.
_Avoid_: interface, endpoint, transport

**Operation**:
One named, typed request in the shared registry, exposed identically on every door.
_Avoid_: endpoint, tool, command

**Owner door**:
The OS-authenticated local channel for owner-only operations.

**Event**:
A durable, replayable notice that a fact or action state changed.
_Avoid_: webhook, notification, message

**Audit record**:
The durable entry written before any disclosure or action step, chained for tamper evidence.
_Avoid_: log line

## Actions

**Proposal**:
An agent's request for a money action, before Money Bridge resolves and freezes it.

**Intent**:
The executor's frozen, fully specified money action with its digest.
_Avoid_: order, transaction, request

**Approval**:
The owner's fresh passkey confirmation of one intent, through a provider's native flow or Cosignet.
_Avoid_: consent, authorization, confirmation

**Approval card**:
The minimal action details shown to the owner and sent to an approval service.

**Executor**:
The separate process that alone holds money-capable credentials and submits approved intents.
_Avoid_: worker, runner

**Attempt**:
One durable record of submitting an intent to a provider under its stable idempotency or client id.

**Outcome unknown**:
The state of an attempt whose provider result could not be established; never resent.

**Reservation**:
Limit capacity held against an intent from submission until a definitive outcome releases it.

**Limit**:
An owner-set ceiling per action or per rolling day that denies proposals; never a substitute for approval.

**Epoch**:
The executor generation; a restored install must open a new epoch before actions resume.

**High-impact action**:
A non-spending action with real-world effect, such as cancelling, disputing or adding a beneficiary; off until qualified.
