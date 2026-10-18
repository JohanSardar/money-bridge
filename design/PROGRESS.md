# Progress

One line per unit. Rules: design/BUILD-GOAL.md. Statuses of record: features.yaml.

## Units
- DONE design: grilling, research, independent designs, debate, Fable ruling (design/, research/).
- DONE 2026-10-17 setup: public repo JohanSardar/money-bridge created; gh authenticated on this machine.
- DONE 2026-10-17 secrets search: no SimpleFIN access URL or setup token on this machine or the Air (only public demo tokens quoted from SimpleFIN docs). Real SimpleFIN level LIMITED; sandbox uses the public demo token (verified working end to end: claim, accounts, holdings extension).
- DONE 2026-10-17 spec: design/SPEC.md, GLOSSARY.md, PRINCIPLES.md, docs/adr/0001-0008, features.yaml + scripts/check_features.py, zero-comment lint, import-boundary test, CI. m0.quality-gates done.
- VERIFIED: sqlcipher3 0.6.4 bundles SQLCipher 4.x wheels for Linux/macOS/Windows; `systemd-creds --user` works without root here.
- NEXT: M1 read bridge (worker).
- DONE 2026-10-17 kernel: Money, canonical JSON/digest/stable ids, Clock (system + test offset file), profiles, error codes; unit tests.
