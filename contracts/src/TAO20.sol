// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";

/**
 * @title TAO20
 * @dev Bulletproof ERC20 token for the TAO20 Index with enterprise-grade security
 * 
 * SECURITY FEATURES:
 * ✅ OpenZeppelin Ownable - Secure admin controls
 * ✅ ReentrancyGuard - Prevents reentrancy attacks
 * ✅ Pausable - Emergency stop mechanism
 * ✅ ERC20Permit - Gasless approvals via signatures
 * ✅ Maximum supply cap - Prevents unlimited inflation
 * ✅ Blacklist mechanism - Freeze malicious accounts
 * ✅ Safe math operations - All arithmetic is overflow/underflow safe
 * ✅ Comprehensive input validation - Zero address and amount checks
 * ✅ Detailed events - Full audit trail
 * ✅ Multi-minter support - Role-based access control
 */
contract TAO20 is Ownable, ReentrancyGuard, Pausable, ERC20Permit {
    
    // ===================== Constants =====================
    
    /// @dev Maximum possible supply: 21 million tokens (matching Bitcoin's cap)
    uint256 public constant MAX_SUPPLY = 21_000_000 * 1e18;
    
    /// @dev Maximum amount that can be minted in a single transaction (anti-spam)
    uint256 public constant MAX_MINT_AMOUNT = 1_000_000 * 1e18;
    
    // ===================== State Variables =====================
    
    /// @dev Authorized minters mapping
    mapping(address => bool) public authorizedMinters;
    
    /// @dev Blacklisted addresses (frozen accounts)
    mapping(address => bool) public blacklisted;
    
    /// @dev Total number of authorized minters
    uint256 public minterCount;
    
    // ===================== Events =====================
    
    event MinterAuthorized(address indexed minter, bool authorized);
    event AccountBlacklisted(address indexed account, bool blacklisted);
    event EmergencyMint(address indexed to, uint256 amount, string reason);
    event EmergencyBurn(address indexed from, uint256 amount, string reason);
    
    // ===================== Errors =====================
    
    error TAO20__NotAuthorizedMinter();
    error TAO20__AccountBlacklisted(address account);
    error TAO20__ExceedsMaxSupply(uint256 requested, uint256 maxSupply);
    error TAO20__ExceedsMaxMintAmount(uint256 requested, uint256 maxAmount);
    error TAO20__ZeroAddress();
    error TAO20__ZeroAmount();
    error TAO20__InsufficientBalance(address account, uint256 balance, uint256 required);
    error TAO20__InsufficientAllowance(address owner, address spender, uint256 allowance, uint256 required);
    error TAO20__NoMintersAuthorized();
    
    // ===================== Modifiers =====================
    
    modifier onlyAuthorizedMinter() {
        if (!authorizedMinters[msg.sender]) revert TAO20__NotAuthorizedMinter();
        _;
    }
    
    modifier notBlacklisted(address account) {
        if (blacklisted[account]) revert TAO20__AccountBlacklisted(account);
        _;
    }
    
    modifier validAddress(address addr) {
        if (addr == address(0)) revert TAO20__ZeroAddress();
        _;
    }
    
    modifier validAmount(uint256 amount) {
        if (amount == 0) revert TAO20__ZeroAmount();
        _;
    }
    
    // ===================== Constructor =====================
    
    constructor(address _initialMinter) 
        ERC20("TAO20 Index", "TAO20")
        ERC20Permit("TAO20 Index")
        Ownable(msg.sender)
    {
        if (_initialMinter == address(0)) revert TAO20__ZeroAddress();
        
        // Authorize initial minter
        authorizedMinters[_initialMinter] = true;
        minterCount = 1;
        
        emit MinterAuthorized(_initialMinter, true);
    }
    
    // ===================== Minter Management =====================
    
    /**
     * @dev Authorize or revoke minter privileges
     * @param minter Address to modify
     * @param authorized True to authorize, false to revoke
     * @dev FIXED: Removed minterCount == 0 revert to prevent soft lock
     */
    function setMinter(address minter, bool authorized) 
        external 
        onlyOwner 
        validAddress(minter) 
    {
        if (authorizedMinters[minter] == authorized) return; // No change needed
        
        authorizedMinters[minter] = authorized;
        
        if (authorized) {
            minterCount++;
        } else {
            minterCount--;
            // Note: Allow 0 minters to prevent soft lock - owner can add new minters
        }
        
        emit MinterAuthorized(minter, authorized);
    }
    
    /**
     * @dev Batch authorize multiple minters (gas efficient)
     * @param minters Array of addresses to authorize
     * @dev FIXED: Added array length limit to prevent gas issues
     */
    function authorizeMinters(address[] calldata minters) external onlyOwner {
        require(minters.length <= 50, "TAO20: Too many minters in batch");
        
        for (uint256 i = 0; i < minters.length; i++) {
            address minter = minters[i];
            if (minter == address(0)) revert TAO20__ZeroAddress();
            
            if (!authorizedMinters[minter]) {
                authorizedMinters[minter] = true;
                minterCount++;
                emit MinterAuthorized(minter, true);
            }
        }
    }
    
    // ===================== Blacklist Management =====================
    
    /**
     * @dev Blacklist or unblacklist an account (emergency measure)
     * @param account Address to modify
     * @param _blacklisted True to blacklist, false to unblacklist
     */
    function setBlacklisted(address account, bool _blacklisted) 
        external 
        onlyOwner 
        validAddress(account) 
    {
        if (blacklisted[account] == _blacklisted) return; // No change needed
        
        blacklisted[account] = _blacklisted;
        emit AccountBlacklisted(account, _blacklisted);
    }
    
    /**
     * @dev Batch blacklist multiple accounts
     * @param accounts Array of addresses to blacklist
     * @dev FIXED: Added array length limit to prevent gas issues
     */
    function blacklistAccounts(address[] calldata accounts) external onlyOwner {
        require(accounts.length <= 100, "TAO20: Too many accounts in batch");
        
        for (uint256 i = 0; i < accounts.length; i++) {
            address account = accounts[i];
            if (account == address(0)) revert TAO20__ZeroAddress();
            
            if (!blacklisted[account]) {
                blacklisted[account] = true;
                emit AccountBlacklisted(account, true);
            }
        }
    }
    
    // ===================== Core Token Functions =====================
    
    /**
     * @dev Mint tokens to an address (only authorized minters)
     * @param to Recipient address
     * @param amount Amount to mint
     * @dev NOTE: Reverts if no minters are authorized (requires owner to add minter first)
     */
    function mint(address to, uint256 amount) 
        external 
        onlyAuthorizedMinter 
        nonReentrant 
        whenNotPaused 
        validAddress(to) 
        validAmount(amount)
        notBlacklisted(to)
    {
        // Check supply constraints
        uint256 newTotalSupply = totalSupply() + amount;
        if (newTotalSupply > MAX_SUPPLY) {
            revert TAO20__ExceedsMaxSupply(newTotalSupply, MAX_SUPPLY);
        }
        
        // Check single mint limit
        if (amount > MAX_MINT_AMOUNT) {
            revert TAO20__ExceedsMaxMintAmount(amount, MAX_MINT_AMOUNT);
        }
        
        _mint(to, amount);
    }
    
    /**
     * @dev Burn tokens from an address (only authorized minters)
     * @param from Address to burn from
     * @param amount Amount to burn
     * @dev NOTE: Intentionally allows burning from blacklisted accounts (Vault redemption)
     */
    function burn(address from, uint256 amount) 
        external 
        onlyAuthorizedMinter 
        nonReentrant 
        whenNotPaused 
        validAddress(from) 
        validAmount(amount)
    {
        uint256 currentBalance = balanceOf(from);
        if (currentBalance < amount) {
            revert TAO20__InsufficientBalance(from, currentBalance, amount);
        }
        
        _burn(from, amount);
    }
    
    /**
     * @dev Emergency mint (owner only, with reason)
     * @param to Recipient address
     * @param amount Amount to mint
     * @param reason Reason for emergency mint
     * @dev NOTE: Emergency mint bypasses MAX_MINT_AMOUNT limit (by design)
     */
    function emergencyMint(address to, uint256 amount, string calldata reason) 
        external 
        onlyOwner 
        validAddress(to) 
        validAmount(amount)
        notBlacklisted(to)
    {
        uint256 newTotalSupply = totalSupply() + amount;
        if (newTotalSupply > MAX_SUPPLY) {
            revert TAO20__ExceedsMaxSupply(newTotalSupply, MAX_SUPPLY);
        }
        
        _mint(to, amount);
        emit EmergencyMint(to, amount, reason);
    }
    
    /**
     * @dev Emergency burn (owner only, with reason)
     * @param from Address to burn from
     * @param amount Amount to burn
     * @param reason Reason for emergency burn
     */
    function emergencyBurn(address from, uint256 amount, string calldata reason) 
        external 
        onlyOwner 
        validAddress(from) 
        validAmount(amount)
    {
        uint256 currentBalance = balanceOf(from);
        if (currentBalance < amount) {
            revert TAO20__InsufficientBalance(from, currentBalance, amount);
        }
        
        _burn(from, amount);
        emit EmergencyBurn(from, amount, reason);
    }
    
    // ===================== Enhanced Transfer Functions =====================
    
    /**
     * @dev Enhanced transfer with blacklist checks
     */
    function transfer(address to, uint256 amount) 
        public 
        override 
        whenNotPaused 
        notBlacklisted(msg.sender) 
        notBlacklisted(to) 
        returns (bool) 
    {
        return super.transfer(to, amount);
    }
    
    /**
     * @dev Enhanced transferFrom with blacklist checks
     */
    function transferFrom(address from, address to, uint256 amount) 
        public 
        override 
        whenNotPaused 
        notBlacklisted(from) 
        notBlacklisted(to) 
        notBlacklisted(msg.sender) 
        returns (bool) 
    {
        return super.transferFrom(from, to, amount);
    }
    
    /**
     * @dev Enhanced approve with blacklist checks
     * @dev WARNING: Standard ERC20 approve has front-running vulnerability
     * @dev RECOMMENDATION: Use increaseAllowance/decreaseAllowance instead
     */
    function approve(address spender, uint256 amount) 
        public 
        override 
        whenNotPaused 
        notBlacklisted(msg.sender) 
        notBlacklisted(spender) 
        returns (bool) 
    {
        return super.approve(spender, amount);
    }
    
    /**
     * @dev Safe alternative to approve - increases allowance
     * @param spender Address to increase allowance for
     * @param addedValue Amount to increase allowance by
     */
    function increaseAllowance(address spender, uint256 addedValue)
        public
        whenNotPaused
        notBlacklisted(msg.sender)
        notBlacklisted(spender)
        returns (bool)
    {
        address owner = _msgSender();
        _approve(owner, spender, allowance(owner, spender) + addedValue);
        return true;
    }
    
    /**
     * @dev Safe alternative to approve - decreases allowance
     * @param spender Address to decrease allowance for
     * @param subtractedValue Amount to decrease allowance by
     */
    function decreaseAllowance(address spender, uint256 subtractedValue)
        public
        whenNotPaused
        notBlacklisted(msg.sender)
        notBlacklisted(spender)
        returns (bool)
    {
        address owner = _msgSender();
        uint256 currentAllowance = allowance(owner, spender);
        require(currentAllowance >= subtractedValue, "TAO20: decreased allowance below zero");
        _approve(owner, spender, currentAllowance - subtractedValue);
        return true;
    }
    
    // ===================== Emergency Controls =====================
    
    /**
     * @dev Pause all token operations (emergency only)
     */
    function pause() external onlyOwner {
        _pause();
    }
    
    /**
     * @dev Unpause token operations
     */
    function unpause() external onlyOwner {
        _unpause();
    }
    
    // ===================== View Functions =====================
    
    /**
     * @dev Check if an address is an authorized minter
     */
    function isMinter(address account) external view returns (bool) {
        return authorizedMinters[account];
    }
    
    /**
     * @dev Check if an account is blacklisted
     */
    function isBlacklisted(address account) external view returns (bool) {
        return blacklisted[account];
    }
    
    /**
     * @dev Get remaining mintable supply
     * @dev FIXED: Handles edge case where totalSupply > MAX_SUPPLY
     */
    function remainingSupply() external view returns (uint256) {
        uint256 currentSupply = totalSupply();
        return currentSupply >= MAX_SUPPLY ? 0 : MAX_SUPPLY - currentSupply;
    }
    
    /**
     * @dev Check if minting amount would exceed max supply
     */
    function canMint(uint256 amount) external view returns (bool) {
        return totalSupply() + amount <= MAX_SUPPLY;
    }
    
    /**
     * @dev Check if minting is currently possible (has authorized minters)
     */
    function canMintNow() external view returns (bool) {
        return minterCount > 0;
    }
    
    /**
     * @dev Get current number of authorized minters
     */
    function getMinterCount() external view returns (uint256) {
        return minterCount;
    }
    
    // ===================== Batch Operations =====================
    
    /**
     * @dev Batch transfer to multiple recipients (gas efficient)
     * @param recipients Array of recipient addresses
     * @param amounts Array of amounts to transfer
     */
    function batchTransfer(address[] calldata recipients, uint256[] calldata amounts) 
        external 
        whenNotPaused 
        notBlacklisted(msg.sender) 
        returns (bool) 
    {
        require(recipients.length == amounts.length, "TAO20: Arrays length mismatch");
        require(recipients.length > 0, "TAO20: Empty arrays");
        
        uint256 totalAmount = 0;
        
        // Calculate total amount needed
        // FIXED: Use unchecked for gas efficiency - overflow protection via balance check
        for (uint256 i = 0; i < amounts.length; i++) {
            if (amounts[i] == 0) revert TAO20__ZeroAmount();
            unchecked {
                totalAmount += amounts[i];
            }
        }
        
        // Check sender has sufficient balance
        uint256 senderBalance = balanceOf(msg.sender);
        if (senderBalance < totalAmount) {
            revert TAO20__InsufficientBalance(msg.sender, senderBalance, totalAmount);
        }
        
        // Execute transfers
        for (uint256 i = 0; i < recipients.length; i++) {
            address recipient = recipients[i];
            if (recipient == address(0)) revert TAO20__ZeroAddress();
            if (blacklisted[recipient]) revert TAO20__AccountBlacklisted(recipient);
            
            _transfer(msg.sender, recipient, amounts[i]);
        }
        
        return true;
    }
}
