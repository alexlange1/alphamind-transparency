TAO20 System Architecture

Mermaid
```mermaid
graph TD
  U["Investor UI"] -->|Mint/Redeem| C["$TAO20 Contracts"]
  subgraph On-chain
    C --> V["Vault (basket holdings)"]
    C --> T["$TAO20 ERC-20"]
    C --> F["Fee Manager (0.2%/1%)"]
  end

  subgraph Oracle_Network[Oracle Network]
    M["Miners"] -->|signed: Emissions, Prices, NAV| A["Validator Aggregator"]
    A -->|stake-weighted median| O["On-chain Params (weights, eligibility)"]
    O --> C
  end

  AMM["Bittensor AMM Pools"] --> M
  AMM --> C
```

Interfaces
- Contracts: `Tao20Token`, `Tao20Vault`, `FeeTreasury`, `ValidatorSet`, `ParamRegistry`, `Slashing`
- Miner reports: `EmissionsReport`, `PriceReport`, `NavReport`
- Validator output: `WeightSet`

Cadence
- Prices: ~60s; Emissions: daily snapshot; Rebalance: every 14 days; Mgmt fee: monthly


