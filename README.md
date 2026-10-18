# Money Bridge

Money Bridge is a free, open-source (MIT) program you run on your own computer to give the AI agents you choose scoped, audited access to your finances. It reads your accounts through official aggregators and provider tools (SimpleFIN, Plaid, Teller, Stripe Link, Alpaca, file imports), keeps every observed fact forever in an encrypted local store, and exposes it through a CLI, an MCP server, an HTTP API and a live event feed. Money actions go only through official APIs, and each one needs your own passkey approval.

It is not a budgeting app, has no UI, is not hosted, and never automates bank websites.

Status: under construction. See `design/SPEC.md`, `features.yaml` and `design/PROGRESS.md`.
