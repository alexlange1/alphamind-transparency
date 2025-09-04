// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./IValidatorSet.sol";

/**
 * @title StakingNAVOracle
 * @dev Simplified NAV oracle that calculates value based on staking yields
 * 
 * This oracle provides real-time NAV calculation based on:
 * 1. Staked subnet token amounts
 * 2. Accumulated staking rewards
 * 3. Current subnet weightings from ValidatorSet
 */
contract StakingNAVOracle is Ownable {
    
    IValidatorSet public validatorSet;
    
    /// @dev Base price per subnet token (in 18 decimals)
    mapping(uint16 => uint256) public subnetBasePrices;
    
    /// @dev Last price update timestamp per subnet
    mapping(uint16 => uint256) public lastPriceUpdate;
    
    /// @dev Price update frequency (1 hour)
    uint256 public constant PRICE_UPDATE_FREQUENCY = 1 hours;
    
    event SubnetPriceUpdated(uint16 indexed netuid, uint256 newPrice, uint256 timestamp);
    
    constructor(address _validatorSet) Ownable(msg.sender) {
        validatorSet = IValidatorSet(_validatorSet);
        
        // Initialize with base prices (1.0 for all subnets)
        for (uint16 i = 1; i <= 20; i++) {
            subnetBasePrices[i] = 1e18;
        }
    }
    
    /**
     * @dev Get current NAV per TAO20 token
     * @param totalStaked Total amount staked across all subnets
     * @param totalYield Total accumulated yield
     * @param totalSupply Total TAO20 token supply
     */
    function getCurrentNAV(
        uint256 totalStaked,
        uint256 totalYield,
        uint256 totalSupply
    ) external view returns (uint256) {
        if (totalSupply == 0) return 1e18; // Initial NAV = 1.0
        
        uint256 totalValue = totalStaked + totalYield;
        return totalValue * 1e18 / totalSupply;
    }
    
    /**
     * @dev Get base price for a subnet (used for deposit valuation)
     * @param netuid Subnet ID
     */
    function getSubnetPrice(uint16 netuid) external view returns (uint256) {
        return subnetBasePrices[netuid];
    }
    
    /**
     * @dev Update subnet base price (owner only)
     * @param netuid Subnet ID
     * @param newPrice New price in 18 decimals
     */
    function updateSubnetPrice(uint16 netuid, uint256 newPrice) external onlyOwner {
        require(newPrice > 0, "Invalid price");
        require(
            block.timestamp >= lastPriceUpdate[netuid] + PRICE_UPDATE_FREQUENCY,
            "Update too frequent"
        );
        
        subnetBasePrices[netuid] = newPrice;
        lastPriceUpdate[netuid] = block.timestamp;
        
        emit SubnetPriceUpdated(netuid, newPrice, block.timestamp);
    }
    
    /**
     * @dev Batch update subnet prices
     * @param netuids Array of subnet IDs
     * @param prices Array of new prices
     */
    function batchUpdatePrices(
        uint16[] calldata netuids,
        uint256[] calldata prices
    ) external onlyOwner {
        require(netuids.length == prices.length, "Array length mismatch");
        require(netuids.length <= 20, "Too many updates");
        
        for (uint i = 0; i < netuids.length; i++) {
            if (prices[i] > 0 && block.timestamp >= lastPriceUpdate[netuids[i]] + PRICE_UPDATE_FREQUENCY) {
                subnetBasePrices[netuids[i]] = prices[i];
                lastPriceUpdate[netuids[i]] = block.timestamp;
                
                emit SubnetPriceUpdated(netuids[i], prices[i], block.timestamp);
            }
        }
    }
    
    /**
     * @dev Set validator set contract
     * @param _validatorSet New validator set address
     */
    function setValidatorSet(address _validatorSet) external onlyOwner {
        validatorSet = IValidatorSet(_validatorSet);
    }
    
    /**
     * @dev Get weighted portfolio value based on current subnet weights
     * @param amounts Array of subnet token amounts
     * @param netuids Array of subnet IDs
     */
    function getWeightedValue(
        uint256[] calldata amounts,
        uint16[] calldata netuids
    ) external view returns (uint256) {
        require(amounts.length == netuids.length, "Array length mismatch");
        
        uint256 totalValue = 0;
        
        for (uint i = 0; i < amounts.length; i++) {
            uint256 subnetValue = amounts[i] * subnetBasePrices[netuids[i]] / 1e18;
            totalValue += subnetValue;
        }
        
        return totalValue;
    }
}
