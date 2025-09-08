// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title TAO20V2
 * @dev Simplified, trustless ERC20 token for TAO20 Index
 * 
 * DESIGN PRINCIPLES:
 * ✅ No supply caps - supply floats based on actual deposits
 * ✅ No blacklisting - protocol remains neutral
 * ✅ No emergency controls - immutable and trustless
 * ✅ No owner privileges - fully decentralized
 * ✅ Only essential minting/burning functionality
 * 
 * SECURITY FEATURES:
 * ✅ ReentrancyGuard - Prevents reentrancy attacks
 * ✅ Single authorized minter - Only TAO20Core can mint/burn
 * ✅ Immutable design - No upgrade mechanisms
 * ✅ Standard ERC20 compliance
 */
contract TAO20V2 is ERC20, ReentrancyGuard {
    
    // ===================== STATE VARIABLES =====================
    
    /// @dev The authorized minter contract (TAO20Core)
    address public immutable authorizedMinter;
    
    // ===================== EVENTS =====================
    
    event TokensMinted(address indexed to, uint256 amount);
    event TokensBurned(address indexed from, uint256 amount);
    
    // ===================== ERRORS =====================
    
    error UnauthorizedMinter();
    error ZeroAddress();
    error ZeroAmount();
    error InsufficientBalance();
    
    // ===================== MODIFIERS =====================
    
    modifier onlyAuthorizedMinter() {
        if (msg.sender != authorizedMinter) revert UnauthorizedMinter();
        _;
    }
    
    modifier validAddress(address addr) {
        if (addr == address(0)) revert ZeroAddress();
        _;
    }
    
    modifier validAmount(uint256 amount) {
        if (amount == 0) revert ZeroAmount();
        _;
    }
    
    // ===================== CONSTRUCTOR =====================
    
    /**
     * @dev Initialize TAO20 token with name and symbol
     * @param name Token name (e.g., "TAO20 Index Token")
     * @param symbol Token symbol (e.g., "TAO20")
     */
    constructor(
        string memory name,
        string memory symbol
    ) ERC20(name, symbol) {
        authorizedMinter = msg.sender; // TAO20Core contract
    }
    
    // ===================== CORE TOKEN FUNCTIONS =====================
    
    /**
     * @dev Mint tokens to an address (only authorized minter)
     * @param to Recipient address
     * @param amount Amount to mint
     */
    function mint(address to, uint256 amount) 
        external 
        onlyAuthorizedMinter 
        nonReentrant 
        validAddress(to) 
        validAmount(amount)
    {
        _mint(to, amount);
        emit TokensMinted(to, amount);
    }
    
    /**
     * @dev Burn tokens from an address (only authorized minter)
     * @param from Address to burn from
     * @param amount Amount to burn
     */
    function burn(address from, uint256 amount) 
        external 
        onlyAuthorizedMinter 
        nonReentrant 
        validAddress(from) 
        validAmount(amount)
    {
        uint256 currentBalance = balanceOf(from);
        if (currentBalance < amount) revert InsufficientBalance();
        
        _burn(from, amount);
        emit TokensBurned(from, amount);
    }
    
    // ===================== ENHANCED ERC20 FUNCTIONS =====================
    
    /**
     * @dev Override transfer to add reentrancy protection
     */
    function transfer(address to, uint256 amount) 
        public 
        override 
        nonReentrant 
        validAddress(to) 
        returns (bool) 
    {
        return super.transfer(to, amount);
    }
    
    /**
     * @dev Override transferFrom to add reentrancy protection
     */
    function transferFrom(address from, address to, uint256 amount) 
        public 
        override 
        nonReentrant 
        validAddress(from) 
        validAddress(to) 
        returns (bool) 
    {
        return super.transferFrom(from, to, amount);
    }
    
    /**
     * @dev Override approve to add reentrancy protection
     */
    function approve(address spender, uint256 amount) 
        public 
        override 
        nonReentrant 
        validAddress(spender) 
        returns (bool) 
    {
        return super.approve(spender, amount);
    }
    
    // ===================== VIEW FUNCTIONS =====================
    
    /**
     * @dev Get token decimals (standard 18)
     */
    function decimals() public pure override returns (uint8) {
        return 18;
    }
    
    /**
     * @dev Check if address is the authorized minter
     */
    function isAuthorizedMinter(address addr) external view returns (bool) {
        return addr == authorizedMinter;
    }
    
    /**
     * @dev Get comprehensive token information
     */
    function getTokenInfo() external view returns (
        string memory tokenName,
        string memory tokenSymbol,
        uint8 tokenDecimals,
        uint256 tokenTotalSupply,
        address tokenMinter
    ) {
        return (
            name(),
            symbol(),
            decimals(),
            totalSupply(),
            authorizedMinter
        );
    }
    
    // ===================== UTILITY FUNCTIONS =====================
    
    /**
     * @dev Calculate percentage of total supply
     * @param amount Token amount
     * @return percentage Percentage in basis points (10000 = 100%)
     */
    function calculateSupplyPercentage(uint256 amount) external view returns (uint256 percentage) {
        uint256 supply = totalSupply();
        if (supply == 0) return 0;
        return (amount * 10000) / supply;
    }
    
    /**
     * @dev Get user's balance as percentage of total supply
     * @param user User address
     * @return percentage Percentage in basis points (10000 = 100%)
     */
    function getUserSupplyPercentage(address user) external view returns (uint256 percentage) {
        return this.calculateSupplyPercentage(balanceOf(user));
    }
}
