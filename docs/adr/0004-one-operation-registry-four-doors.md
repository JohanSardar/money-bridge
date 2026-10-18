# One operation registry generates CLI, MCP, HTTP and the owner door

Every operation is declared once with its scope, types and handler; FastAPI routes, FastMCP tools and Typer commands are generated from it. This makes "same result and same denial on every door" structural rather than tested-in, and keeps the doors thin. Hand-written per-door handlers were rejected.
