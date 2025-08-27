/**
 * Concrete TAO20 Mint Interface
 * Handles the exact minting flow: SS58 deposit → structured message signing → EVM claim submission
 */

class ConcreteTao20MintInterface {
    constructor(apiUrl = 'http://localhost:8000') {
        this.apiUrl = apiUrl;
        this.ss58Wallet = null;
        this.evmWallet = null;
        this.statusCallbacks = [];
    }

    // Wallet Connection
    async connectSS58Wallet() {
        try {
            this.updateStatus('Connecting SS58 wallet...');
            
            // Check if Polkadot.js extension is available
            if (!window.injectedWeb3) {
                throw new Error('Polkadot.js extension not found. Please install it first.');
            }

            // Connect to Substrate wallet
            const { web3Enable, web3Accounts } = await import('@polkadot/extension-dapp');
            await web3Enable('TAO20 Mint Interface');
            
            const accounts = await web3Accounts();
            if (accounts.length === 0) {
                throw new Error('No accounts found in Polkadot.js extension');
            }

            this.ss58Wallet = accounts[0];
            this.updateStatus(`SS58 wallet connected: ${this.ss58Wallet.address}`);
            
            return this.ss58Wallet;
        } catch (error) {
            this.updateStatus(`SS58 wallet connection failed: ${error.message}`);
            throw error;
        }
    }

    async connectEVMWallet() {
        try {
            this.updateStatus('Connecting EVM wallet...');
            
            // Check if MetaMask is available
            if (!window.ethereum) {
                throw new Error('MetaMask not found. Please install it first.');
            }

            // Request account access
            const accounts = await window.ethereum.request({ 
                method: 'eth_requestAccounts' 
            });
            
            if (accounts.length === 0) {
                throw new Error('No accounts found in MetaMask');
            }

            this.evmWallet = accounts[0];
            this.updateStatus(`EVM wallet connected: ${this.evmWallet}`);
            
            return this.evmWallet;
        } catch (error) {
            this.updateStatus(`EVM wallet connection failed: ${error.message}`);
            throw error;
        }
    }

    // Mint Flow
    async prepareMintClaim(blockHash, extrinsicIndex) {
        try {
            this.updateStatus('Preparing mint claim...');
            
            if (!this.ss58Wallet || !this.evmWallet) {
                throw new Error('Both SS58 and EVM wallets must be connected');
            }

            // Call API to prepare mint claim
            const response = await fetch(`${this.apiUrl}/mint/prepare`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    block_hash: blockHash,
                    extrinsic_index: extrinsicIndex
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to prepare mint claim');
            }

            const mintData = await response.json();
            this.updateStatus('Mint claim prepared successfully');
            
            return mintData;
        } catch (error) {
            this.updateStatus(`Mint claim preparation failed: ${error.message}`);
            throw error;
        }
    }

    async signMintClaim(mintData) {
        try {
            this.updateStatus('Signing mint claim with SS58 wallet...');
            
            if (!this.ss58Wallet) {
                throw new Error('SS58 wallet not connected');
            }

            // Create the JSON payload to sign
            const jsonPayload = JSON.stringify({
                type: mintData.type,
                ss58: mintData.ss58,
                evm: mintData.evm,
                deposit: mintData.deposit,
                chain_id: mintData.chain_id,
                domain: mintData.domain,
                nonce: mintData.nonce,
                expires: mintData.expires
            }, null, 2);

            this.updateStatus('Please sign the following message in your Polkadot.js extension:');
            console.log('JSON to sign:', jsonPayload);

            // Sign with SS58 wallet
            const { web3FromSource } = await import('@polkadot/extension-dapp');
            const injector = await web3FromSource(this.ss58Wallet.meta.source);
            
            // Sign the JSON payload
            const signResult = await injector.signer.signRaw({
                address: this.ss58Wallet.address,
                data: jsonPayload,
                type: 'bytes'
            });

            this.updateStatus('Mint claim signed successfully');
            
            return {
                signature: signResult.signature,
                messageHash: mintData.message_hash,
                jsonPayload: jsonPayload
            };
        } catch (error) {
            this.updateStatus(`Mint claim signing failed: ${error.message}`);
            throw error;
        }
    }

    async submitMintClaim(mintData, signature) {
        try {
            this.updateStatus('Submitting mint claim to EVM...');
            
            if (!this.evmWallet) {
                throw new Error('EVM wallet not connected');
            }

            // Prepare contract call data
            const contractData = this.prepareContractCall(mintData, signature);
            
            // Submit transaction via MetaMask
            const transactionParameters = {
                to: this.getContractAddress(), // TAO20 Minter contract address
                from: this.evmWallet,
                data: contractData,
                gas: '500000', // Estimate gas
                gasPrice: await this.getGasPrice()
            };

            const txHash = await window.ethereum.request({
                method: 'eth_sendTransaction',
                params: [transactionParameters]
            });

            this.updateStatus(`Mint claim submitted! Transaction: ${txHash}`);
            
            return txHash;
        } catch (error) {
            this.updateStatus(`Mint claim submission failed: ${error.message}`);
            throw error;
        }
    }

    prepareContractCall(mintData, signature) {
        // Prepare the contract call data for claimMint function
        // This would use web3.js or ethers.js to encode the function call
        
        const { ethers } = require('ethers');
        
        // Contract ABI for claimMint function
        const abi = [
            "function claimMint(tuple(bytes32,uint32,bytes32,uint256,uint16) dep, tuple(address,bytes32,uint64) c, bytes32 r, bytes32 s, bytes32 messageHash)"
        ];
        
        const iface = new ethers.utils.Interface(abi);
        
        // Prepare function parameters
        const dep = [
            mintData.deposit.block_hash,
            mintData.deposit.extrinsic_index,
            this.ss58ToBytes32(mintData.ss58),
            mintData.deposit.amount,
            parseInt(mintData.deposit.asset.split(':')[1])
        ];
        
        const c = [
            mintData.evm,
            mintData.nonce,
            Math.floor(new Date(mintData.expires).getTime() / 1000)
        ];
        
        // Split signature into r and s
        const sig = ethers.utils.splitSignature(signature);
        
        // Encode function call
        return iface.encodeFunctionData('claimMint', [dep, c, sig.r, sig.s, mintData.message_hash]);
    }

    ss58ToBytes32(ss58Address) {
        // Convert SS58 address to bytes32
        // This is a simplified conversion - in production you'd use proper SS58 decoding
        const hash = ethers.utils.keccak256(ethers.utils.toUtf8Bytes(ss58Address));
        return hash;
    }

    async getGasPrice() {
        // Get current gas price
        const gasPrice = await window.ethereum.request({
            method: 'eth_gasPrice'
        });
        return gasPrice;
    }

    getContractAddress() {
        // Return the TAO20 Minter contract address
        return '0x1234567890123456789012345678901234567890'; // Set actual address
    }

    // Queue Status
    async getQueueStatus(address) {
        try {
            const response = await fetch(`${this.apiUrl}/queue/status?address=${address}`);
            
            if (!response.ok) {
                throw new Error('Failed to get queue status');
            }

            return await response.json();
        } catch (error) {
            this.updateStatus(`Queue status check failed: ${error.message}`);
            throw error;
        }
    }

    // Complete Flow
    async completeMintingFlow(blockHash, extrinsicIndex) {
        try {
            this.updateStatus('Starting complete minting flow...');
            
            // Step 1: Prepare mint claim
            const mintData = await this.prepareMintClaim(blockHash, extrinsicIndex);
            
            // Step 2: Sign mint claim
            const signature = await this.signMintClaim(mintData);
            
            // Step 3: Submit mint claim
            const txHash = await this.submitMintClaim(mintData, signature.signature);
            
            // Step 4: Get queue status
            const queueStatus = await this.getQueueStatus(this.evmWallet);
            
            this.updateStatus('Minting flow completed successfully!');
            
            return {
                mintData,
                signature,
                txHash,
                queueStatus
            };
        } catch (error) {
            this.updateStatus(`Minting flow failed: ${error.message}`);
            throw error;
        }
    }

    // Utility Methods
    updateStatus(message) {
        console.log(`[TAO20 Mint] ${message}`);
        this.statusCallbacks.forEach(callback => callback(message));
    }

    onStatusUpdate(callback) {
        this.statusCallbacks.push(callback);
    }

    // Auto-discovery of deposits (optional)
    async discoverDeposits(ss58Address) {
        try {
            this.updateStatus('Discovering deposits...');
            
            // In production, this would query the API for deposits by SS58 address
            const response = await fetch(`${this.apiUrl}/deposits/discover?ss58=${ss58Address}`);
            
            if (!response.ok) {
                throw new Error('Failed to discover deposits');
            }

            const deposits = await response.json();
            this.updateStatus(`Found ${deposits.length} deposits`);
            
            return deposits;
        } catch (error) {
            this.updateStatus(`Deposit discovery failed: ${error.message}`);
            throw error;
        }
    }

    // Health check
    async checkHealth() {
        try {
            const response = await fetch(`${this.apiUrl}/health`);
            
            if (!response.ok) {
                throw new Error('API health check failed');
            }

            const health = await response.json();
            this.updateStatus(`API Status: ${health.status}`);
            
            return health;
        } catch (error) {
            this.updateStatus(`Health check failed: ${error.message}`);
            throw error;
        }
    }
}

// Export for use in browser
if (typeof window !== 'undefined') {
    window.ConcreteTao20MintInterface = ConcreteTao20MintInterface;
}

// Export for Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ConcreteTao20MintInterface;
}
