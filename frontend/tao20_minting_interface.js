/**
 * TAO20 Minting Interface for Frontend
 * Provides wallet connection and minting functionality for alphamind.xyz
 */

class TAO20MintingInterface {
    constructor(apiBaseUrl = 'http://localhost:8000') {
        this.apiBaseUrl = apiBaseUrl;
        this.wallet = null;
        this.userAddress = null;
        this.isConnected = false;
        
        // Event listeners for status updates
        this.statusCallbacks = [];
        
        // Initialize
        this.init();
    }
    
    init() {
        console.log('TAO20 Minting Interface initialized');
        this.updateStatus('Ready to connect wallet');
    }
    
    /**
     * Connect to user's wallet (Polkadot.js, Talisman, etc.)
     */
    async connectWallet() {
        try {
            this.updateStatus('Connecting to wallet...');
            
            // Check if Polkadot.js extension is available
            if (typeof window.injectedWeb3 === 'undefined') {
                throw new Error('Polkadot.js extension not found. Please install it first.');
            }
            
            // Request connection to wallet
            const extension = await window.injectedWeb3['polkadot-js'];
            if (!extension) {
                throw new Error('Polkadot.js extension not available');
            }
            
            // Connect to the extension
            const accounts = await extension.accounts.get();
            if (accounts.length === 0) {
                throw new Error('No accounts found in wallet. Please add an account first.');
            }
            
            // Use the first account for now (could add account selection UI)
            this.wallet = extension;
            this.userAddress = accounts[0].address;
            this.isConnected = true;
            
            this.updateStatus(`Connected to wallet: ${this.userAddress.substring(0, 10)}...`);
            
            return {
                success: true,
                address: this.userAddress,
                accounts: accounts
            };
            
        } catch (error) {
            console.error('Error connecting to wallet:', error);
            this.updateStatus(`Wallet connection failed: ${error.message}`);
            throw error;
        }
    }
    
    /**
     * Track a new deposit
     */
    async trackDeposit(netuid, amount) {
        if (!this.isConnected) {
            throw new Error('Wallet not connected');
        }
        
        try {
            this.updateStatus('Tracking deposit...');
            
            const response = await fetch(`${this.apiBaseUrl}/deposits/track`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_address: this.userAddress,
                    netuid: netuid,
                    amount: amount
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to track deposit');
            }
            
            const result = await response.json();
            this.updateStatus(`Deposit tracked: ${result.deposit_id}`);
            
            return result;
            
        } catch (error) {
            console.error('Error tracking deposit:', error);
            this.updateStatus(`Deposit tracking failed: ${error.message}`);
            throw error;
        }
    }
    
    /**
     * Sign deposit confirmation message
     */
    async signDepositConfirmation(depositInfo) {
        if (!this.isConnected) {
            throw new Error('Wallet not connected');
        }
        
        try {
            this.updateStatus('Signing deposit confirmation...');
            
            // Create the message to sign
            const message = this.createDepositMessage(depositInfo);
            
            // Sign the message using the wallet
            const signature = await this.wallet.signer.signRaw({
                type: 'bytes',
                data: this.stringToHex(message),
                address: this.userAddress
            });
            
            this.updateStatus('Deposit confirmation signed');
            
            return {
                message: message,
                signature: signature.signature
            };
            
        } catch (error) {
            console.error('Error signing deposit confirmation:', error);
            this.updateStatus(`Signature failed: ${error.message}`);
            throw error;
        }
    }
    
    /**
     * Create the message that should be signed by the user
     */
    createDepositMessage(depositInfo) {
        return (
            `I confirm I deposited ${depositInfo.amount} alpha tokens ` +
            `from subnet ${depositInfo.netuid} to the TAO20 vault ` +
            `at timestamp ${depositInfo.timestamp}. ` +
            `Deposit ID: ${depositInfo.deposit_id}`
        );
    }
    
    /**
     * Mint TAO20 tokens for a deposit
     */
    async mintTAO20(depositInfo) {
        if (!this.isConnected) {
            throw new Error('Wallet not connected');
        }
        
        try {
            this.updateStatus('Processing mint request...');
            
            // Sign the deposit confirmation
            const { message, signature } = await this.signDepositConfirmation(depositInfo);
            
            // Send mint request to API
            const response = await fetch(`${this.apiBaseUrl}/mint`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_address: this.userAddress,
                    deposit_info: depositInfo,
                    signature: signature,
                    message: message
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to mint TAO20');
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.updateStatus(`TAO20 minted successfully! Amount: ${result.tao20_amount}`);
            } else {
                throw new Error(result.error || 'Minting failed');
            }
            
            return result;
            
        } catch (error) {
            console.error('Error minting TAO20:', error);
            this.updateStatus(`Minting failed: ${error.message}`);
            throw error;
        }
    }
    
    /**
     * Get deposit status
     */
    async getDepositStatus(depositId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/deposits/${depositId}`);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to get deposit status');
            }
            
            return await response.json();
            
        } catch (error) {
            console.error('Error getting deposit status:', error);
            throw error;
        }
    }
    
    /**
     * Get all deposits for current user
     */
    async getUserDeposits() {
        if (!this.isConnected) {
            throw new Error('Wallet not connected');
        }
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/deposits/user/${this.userAddress}`);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to get user deposits');
            }
            
            return await response.json();
            
        } catch (error) {
            console.error('Error getting user deposits:', error);
            throw error;
        }
    }
    
    /**
     * Get vault summary
     */
    async getVaultSummary() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/vault/summary`);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to get vault summary');
            }
            
            return await response.json();
            
        } catch (error) {
            console.error('Error getting vault summary:', error);
            throw error;
        }
    }
    
    /**
     * Get current NAV
     */
    async getCurrentNAV() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/nav/current`);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to get current NAV');
            }
            
            return await response.json();
            
        } catch (error) {
            console.error('Error getting current NAV:', error);
            throw error;
        }
    }
    
    /**
     * Complete minting flow: track deposit -> sign -> mint
     */
    async completeMintingFlow(netuid, amount) {
        try {
            this.updateStatus('Starting minting flow...');
            
            // Step 1: Track the deposit
            const depositResult = await this.trackDeposit(netuid, amount);
            const depositId = depositResult.deposit_id;
            
            // Step 2: Wait a moment for deposit to be confirmed
            this.updateStatus('Waiting for deposit confirmation...');
            await this.sleep(2000);
            
            // Step 3: Get deposit info
            const depositInfo = await this.getDepositStatus(depositId);
            
            if (depositInfo.status !== 'confirmed') {
                throw new Error(`Deposit not confirmed. Status: ${depositInfo.status}`);
            }
            
            // Step 4: Mint TAO20
            const mintResult = await this.mintTAO20(depositInfo);
            
            this.updateStatus('Minting flow completed successfully!');
            
            return {
                deposit_id: depositId,
                mint_result: mintResult
            };
            
        } catch (error) {
            console.error('Error in minting flow:', error);
            this.updateStatus(`Minting flow failed: ${error.message}`);
            throw error;
        }
    }
    
    /**
     * Poll deposit status until confirmed
     */
    async waitForDepositConfirmation(depositId, maxAttempts = 30, intervalMs = 2000) {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            try {
                const status = await this.getDepositStatus(depositId);
                
                if (status.status === 'confirmed') {
                    this.updateStatus('Deposit confirmed!');
                    return status;
                } else if (status.status === 'failed') {
                    throw new Error(`Deposit failed: ${status.error_message}`);
                }
                
                this.updateStatus(`Waiting for deposit confirmation... (${attempt + 1}/${maxAttempts})`);
                await this.sleep(intervalMs);
                
            } catch (error) {
                console.error(`Error checking deposit status (attempt ${attempt + 1}):`, error);
                await this.sleep(intervalMs);
            }
        }
        
        throw new Error('Deposit confirmation timeout');
    }
    
    /**
     * Utility function to sleep
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    /**
     * Convert string to hex
     */
    stringToHex(str) {
        return '0x' + Array.from(str).map(c => c.charCodeAt(0).toString(16).padStart(2, '0')).join('');
    }
    
    /**
     * Update status and notify callbacks
     */
    updateStatus(message) {
        console.log(`[TAO20] ${message}`);
        
        // Notify status callbacks
        this.statusCallbacks.forEach(callback => {
            try {
                callback(message);
            } catch (error) {
                console.error('Error in status callback:', error);
            }
        });
    }
    
    /**
     * Add status update callback
     */
    onStatusUpdate(callback) {
        this.statusCallbacks.push(callback);
    }
    
    /**
     * Remove status update callback
     */
    removeStatusCallback(callback) {
        const index = this.statusCallbacks.indexOf(callback);
        if (index > -1) {
            this.statusCallbacks.splice(index, 1);
        }
    }
    
    /**
     * Disconnect wallet
     */
    disconnect() {
        this.wallet = null;
        this.userAddress = null;
        this.isConnected = false;
        this.updateStatus('Wallet disconnected');
    }
    
    /**
     * Check if wallet is connected
     */
    isWalletConnected() {
        return this.isConnected && this.wallet !== null;
    }
    
    /**
     * Get current user address
     */
    getUserAddress() {
        return this.userAddress;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TAO20MintingInterface;
}

// Make available globally for browser use
if (typeof window !== 'undefined') {
    window.TAO20MintingInterface = TAO20MintingInterface;
}
