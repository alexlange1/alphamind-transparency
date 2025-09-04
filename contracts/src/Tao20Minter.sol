// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./NAVOracle.sol";

interface IEd25519Verify {
    function verify(bytes32 message, bytes32 pubkey, bytes32 r, bytes32 s) external pure returns (bool);
}

interface IStakingV2 {
    function addStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    function removeStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    function getStake(bytes32 hotkey) external view returns (uint256);
}

/**
 * @title Tao20Minter (LEGACY)
 * @dev DEPRECATED: Use TAO20Core.sol instead
 * 
 * This contract is kept for reference but should not be used.
 * The new architecture is implemented in TAO20Core.sol with:
 * - Direct Bittensor staking integration
 * - Simplified Ed25519 signature verification
 * - Yield-based NAV calculation
 * - Clean anti-dilution mechanism
 */
contract Tao20Minter is ERC20, Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;
    
    // ===================== Constants =====================
    
    IEd25519Verify constant ED = IEd25519Verify(0x0000000000000000000000000000000000000402);
    IStakingV2 constant STAKE = IStakingV2(0x0000000000000000000000000000000000000805);
    address constant TAO_TOKEN = 0x0000000000000000000000000000000000000001; // Placeholder for local testing
    
    // ===================== EIP-712 Domain Separator =====================
    
    bytes32 public constant EIP712_DOMAIN_TYPEHASH = keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
    bytes32 public DOMAIN_SEPARATOR;
    bytes32 public constant DEPOSIT_ATTESTATION_TYPEHASH = keccak256(
        "DepositAttestation(bytes32 depositId,uint256 amount,uint16 netuid,bytes32 blockHash,uint32 extrinsicIndex,uint64 finalityHeight,uint256 chainId,uint256 nonce)"
    );
    
    // ===================== Structs =====================
    
    struct DepositRef {
        bytes32 blockHash;
        uint32 extrinsicIndex;
        bytes32 ss58Pubkey;
        uint256 amount;
        uint16 netuid;
    }
    
    struct Claim {
        address claimer;
        bytes32 nonce;
        uint64 expires;
    }
    
    struct QueueItem {
        bytes32 id;
        address user;
        uint256 amount; // alphaAmount for mint, shares for redeem
        uint16 netuid;
        uint256 queuedAt;
    }
    
    // ===================== State Variables =====================
    
    NAVOracle public navOracle;
    mapping(bytes32 => bool) public seenDeposit;
    mapping(address => bytes32) public nonces;
    mapping(address => bool) public authorizedKeepers;
    mapping(uint16 => address) public alphaTokenAddresses;
    mapping(address => bool) public validators;
    mapping(bytes32 => mapping(address => bool)) public hasAttested;
    mapping(bytes32 => uint256) public attestationCount;
    
    QueueItem[] public mintQueue;
    QueueItem[] public redeemQueue;
    
    uint256 public minExecutionDelay;
    uint256 public maxExecutionDelay;
    uint256 public attestationThreshold;
    
    // ===================== Modifiers =====================
    
    modifier onlyKeeper() {
        require(authorizedKeepers[msg.sender] || msg.sender == owner(), "Not authorized keeper");
        _;
    }
    
    modifier onlyValidator() {
        require(validators[msg.sender], "Not authorized validator");
        _;
    }
    
    // ===================== Events =====================
    
    event ClaimQueued(bytes32 indexed depositId, address indexed claimer, uint256 amount, uint16 netuid);
    event RedeemQueued(bytes32 indexed redeemId, address indexed redeemer, uint256 shares);
    event BatchMintExecuted(uint256 itemsProcessed, uint256 totalTao20Minted, uint256 totalAlphaValue);
    event BatchRedeemExecuted(uint256 itemsProcessed, uint256 totalSharesBurned, uint256 totalValueReturned);
    event AttestationSubmitted(bytes32 indexed depositId, address indexed validator);
    
    // ===================== Constructor =====================
    
    constructor(address _navOracle) ERC20("TAO20 Index Token", "TAO20") Ownable(msg.sender) {
        navOracle = NAVOracle(_navOracle);

        DOMAIN_SEPARATOR = keccak256(abi.encode(
            EIP712_DOMAIN_TYPEHASH,
            keccak256(bytes("TAO20 Minter")),
            keccak256(bytes("1")),
            block.chainid,
            address(this)
        ));

        // Default configuration
        minExecutionDelay = 300; // 5 minutes
        maxExecutionDelay = 3600; // 1 hour
        attestationThreshold = 3;
    }
    
    // ===================== User Functions =====================
    
    function claimMint(
        DepositRef calldata dep,
        Claim calldata c,
        bytes32 r, bytes32 s,
        bytes32 messageHash
    ) external nonReentrant whenNotPaused {
        require(block.timestamp < c.expires, "Claim expired");
        require(nonces[c.claimer] == c.nonce, "Invalid nonce");
        
        nonces[c.claimer] = bytes32(uint256(nonces[c.claimer]) + 1);
        
        bool ok = ED.verify(messageHash, dep.ss58Pubkey, r, s);
        require(ok, "Invalid ed25519 signature");

        bytes32 depositId = keccak256(abi.encodePacked(
            dep.blockHash, dep.extrinsicIndex, dep.ss58Pubkey, dep.amount, dep.netuid
        ));
        require(!seenDeposit[depositId], "Deposit already claimed");
        require(attestationCount[depositId] >= attestationThreshold, "Insufficient attestations");

        seenDeposit[depositId] = true;
        mintQueue.push(QueueItem({
            id: depositId,
            user: c.claimer,
            amount: dep.amount,
            netuid: dep.netuid,
            queuedAt: block.timestamp
        }));
        
        emit ClaimQueued(depositId, c.claimer, dep.amount, dep.netuid);
    }

    function redeem(uint256 shares, address receiver) external nonReentrant whenNotPaused {
        require(shares > 0, "Zero shares");
        require(receiver != address(0), "Invalid receiver");
        
        _transfer(msg.sender, address(this), shares);
        
        bytes32 redeemId = keccak256(abi.encodePacked(msg.sender, shares, block.timestamp, nonces[msg.sender]));
        nonces[msg.sender] = bytes32(uint256(nonces[msg.sender]) + 1);
        
        redeemQueue.push(QueueItem({
            id: redeemId,
            user: receiver,
            amount: shares,
            netuid: 0,
            queuedAt: block.timestamp
        }));
        
        emit RedeemQueued(redeemId, receiver, shares);
    }
    
    // ===================== Keeper Functions =====================
    
    function executeMintBatch(uint256 maxItems) external onlyKeeper nonReentrant whenNotPaused {
        uint256 itemsToProcess = Math.min(mintQueue.length, maxItems);
        require(itemsToProcess > 0, "Empty queue");
        
        uint256 totalTao20ToMint = 0;
        uint256 totalAlphaValue = 0;
        
        for (uint i = 0; i < itemsToProcess; i++) {
            QueueItem storage item = mintQueue[mintQueue.length - 1 - i];
            
            require(block.timestamp >= item.queuedAt + minExecutionDelay, "Too early");
            require(block.timestamp <= item.queuedAt + maxExecutionDelay, "Expired");
            
            uint256 taoReceived = _convertAlphaToTao(item.amount, item.netuid);
            totalAlphaValue += taoReceived;
            
            uint256 tao20Amount = navOracle.getNAVForMinting(taoReceived);
            totalTao20ToMint += tao20Amount;
            
            _mint(item.user, tao20Amount);
            
            _autoStakeUnderlying(taoReceived, item.netuid);
        }
        
        // Remove processed items from the queue
        for (uint256 i = 0; i < itemsToProcess; i++) {
            mintQueue.pop();
        }
        
        emit BatchMintExecuted(itemsToProcess, totalTao20ToMint, totalAlphaValue);
    }
    
    function executeRedeemBatch(uint256 maxItems) external onlyKeeper nonReentrant whenNotPaused {
        uint256 itemsToProcess = Math.min(redeemQueue.length, maxItems);
        require(itemsToProcess > 0, "Empty redeem queue");
        
        uint256 totalSharesBurned = 0;
        uint256 totalValueReturned = 0;
        
        for (uint i = 0; i < itemsToProcess; i++) {
            QueueItem storage item = redeemQueue[redeemQueue.length - 1 - i];
            
            require(block.timestamp >= item.queuedAt + minExecutionDelay, "Too early");
            require(block.timestamp <= item.queuedAt + maxExecutionDelay, "Expired");
            
            uint256 redemptionValue = navOracle.getTAOForRedemption(item.amount);
            totalValueReturned += redemptionValue;
            totalSharesBurned += item.amount;
            
            _burn(address(this), item.amount);
            
            _transferProceeds(item.user, redemptionValue);
        }
        
        // Remove processed items from the queue
        for (uint256 i = 0; i < itemsToProcess; i++) {
            redeemQueue.pop();
        }
        
        emit BatchRedeemExecuted(itemsToProcess, totalSharesBurned, totalValueReturned);
    }
    
    // ===================== Internal Batch Functions (Reentrancy Fix) =====================
    
    function _executeMintBatchInternal(uint256 maxItems) internal {
        uint256 itemsToProcess = Math.min(mintQueue.length, maxItems);
        require(itemsToProcess > 0, "Empty queue");
        
        uint256 totalTao20ToMint = 0;
        uint256 totalAlphaValue = 0;
        
        for (uint i = 0; i < itemsToProcess; i++) {
            QueueItem storage item = mintQueue[mintQueue.length - 1 - i];
            
            require(block.timestamp >= item.queuedAt + minExecutionDelay, "Too early");
            require(block.timestamp <= item.queuedAt + maxExecutionDelay, "Expired");
            
            uint256 taoReceived = _convertAlphaToTao(item.amount, item.netuid);
            totalAlphaValue += taoReceived;
            
            uint256 tao20Amount = navOracle.getNAVForMinting(taoReceived);
            totalTao20ToMint += tao20Amount;
            
            _mint(item.user, tao20Amount);
            
            _autoStakeUnderlying(taoReceived, item.netuid);
        }
        
        // Remove processed items from the queue
        for (uint256 i = 0; i < itemsToProcess; i++) {
            mintQueue.pop();
        }
        
        emit BatchMintExecuted(itemsToProcess, totalTao20ToMint, totalAlphaValue);
    }
    
    function _executeRedeemBatchInternal(uint256 maxItems) internal {
        uint256 itemsToProcess = Math.min(redeemQueue.length, maxItems);
        require(itemsToProcess > 0, "Empty redeem queue");
        
        uint256 totalSharesBurned = 0;
        uint256 totalValueReturned = 0;
        
        for (uint i = 0; i < itemsToProcess; i++) {
            QueueItem storage item = redeemQueue[redeemQueue.length - 1 - i];
            
            require(block.timestamp >= item.queuedAt + minExecutionDelay, "Too early");
            require(block.timestamp <= item.queuedAt + maxExecutionDelay, "Expired");
            
            uint256 redemptionValue = navOracle.getTAOForRedemption(item.amount);
            totalValueReturned += redemptionValue;
            totalSharesBurned += item.amount;
            
            _burn(address(this), item.amount);
            
            _transferProceeds(item.user, redemptionValue);
        }
        
        // Remove processed items from the queue
        for (uint256 i = 0; i < itemsToProcess; i++) {
            redeemQueue.pop();
        }
        
        emit BatchRedeemExecuted(itemsToProcess, totalSharesBurned, totalValueReturned);
    }

    function executeBatch(uint256 maxItems) external onlyKeeper nonReentrant whenNotPaused {
        // Generic batch execution that processes both mint and redeem queues
        // Prioritize mint queue execution
        if (mintQueue.length > 0) {
            _executeMintBatchInternal(maxItems);
        } else if (redeemQueue.length > 0) {
            _executeRedeemBatchInternal(maxItems);
        } else {
            revert("No items in queue to execute");
        }
    }
    
    // ===================== Attestation =====================
    
    function submitAttestation(bytes32 depositId, bytes calldata signature) external onlyValidator {
        require(!hasAttested[depositId][msg.sender], "Already attested");
        
        bytes32 structHash = keccak256(abi.encode(
            DEPOSIT_ATTESTATION_TYPEHASH,
            depositId,
            nonces[msg.sender]
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", DOMAIN_SEPARATOR, structHash));
        address signer = ECDSA.recover(digest, signature);
        require(signer == msg.sender, "Invalid signature");
        
        nonces[msg.sender] = bytes32(uint256(nonces[msg.sender]) + 1);
        hasAttested[depositId][msg.sender] = true;
        attestationCount[depositId]++;
        
        emit AttestationSubmitted(depositId, msg.sender);
    }

    // ===================== Internal Functions =====================
    
    function _convertAlphaToTao(uint256 alphaAmount, uint16 netuid) internal returns (uint256) {
        // In production, this would involve DEX swaps. For now, we simulate a 1:1 conversion
        return alphaAmount;
    }
    
    function _autoStakeUnderlying(uint256 taoAmount, uint16 netuid) internal {
        // Staking logic
    }
    
    function _transferProceeds(address receiver, uint256 amount) internal {
        require(receiver != address(0), "Invalid receiver address");
        require(amount > 0, "Invalid transfer amount");
        require(receiver != address(this), "Cannot transfer to self");
        
        // Transfer actual TAO tokens from contract's holdings to the receiver
        // This is the proper redemption mechanism - burning TAO20 and returning underlying TAO
        IERC20(TAO_TOKEN).safeTransfer(receiver, amount);
    }
    
    // ===================== Admin Functions =====================
    
    function setKeeper(address keeper, bool authorized) external onlyOwner {
        authorizedKeepers[keeper] = authorized;
    }
    
    function setValidators(address[] calldata _validators, uint256 _threshold) external onlyOwner {
        require(_threshold > 0 && _threshold <= _validators.length, "Invalid threshold");
        
        // Clear existing validators
        for (uint256 i = 0; i < _validators.length; i++) {
            validators[_validators[i]] = false;
        }
        
        // Set new validators
        for (uint256 i = 0; i < _validators.length; i++) {
            validators[_validators[i]] = true;
        }
        
        attestationThreshold = _threshold;
    }
    
    function isAttestationThresholdMet(bytes32 depositId) external view returns (bool) {
        return attestationCount[depositId] >= attestationThreshold;
    }
    
    function setExecutionDelay(uint256 min, uint256 max) external onlyOwner {
        require(min < max, "Min > max");
        minExecutionDelay = min;
        maxExecutionDelay = max;
    }
    
    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }
}
