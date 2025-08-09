# TAO20 Implementation Roadmap

Phases & Milestones
- Phase 0 (1–2w): Specs lock, parameter registry, diagrams
- Phase 1 (3–5w): Core contracts (Token, Vault, Router, FeeMgr, ValidatorSet, Params, Slashing)
- Phase 2 (4–6w): Miners/Validators (aggregation, quorum, slashing, TWAP, circuit breakers)
- Phase 3 (2–3w): AMM basket router and execution
- Phase 4 (3–4w): Frontend & SDKs
- Phase 5 (3–5w): Testing, fuzz, formal checks
- Phase 6 (3–4w): Audit, runbooks
- Phase 7 (2–3w): Genesis launch & ops

Key Tickets (examples)
- SC-012: `mintWithTAO` basket-swap w/ weighted slippage ≤1% and NAV issuance
- VAL-021: Stake-weighted median emissions → `setTargetWeights`
- MIN-034: 60s price feed; block-pinned quotes + signatures
- OPS-007: Circuit breaker runbook & TWAP liquidation job
- FE-015: Mint flow UI with NAV and minOut guard


