# Official provider tools: probe results (2026-10-17, build leader)

Probed locally without any account. Facts below were observed by running the released packages.

## Alpaca MCP server (`alpaca-mcp-server` 2.4.0 on PyPI, MIT, github.com/alpacahq/alpaca-mcp-server)
- Python package built on FastMCP: `alpaca_mcp_server.server.build_server()` generates tools from bundled Alpaca OpenAPI specs (`specs/trading-api.json`, `specs/market-data-api.json`) at process start.
- Loads and lists tools with dummy `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`; no network needed to list. 72 tools in 2.4.0, including money tools `place_stock_order`, `place_crypto_order`, `place_option_order`, `replace_order_by_id`, `cancel_order_by_id`, `cancel_all_orders`, `close_position`, `close_all_positions`, `exercise_options_position`, `update_account_config`, and the recovery read `get_order_by_client_id`.
- Env: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER_TRADE` (default true → `https://paper-api.alpaca.markets`; false → live), `ALPACA_TOOLSETS`, `DATA_API_URL` (market data base URL override), `ALPACA_MCP_USER_AGENT`.
- The trading base URL is a module constant `TRADING_API_BASE_URLS` with no env override. Sim-level plan: a test-only launcher (`tests/fakes/alpaca_official_launcher.py`) imports the official package, points `TRADING_API_BASE_URLS["paper"]` and `DATA_API_URL` at the fake Alpaca REST server, then runs the official server over stdio. Production launches the official entry point unchanged with `ALPACA_PAPER_TRADE=true` until a live route is owner-enabled.
- Tool annotations are mostly absent (`readOnlyHint` None), confirming they cannot serve as classifications; the pinned manifest must classify every tool.

## Stripe Link CLI (`@stripe/link-cli` 0.28.0 on npm, MIT, github.com/stripe/link-cli)
- Node CLI (`dist/cli.js`). `link-cli --llms-full` prints the full command reference (523 lines in 0.28.0) without authentication: usable as the pinned manifest (digest it).
- Commands relevant to Money Bridge: `auth login|status|logout|upgrade`, `sources list`, `transactions list [--start-date --end-date --source]`, `balances list`, `insights list`, `payment-methods list|retrieve`, `approval-policy retrieve`, `spend-request create|retrieve|cancel` (Link's native approval in the Link app), `mpp decode|pay` (machine payment protocol, merchant API payments).
- `--mcp` mode exposes only four meta-tools (`search_tools`, `get_tool_details`, `call_read_tool`, `call_write_tool`), which cannot be pinned per operation. Money Bridge therefore invokes the CLI with fixed argument arrays and `--format json`, never the meta-tool MCP.
- Env overrides present in the bundle: `LINK_API_BASE_URL` (default `https://api.link.com`), `LINK_AUTH_BASE_URL` (default `https://login.link.com`), `LINK_AUTH_FILE`, `LINK_ACCESS_TOKEN`, `LINK_REFRESH_TOKEN`, `LINK_NO_REFRESH`, `LINK_HTTP_PROXY`. Sim-level plan: run the official CLI against a fake Link API via `LINK_API_BASE_URL`/`LINK_AUTH_BASE_URL` with a private `LINK_AUTH_FILE` in the executor's directory.
- `spend-request retrieve --include card` can release card credentials to a file; the executor must never request or forward them except into its own private temporary storage for an approved MPP payment.
- Installing it runs a `postinstall` that globally installs agent skills (`npx skills add stripe/link-cli -g`) into `~/.claude/skills`, `~/.grok/skills` and `~/.agents`. Always install with `npm install --ignore-scripts` (or `LINK_CLI_SKIP_SKILL_INSTALL=1`) into a private prefix; the executor must never trigger it.
