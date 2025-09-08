// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

/**
 * @title INAVOracle
 * @dev Interface for automated NAV Oracle (no validator involvement)
 */
interface INAVOracle {
    
    // ===================== EVENTS =====================
    
    event NAVUpdated(uint256 newNAV, uint256 timestamp);
    event SubnetPriceUpdated(uint16 indexed netuid, uint256 newPrice, uint256 timestamp);
    
    // ===================== ERRORS =====================
    
    error InvalidNAV();
    error NAVTooStale();
    error ZeroSupply();
    
    // ===================== FUNCTIONS =====================
    
    /**
     * @dev Get current NAV per token
     * @return NAV in 18 decimals (1e18 = 1.0)
     */
    function getCurrentNAV() external view returns (uint256);
    
    /**
     * @dev Get NAV calculation based on staking data
     * @param totalStaked Total amount staked across all subnets
     * @param totalYield Total accumulated yield
     * @param totalSupply Total TAO20 token supply
     * @return NAV in 18 decimals
     */
    function getCurrentNAV(
        uint256 totalStaked,
        uint256 totalYield,
        uint256 totalSupply
    ) external view returns (uint256);
    
    /**
     * @dev Get base price for a subnet token
     * @param netuid Subnet ID
     * @return Price in 18 decimals
     */
    function getSubnetPrice(uint16 netuid) external view returns (uint256);
    
    /**
     * @dev Get weighted portfolio value
     * @param amounts Array of subnet token amounts
     * @param netuids Array of subnet IDs
     * @return Total weighted value
     */
    function getWeightedValue(
        uint256[] calldata amounts,
        uint16[] calldata netuids
    ) external view returns (uint256);
}
