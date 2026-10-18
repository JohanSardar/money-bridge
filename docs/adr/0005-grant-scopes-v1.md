# v1 grants: operation scopes plus account and connection allowlists

Per design/debate/FABLE-M13.md: grants carry operations (data kind in the name), accounts, connections and expiry; `read:raw` is separate and off by default. Field and date-range restrictions are reserved and added later without breaking keys; unknown dimensions are rejected so downgrades fail closed.
