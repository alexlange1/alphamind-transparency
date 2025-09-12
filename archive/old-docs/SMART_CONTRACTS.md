# 🛡️ TAO20 Smart Contracts: Security & Design

## 🎯 Overview

The TAO20 smart contract suite is engineered to be **bulletproof, ironclad, and completely immune to gaming**. The architecture is designed with a security-in-depth approach, combining robust access control, manipulation-resistant mechanisms, and real-time validation to create a trustless on-chain environment for the TAO20 index fund.

This document provides a detailed overview of each core contract, its purpose, and its key security features.

---

## 🏗️ Core Contracts

### **1. `NAVOracle.sol`**
- **Purpose**: To provide a single, un-gameable source of truth for the Net Asset Value (NAV) of the TAO20 token. This is the cornerstone of the entire system's security and pricing accuracy.
- **Key Security Features**:
  - **Multi-Validator Consensus**: Requires a configurable number of authorized validators (e.g., 3) to submit NAV calculations before a consensus can be reached.
  - **Stake-Weighted Averaging**: The final consensus NAV is a weighted average based on the stake of the participating validators, giving more influence to those with more skin in the game.
  - **Deviation Checks**: Rejects any validator submission that deviates more than a configurable percentage (e.g., 5%) from the current consensus, preventing outliers from manipulating the price.
  - **Anti-Replay Protection**: Uses an incrementing nonce for each validator, ensuring that a signed NAV submission can only be used once.
  - **EIP-712 Signatures**: Implements typed structured data hashing for signature verification, providing clarity to signers and preventing phishing attacks.
  - **Emergency Override**: `Ownable` functions allow a trusted owner to pause the contract or manually update the NAV in a black swan event.

### **2. `Tao20Minter.sol`**
- **Purpose**: To manage the complex, time-delayed minting and redemption process, ensuring fairness and preventing front-running.
- **Key Security Features**:
  - **Real-Time NAV Integration**: All minting and redemption calculations are performed using the real-time NAV provided by the `NAVOracle`, ensuring precise and fair value exchange.
  - **Time-Lock Execution Queue**: Implements a mandatory delay (e.g., 5 minutes) between a user queuing a mint/redeem request and a keeper executing it. This is a critical defense against front-running and MEV (Miner Extractable Value) attacks.
  - **Gas Griefing Protection**: All queue processing is done in fixed-size batches, preventing unbounded loops that could be exploited to cause transactions to run out of gas.
  - **Strict Access Control**: Only authorized "Keeper" addresses can execute the batches, and only authorized "Validator" addresses can submit attestations.
  - **Nonce-Based Replay Protection**: Each user action (claim, redeem, attest) is tied to a personal, incrementing nonce.

### **3. `Vault.sol`**
- **Purpose**: To securely hold the 20 underlying subnet tokens that back the TAO20 index. Its primary role is asset custody.
- **Key Security Features**:
  - **Composition Tolerance**: When a miner makes an in-kind deposit, this contract enforces that the basket's composition is within a strict tolerance (e.g., 1%) of the official portfolio weights for that epoch. This prevents miners from depositing undesirable assets.
  - **Emergency Circuit Breaker**: The owner can trigger an `emergencyStop` to halt all minting and redemption functions instantly. A mandatory `emergencyCooldown` period (e.g., 1 hour) must pass before the system can be resumed, providing time to assess and mitigate any threats.
  - **Slippage Protection**: For `mintViaTAO` operations, the contract enforces a maximum slippage (e.g., 0.5%) on every individual DEX trade performed by the router, preventing value loss due to price impact.
  - **Reentrancy Guard**: All major state-changing functions are protected by OpenZeppelin's `ReentrancyGuard`.
  - **Consolidated Configuration**: A single, `Ownable` function `updateConfig` is used to manage all key parameters, reducing the attack surface and preventing misconfiguration.

### **4. `TAO20.sol` (ERC-20 Token)**
- **Purpose**: The standard ERC-20 token contract representing a share in the Vault.
- **Security**: Based on the battle-tested OpenZeppelin ERC20 implementation. The `mint` and `burn` functions are restricted to only be callable by the `Vault` and `Minter` contracts, ensuring that the token supply always accurately reflects the assets held in the Vault.

---

## 🔄 Security-Focused Process Flows

### **Minting Flow**
1.  **User/Miner**: Delivers an asset basket to the `Vault`.
2.  **Vault**: Enforces `compTolBps` to ensure the basket composition is correct.
3.  **Validators**: Submit EIP-712 signed NAV calculations with a unique `nonce` to the `NAVOracle`.
4.  **NAVOracle**: Verifies signatures, checks for deviation, and achieves a stake-weighted consensus NAV.
5.  **Minter**: Verifies validator attestations and queues the mint request.
6.  **Time-Lock**: A mandatory `minExecutionDelay` begins.
7.  **Keeper**: After the delay, executes the mint.
8.  **Minter**: Fetches the **real-time, consensus NAV** from the `NAVOracle` and mints the precise amount of TAO20 tokens.

### **Redemption Flow**
1.  **User**: Burns TAO20 tokens by calling `redeem` on the `Minter` contract.
2.  **Minter**: Queues the redemption request, which includes the user's current `nonce`.
3.  **Time-Lock**: A mandatory `minExecutionDelay` begins.
4.  **Keeper**: After the delay, executes the redemption.
5.  **Minter**: Fetches the **real-time, consensus NAV** from the `NAVOracle` to calculate the exact amount of underlying assets to be returned.
6.  **Vault**: Releases the proportional basket of 20 assets to the user.
