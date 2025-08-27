// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title TAO20Index
 * @dev Decentralized index token tracking top 20 Bittensor subnets
 */
contract TAO20Index is Ownable(msg.sender), ReentrancyGuard {
    // Token details
    string public constant name = "TAO20 Index";
    string public constant symbol = "TAO20";
    uint8 public constant decimals = 18;

    // Bittensor integration
    address public constant STAKING_PRECOMPILE = address(0x801);
    address public constant ED25519_VERIFY = address(0x402);
    
    // Index configuration
    uint256 public constant MAX_SUBNETS = 20;
    uint256 public constant MIN_HOLDING_PERIOD = 3600; // 1 hour
    
    // State variables
    uint256 public totalSupply;
    uint256 public currentEpoch;
    
    // Subnet weights (netuid -> weight percentage, scaled by 1e18)
    mapping(uint256 => uint256) public subnetWeights;
    uint256[] public activeSubnets;
    
    // Balances and allowances
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    
    // Miner tracking
    mapping(bytes32 => uint256) public minerVolume;
    mapping(address => uint256) public lastMintTime;
    
    // Events
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event MintInKind(
        address indexed minter,
        uint256 amount,
        bytes32 indexed minerHotkey,
        uint256 timestamp
    );
    event RedeemInKind(
        address indexed redeemer,
        uint256 amount,
        bytes32 indexed minerHotkey,
        uint256 timestamp
    );
    event WeightsUpdated(uint256[] subnets, uint256[] weights, uint256 epoch);

    modifier onlyAfterHoldingPeriod(address account) {
        require(
            block.timestamp >= lastMintTime[account] + MIN_HOLDING_PERIOD,
            "TAO20: Holding period not met"
        );
        _;
    }

    constructor() {
        currentEpoch = 1;
    }

    /**
     * @dev Mint TAO20 tokens by depositing the required basket of subnet tokens
     */
    function mintInKind(
        uint256 amount,
        bytes32 minerHotkey,
        bytes calldata signature,
        bytes calldata message
    ) external nonReentrant {
        require(amount > 0, "TAO20: Amount must be positive");
        require(activeSubnets.length > 0, "TAO20: No active subnets");
        
        require(
            _verifyMinerSignature(minerHotkey, signature, message),
            "TAO20: Invalid miner signature"
        );
        
        require(
            _verifySubnetTokenDeposits(amount),
            "TAO20: Insufficient subnet token deposits"
        );
        
        totalSupply += amount;
        balanceOf[msg.sender] += amount;
        lastMintTime[msg.sender] = block.timestamp;
        minerVolume[minerHotkey] += amount;
        
        emit MintInKind(msg.sender, amount, minerHotkey, block.timestamp);
        emit Transfer(address(0), msg.sender, amount);
    }

    /**
     * @dev Redeem TAO20 tokens for the underlying subnet token basket
     */
    function redeemInKind(
        uint256 amount,
        bytes32 minerHotkey,
        bytes calldata signature,
        bytes calldata message
    ) external nonReentrant onlyAfterHoldingPeriod(msg.sender) {
        require(amount > 0, "TAO20: Amount must be positive");
        require(balanceOf[msg.sender] >= amount, "TAO20: Insufficient balance");
        require(activeSubnets.length > 0, "TAO20: No active subnets");
        
        require(
            _verifyMinerSignature(minerHotkey, signature, message),
            "TAO20: Invalid miner signature"
        );
        
        balanceOf[msg.sender] -= amount;
        totalSupply -= amount;
        
        _transferOutSubnetTokens(amount, msg.sender);
        minerVolume[minerHotkey] += amount;
        
        emit RedeemInKind(msg.sender, amount, minerHotkey, block.timestamp);
        emit Transfer(msg.sender, address(0), amount);
    }

    /**
     * @dev Update index weights (owner only)
     */
    function updateWeights(
        uint256[] calldata subnets,
        uint256[] calldata weights
    ) external onlyOwner {
        require(
            subnets.length == weights.length,
            "TAO20: Arrays length mismatch"
        );
        require(
            subnets.length <= MAX_SUBNETS,
            "TAO20: Too many subnets"
        );
        
        // Clear existing weights
        for (uint256 i = 0; i < activeSubnets.length; i++) {
            subnetWeights[activeSubnets[i]] = 0;
        }
        
        // Set new weights
        uint256 totalWeight = 0;
        activeSubnets = new uint256[](subnets.length);
        
        for (uint256 i = 0; i < subnets.length; i++) {
            require(weights[i] > 0, "TAO20: Weight must be positive");
            subnetWeights[subnets[i]] = weights[i];
            activeSubnets[i] = subnets[i];
            totalWeight += weights[i];
        }
        
        require(
            totalWeight == 1e18,
            "TAO20: Weights must sum to 1e18"
        );
        
        currentEpoch++;
        
        emit WeightsUpdated(subnets, weights, currentEpoch);
    }

    /**
     * @dev Get current index composition
     */
    function getIndexComposition() external view returns (
        uint256[] memory subnets,
        uint256[] memory weights
    ) {
        subnets = activeSubnets;
        weights = new uint256[](subnets.length);
        
        for (uint256 i = 0; i < subnets.length; i++) {
            weights[i] = subnetWeights[subnets[i]];
        }
    }

    /**
     * @dev Get miner volume for a specific hotkey
     */
    function getMinerVolume(bytes32 minerHotkey) external view returns (uint256) {
        return minerVolume[minerHotkey];
    }

    // ERC20 functions
    function transfer(address to, uint256 amount) external returns (bool) {
        require(to != address(0), "TAO20: Transfer to zero address");
        require(balanceOf[msg.sender] >= amount, "TAO20: Insufficient balance");
        
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(to != address(0), "TAO20: Transfer to zero address");
        require(balanceOf[from] >= amount, "TAO20: Insufficient balance");
        require(allowance[from][msg.sender] >= amount, "TAO20: Insufficient allowance");
        
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        allowance[from][msg.sender] -= amount;
        
        emit Transfer(from, to, amount);
        return true;
    }

    // Internal functions
    function _verifyMinerSignature(
        bytes32 minerHotkey,
        bytes calldata signature,
        bytes calldata message
    ) internal view returns (bool) {
        (bool success, bytes memory result) = ED25519_VERIFY.staticcall(
            abi.encodeWithSignature(
                "verify(bytes32,bytes,bytes)",
                minerHotkey,
                signature,
                message
            )
        );
        
        if (!success) return false;
        return abi.decode(result, (bool));
    }

    function _verifySubnetTokenDeposits(uint256 tao20Amount) internal view returns (bool) {
        address contractSubstrate = _getSubstrateAddress(address(this));
        
        for (uint256 i = 0; i < activeSubnets.length; i++) {
            uint256 netuid = activeSubnets[i];
            uint256 requiredStake = (tao20Amount * subnetWeights[netuid]) / 1e18;
            
            uint256 actualStake = _getSubnetStake(contractSubstrate, netuid);
            
            if (actualStake < requiredStake) {
                return false;
            }
        }
        
        return true;
    }

    function _transferOutSubnetTokens(uint256 tao20Amount, address redeemer) internal {
        address redeemerSubstrate = _getSubstrateAddress(redeemer);
        
        for (uint256 i = 0; i < activeSubnets.length; i++) {
            uint256 netuid = activeSubnets[i];
            uint256 transferAmount = (tao20Amount * subnetWeights[netuid]) / 1e18;
            
            if (transferAmount > 0) {
                _transferSubnetStake(netuid, transferAmount, redeemerSubstrate);
            }
        }
    }

    function _getSubstrateAddress(address evmAddress) internal pure returns (address) {
        // TODO: Implement proper conversion
        return evmAddress;
    }

    function _getSubnetStake(address coldkey, uint256 netuid) internal view returns (uint256) {
        (bool success, bytes memory result) = STAKING_PRECOMPILE.staticcall(
            abi.encodeWithSignature(
                "getTotalColdkeyStake(address,uint256)",
                coldkey,
                netuid
            )
        );
        
        if (!success) return 0;
        return abi.decode(result, (uint256));
    }

    function _transferSubnetStake(
        uint256 netuid,
        uint256 amount,
        address toColdkey
    ) internal {
        (bool success,) = STAKING_PRECOMPILE.call(
            abi.encodeWithSignature(
                "transferStake(uint256,uint256,address,address)",
                netuid,
                amount,
                address(this),
                toColdkey
            )
        );
        
        require(success, "TAO20: Stake transfer failed");
    }
}
