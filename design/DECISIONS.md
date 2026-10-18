# User decisions (Johan): finance connector

Binding source of truth. Build agents read this file, not chat history.

## 2026-10-17, grilling round 1
- **For everybody.** A real product anyone can install and run their own copy of (e.g. a friend hooks up his own accounts). No hard-coded accounts.
- **Standalone, new repo, separate from Toy.** Toy is just one agent that uses it.
- **What it is:** a plugin/system for agents and computers to pull financial data and act on accounts. It is NOT a tracking or budgeting app. Others build their own tracking on top of the data.
- **Coverage goal:** every bank possible. Johan's accounts right now: Amex, Chase bank, Venmo, X Money, Zelle, Link. He already has a SimpleFIN Bridge account.
- **Actions:** all of them, including sending money to people and trading investments: organize (categorize/tag/notes), pay bills, move money between own accounts, send money (Venmo/Zelle/etc.), cancel subscriptions / dispute / refund, trade, virtual cards.
- **Approval:** any spending or moving of money requires the owner's **passkey** confirmation. Non-money actions (organizing) need no approval, with undo.
- **Do not build tracking itself.** Build the data system that tracking can be built on: transactions, balances, pending, bills/due dates, recurring charges, business vs personal, net worth inputs, investments, tax documents, credit score.
- **History:** keep everything forever. Backfill past what SimpleFIN returns (old statements/CSV exports), as far back as each provider allows.
- **Security:** high bar. Data only on the owner's own machine, disk encrypted; tokens and logins in a secrets store, never in chat or logs; agents get scoped keys.

## 2026-10-17, round 2 (Johan's corrections)
- **What it is: an API, an MCP server and a CLI** (possibly several) that let any agent, now or in the future, access and act on the owner's finances. Agents built on top do the tracking, the actions, the logging, the organizing and the advising. The product itself contains no tracking, budgeting or advice logic.
- **Runs on Linux for Johan, on any computer for everyone else.** Public project.
- **Don't build passkey approval ourselves.** Reuse something that already exists.
- **No bank-website automation.** (Johan: "this has nothing to do with website, don't worry about it." Interpreted as: act only where an official API exists. To confirm in round 3.)
- **Data as up to date as possible at all times.**

## 2026-10-17, round 3 (all confirmed)
- **Actions only through official APIs.** The program never logs into bank websites. Accounts without an action API stay read-only until one exists. Today: Stripe Link (read + act), Zelle via Chase (maybe, Teller payments beta), brokerages like Alpaca/Schwab (trade); Chase, Amex, Venmo, X Money are read-only.
- **Approval is reused, never built.** Use the provider's own approval where it has one (e.g. Link). Otherwise use an existing service that prompts the owner's phone to approve the exact action with Face ID/passkey (research pending: research/approval.md).
- **Freshness:** Teller/Plaid push updates where available (seconds to minutes); SimpleFIN is the daily backup that catches anything missed. Each user brings their own provider accounts; setup walks them through it.
- **Every agent gets its own scoped key; every read and action is logged.**
- **Name: Money Bridge** (working). Public GitHub repo, MIT license.
- **Shape (summary):** connectors → local copy (everything, forever, one standard format) → actions → approval → permissions → log. Doors: CLI, MCP, API, live event feed. Not a tracking app, no UI, not hosted, no website automation. One person per install, runs on any computer.

## 2026-10-17, build-as-little-as-possible rule
- **Reuse first, build last.** For every provider and every piece, use in this order: (1) the provider's official MCP / CLI / API as-is (e.g. Alpaca's official MCP, Stripe Link's official CLI/MCP), (2) big, healthy open-source projects, (3) only then build our own, and only for gaps, as long as the reused piece fits the requirements above.
- Money Bridge is therefore mostly an **assembly** of existing MCPs, CLIs and APIs, plus the thin glue nobody else provides.

## 2026-10-17, round 4
- **No agentgateway, and no separate gateway program.** Money Bridge is itself the program. It *has* an MCP server, a CLI and an API; it is not "just an MCP". Behind the scenes it runs the official provider MCPs/CLIs/APIs, holds their keys, passes read tools through, and stops money tools for approval. Agents never hold keys that can move money. Use an existing MCP library's pass-through/proxy feature rather than writing that plumbing.

## 2026-10-17, round 5 (all approved)
- **Local copy: our own, in SQLite.** Breadbox is not the core (AGPL, Postgres, single maintainer, and the hard parts would still be ours); it may be an optional source for people already running it. Borrow MIT-licensed sync code from Fungible, Actual Sync Hub and bank-mcp where useful.
- **Approval: provider-native first** (Link, Mercury), **Cosignet for everything else.** Only the action details (amount, payee, account name) go to Cosignet's cloud, never balances or history. If Cosignet fails qualification, money actions for that provider stay off.
- **Data sources: support all three aggregators.** Build order: SimpleFIN first (Johan already has it), then Plaid (live updates, formal bank agreements, only route to X Money), then Teller (only for Zelle sending from Chase, if its beta works). Each user connects whichever they have.
- **No dlt.** Fetch with each provider's official SDK and write straight into SQLite.

## 2026-10-17, after the design debate
- Design debate resolved: debate/RESOLUTION.md (Astra's design as the base, plus accepted changes and Fable's M13 ruling).
- **No live money test.** Johan doesn't want a small real-money pilot. Money actions are verified with fakes and provider sandboxes/paper accounts only.

## 2026-10-17, final design questions
- **Agents may do anything on Johan's machine.** Toy keeps running as `johan` with full sudo/docker access; no limited agent user. Owner-accepted risk: on this install the approval gate protects against agent mistakes and prompt injection through Money Bridge's normal doors, not against an agent that deliberately uses root to read the executor's keys. Money actions are allowed on Johan's install anyway. The product still ships executor isolation for everyone else; running agents with admin access is an explicit owner opt-in ("trusted agent host") recorded at setup.
- **No standing approvals in v1.** Every money move needs a fresh approval; agents may prepare recurring payments and ask.
- **Sync schedule:** Plaid and Teller polled every 2 minutes (backing off automatically on rate limits); SimpleFIN 4 times a day; a "refresh now" command within limits. No Tailscale Funnel by default; webhooks stay an optional switch.

## Open
- Research done: existing-tools.md, provider-routes.md, existing-agent-finance-layers.md, approval.md, assembly.md (all in research/).
- Design debate done. Next: final grilling (repo, test strategy), then module plan and BUILD-GOAL.md.
