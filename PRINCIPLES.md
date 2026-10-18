# Money Bridge engineering principles (binding)

If `design/SPEC.md` conflicts with this file, this file wins for how code is written; `design/DECISIONS.md` wins for what is built.

## P1. Verified by running the real thing
A unit is done when its E2E scenarios pass through the real doors (CLI, MCP, HTTP) against real processes at their assigned level (sim, sandbox, real). Reading code is not verification. Merge on green; there are no review gates.

## P2. Test through the largest interface that reaches the behaviour
1. E2E through the doors with fake providers as real processes.
2. Module interface with its real SQLCipher database and external fakes.
3. Unit tests only for pure logic the rungs above cannot isolate: canonical digests, revision identity, decimal parsing, grant evaluation, time math, mapping edge cases.
No mocks of internal collaborators. Fakes exist only at external seams: providers, approval service, broker, clock, OS.

## P3. Deep modules, small interfaces
Five modules (Evidence store, Source host, Action executor, Access boundary, Installation/host adapter) plus a kernel of value types. A module imports only another module's public interface; the import rule is a test. A new module needs a written interface in SPEC.md first and must pass the deletion test.

## P4. Reuse before build
Official provider MCPs, CLIs and SDKs as-is; then big healthy open source; build only the glue. Record any exception in an ADR.

## P5. Zero comments
No comments in Money Bridge code, tests or scripts. Names and types carry meaning; rationale lives in SPEC.md or `docs/adr/`. `scripts/check_no_comments.py` fails the build on any comment token except a shebang line.

## P6. One paved path
One way to add an operation (the registry), a provider (a `ReadAdapter` or `ExecutionAdapter`), a migration (numbered SQL file) and a scenario (pytest in `tests/e2e`). Copy the first one; extract helpers only when the second appears.

## P7. Fail closed
Unknown grant dimensions, unknown tools, unverifiable approvals, failed audit writes, missing secret stores and unknown provider outcomes all stop the operation. Never a plaintext fallback, never a blind retry of a money call.

## P8. Correction ladder
Fix every mistake at the highest rung that works: make it impossible (types, module boundary, DB constraint), then a lint/test check, then documentation.

## P9. No personal data in git
Fixtures are synthetic. Never commit account numbers, balances, transactions, payee names, tokens, access URLs, emails or IPs from real accounts.

## P10. Truthful status
`features.yaml` and `design/PROGRESS.md` say exactly what passes at which level. Anything needing the owner's identity is `limited` with the smallest step the owner must take.
