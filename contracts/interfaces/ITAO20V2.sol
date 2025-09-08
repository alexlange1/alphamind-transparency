// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title ITAO20V2
 * @dev Interface for the TAO20V2 token
 */
interface ITAO20V2 is IERC20 {
    
    // ===================== EVENTS =====================
    
    event TokensMinted(address indexed to, uint256 amount);
    event TokensBurned(address indexed from, uint256 amount);
    
    // ===================== ERRORS =====================
    
    error UnauthorizedMinter();
    error ZeroAddress();
    error ZeroAmount();
    error InsufficientBalance();
    
    // ===================== FUNCTIONS =====================
    
    /**
     * @dev Mint tokens to an address (only authorized minter)
     */
    function mint(address to, uint256 amount) external;
    
    /**
     * @dev Burn tokens from an address (only authorized minter)
     */
    function burn(address from, uint256 amount) external;
    
    /**
     * @dev Get the authorized minter address
     */
    function authorizedMinter() external view returns (address);
    
    /**
     * @dev Check if address is the authorized minter
     */
    function isAuthorizedMinter(address addr) external view returns (bool);
    
    /**
     * @dev Get comprehensive token information
     */
    function getTokenInfo() external view returns (
        string memory tokenName,
        string memory tokenSymbol,
        uint8 tokenDecimals,
        uint256 tokenTotalSupply,
        address tokenMinter
    );
    
    /**
     * @dev Calculate percentage of total supply
     */
    function calculateSupplyPercentage(uint256 amount) external view returns (uint256 percentage);
    
    /**
     * @dev Get user's balance as percentage of total supply
     */
    function getUserSupplyPercentage(address user) external view returns (uint256 percentage);
}
