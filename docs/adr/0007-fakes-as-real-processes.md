# Fake providers, approver and broker run as real processes outside the package

E2E scenarios need an independent oracle: the fakes keep their own state and effect logs and speak the providers' wire protocols, so our normalization is never checked against itself. They live in tests/fakes/, are never installed, and the production profile refuses their trust roots, so they cannot become a backdoor.
