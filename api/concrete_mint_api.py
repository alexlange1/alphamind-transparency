#!/usr/bin/env python3
"""
Concrete Mint API - FastAPI implementation for TAO20 minting
Handles mint preparation and queue status as specified in the concrete example
"""

import asyncio
import logging
import time
import uuid
import json
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

import bittensor as bt
from web3 import Web3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
class MintPrepareRequest(BaseModel):
    block_hash: str
    extrinsic_index: int

class MintPrepareResponse(BaseModel):
    type: str = "ALPHAMIND_MINT_CLAIM_V1"
    ss58: str
    evm: str
    deposit: Dict
    chain_id: str = "subtensor-mainnet"
    domain: str = "alphamind.xyz"
    nonce: str
    expires: str
    message_hash: str

class QueueStatusResponse(BaseModel):
    address: str
    queue_position: Optional[int]
    estimated_execution: Optional[str]
    last_batch_execution: Optional[str]
    queue_length: int
    batch_window_minutes: int
    slippage_cap_percent: float

class DepositRecord(BaseModel):
    deposit_id: str
    block_hash: str
    extrinsic_index: int
    ss58_pubkey: str
    netuid: int
    amount: str
    finalized_at: str
    status: str  # 'pending', 'queued', 'executed', 'refunded'
    error: Optional[str] = None

class ClaimRecord(BaseModel):
    deposit_id: str
    claimer_evm: str
    nonce: str
    expires_at: str
    message_hash: str
    created_at: str

# Database simulation (in production, use PostgreSQL)
class InMemoryDB:
    def __init__(self):
        self.deposits: Dict[str, DepositRecord] = {}
        self.claims: Dict[str, ClaimRecord] = {}
        self.nonces: set = set()
    
    def add_deposit(self, deposit: DepositRecord):
        self.deposits[deposit.deposit_id] = deposit
    
    def get_deposit(self, deposit_id: str) -> Optional[DepositRecord]:
        return self.deposits.get(deposit_id)
    
    def update_deposit_status(self, deposit_id: str, status: str, error: Optional[str] = None):
        if deposit_id in self.deposits:
            self.deposits[deposit_id].status = status
            if error:
                self.deposits[deposit_id].error = error
    
    def add_claim(self, claim: ClaimRecord):
        self.claims[claim.deposit_id] = claim
        self.nonces.add(claim.nonce)
    
    def is_nonce_used(self, nonce: str) -> bool:
        return nonce in self.nonces
    
    def get_claims_by_address(self, address: str) -> List[ClaimRecord]:
        return [claim for claim in self.claims.values() if claim.claimer_evm.lower() == address.lower()]

# Initialize FastAPI app
app = FastAPI(
    title="TAO20 Concrete Mint API",
    description="Concrete implementation of TAO20 minting API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
db = InMemoryDB()
vault_ss58 = "your_vault_ss58_here"  # Set in environment
contract_address = "0x1234567890123456789012345678901234567890"  # Set in environment

class ConcreteMintAPI:
    """Concrete implementation of the mint API"""
    
    def __init__(self):
        self.vault_ss58 = vault_ss58
        self.contract_address = contract_address
        
        # Initialize Bittensor connection
        self.subtensor = bt.subtensor(network="finney")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:9944"))
        
        # Load contract ABI (simplified for this example)
        self.contract_abi = self._load_contract_abi()
        self.contract = self.w3.eth.contract(
            address=contract_address,
            abi=self.contract_abi
        )
    
    def _load_contract_abi(self) -> List[Dict]:
        """Load the Tao20Minter contract ABI"""
        return [
            {
                "inputs": [
                    {"name": "dep", "type": "tuple"},
                    {"name": "c", "type": "tuple"},
                    {"name": "r", "type": "bytes32"},
                    {"name": "s", "type": "bytes32"},
                    {"name": "messageHash", "type": "bytes32"}
                ],
                "name": "claimMint",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"name": "maxItems", "type": "uint256"}],
                "name": "executeBatch",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "getQueueLength",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "index", "type": "uint256"}],
                "name": "getQueueItem",
                "outputs": [
                    {"name": "depositId", "type": "bytes32"},
                    {"name": "claimer", "type": "address"},
                    {"name": "alphaAmount", "type": "uint256"},
                    {"name": "netuid", "type": "uint16"},
                    {"name": "queuedAt", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def create_deposit_id(self, block_hash: str, extrinsic_index: int, ss58_pubkey: str, amount: str, netuid: int) -> str:
        """Create canonical deposit ID"""
        # Convert to bytes for keccak256
        block_hash_bytes = bytes.fromhex(block_hash[2:] if block_hash.startswith('0x') else block_hash)
        ss58_bytes = ss58_pubkey.encode()
        amount_bytes = amount.encode()
        
        # Pack the data
        packed = block_hash_bytes + extrinsic_index.to_bytes(4, 'big') + ss58_bytes + amount_bytes + netuid.to_bytes(2, 'big')
        
        # Hash
        return hashlib.sha256(packed).hexdigest()
    
    def create_mint_claim_json(self, ss58: str, evm: str, deposit_data: Dict, nonce: str, expires: str) -> str:
        """Create the JSON payload for mint claim signature"""
        
        payload = {
            "type": "ALPHAMIND_MINT_CLAIM_V1",
            "ss58": ss58,
            "evm": evm,
            "deposit": deposit_data,
            "chain_id": "subtensor-mainnet",
            "domain": "alphamind.xyz",
            "nonce": nonce,
            "expires": expires
        }
        
        return json.dumps(payload, separators=(',', ':'))
    
    def create_message_hash(self, json_payload: str) -> str:
        """Create keccak256 hash of JSON payload"""
        return self.w3.keccak(text=json_payload).hex()
    
    async def prepare_mint_claim(self, block_hash: str, extrinsic_index: int, ss58: str, evm: str) -> MintPrepareResponse:
        """Prepare a mint claim - returns JSON to sign"""
        
        try:
            # 1. Verify the deposit exists and is finalized
            deposit = await self._verify_deposit(block_hash, extrinsic_index, ss58)
            if not deposit:
                raise HTTPException(status_code=404, detail="Deposit not found or not finalized")
            
            # 2. Generate nonce and expiry
            nonce = str(uuid.uuid4())
            expires = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
            
            # 3. Create deposit data
            deposit_data = {
                "block_hash": block_hash,
                "extrinsic_index": extrinsic_index,
                "asset": f"ALPHA:{deposit.netuid}",
                "amount": deposit.amount
            }
            
            # 4. Create JSON payload
            json_payload = self.create_mint_claim_json(ss58, evm, deposit_data, nonce, expires)
            
            # 5. Create message hash
            message_hash = self.create_message_hash(json_payload)
            
            # 6. Store claim record
            claim_record = ClaimRecord(
                deposit_id=deposit.deposit_id,
                claimer_evm=evm,
                nonce=nonce,
                expires_at=expires,
                message_hash=message_hash,
                created_at=datetime.utcnow().isoformat()
            )
            db.add_claim(claim_record)
            
            # 7. Update deposit status
            db.update_deposit_status(deposit.deposit_id, "queued")
            
            return MintPrepareResponse(
                ss58=ss58,
                evm=evm,
                deposit=deposit_data,
                nonce=nonce,
                expires=expires,
                message_hash=message_hash
            )
            
        except Exception as e:
            logger.error(f"Error preparing mint claim: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _verify_deposit(self, block_hash: str, extrinsic_index: int, ss58: str) -> Optional[DepositRecord]:
        """Verify deposit exists and is finalized"""
        
        # In production, this would:
        # 1. Query Substrate RPC for the specific block/extrinsic
        # 2. Verify the transfer was to the vault SS58
        # 3. Check finality (GRANDPA)
        # 4. Extract amount and netuid
        
        # For now, we'll simulate finding a deposit
        deposit_id = self.create_deposit_id(block_hash, extrinsic_index, ss58, "123456789", 1)
        
        # Check if we already have this deposit
        existing_deposit = db.get_deposit(deposit_id)
        if existing_deposit:
            return existing_deposit
        
        # Simulate finding a new deposit
        # In production, this would come from the Substrate indexer
        deposit = DepositRecord(
            deposit_id=deposit_id,
            block_hash=block_hash,
            extrinsic_index=extrinsic_index,
            ss58_pubkey=ss58,
            netuid=1,  # Would be extracted from the transfer
            amount="123456789",  # Would be extracted from the transfer
            finalized_at=datetime.utcnow().isoformat(),
            status="pending"
        )
        
        db.add_deposit(deposit)
        return deposit
    
    async def get_queue_status(self, address: str) -> QueueStatusResponse:
        """Get queue status for an address"""
        
        try:
            # Get queue length from contract
            queue_length = self.contract.functions.getQueueLength().call()
            
            # Find user's position in queue
            queue_position = None
            estimated_execution = None
            
            for i in range(queue_length):
                try:
                    item = self.contract.functions.getQueueItem(i).call()
                    if item[1].lower() == address.lower():  # claimer address
                        queue_position = i
                        
                        # Estimate execution time (simplified)
                        queued_at = item[4]  # timestamp
                        earliest_execution = queued_at + 300  # 5 minutes
                        estimated_execution = datetime.fromtimestamp(earliest_execution).isoformat()
                        break
                except Exception as e:
                    logger.warning(f"Error getting queue item {i}: {e}")
                    continue
            
            return QueueStatusResponse(
                address=address,
                queue_position=queue_position,
                estimated_execution=estimated_execution,
                last_batch_execution=None,  # Would track from events
                queue_length=queue_length,
                batch_window_minutes=60,  # Configurable
                slippage_cap_percent=1.0  # 1% slippage cap
            )
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def monitor_deposits(self):
        """Monitor for new deposits (background task)"""
        
        logger.info("Starting deposit monitoring")
        
        while True:
            try:
                # In production, this would:
                # 1. Subscribe to finalized blocks via Substrate RPC
                # 2. Watch for Transfer events to vault SS58
                # 3. Extract deposit information
                # 4. Store in database
                
                # For now, we'll just sleep
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in deposit monitoring: {e}")
                await asyncio.sleep(30)

# Initialize API
api = ConcreteMintAPI()

@app.on_event("startup")
async def startup_event():
    """Initialize the API on startup"""
    logger.info("Concrete Mint API initialized")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "TAO20 Concrete Mint API",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/mint/prepare", response_model=MintPrepareResponse)
async def prepare_mint(request: MintPrepareRequest, background_tasks: BackgroundTasks):
    """Prepare a mint claim - returns JSON to sign"""
    
    # In production, you'd get these from the request context
    ss58 = "user_ss58_address_here"  # Would come from wallet connection
    evm = "user_evm_address_here"    # Would come from wallet connection
    
    return await api.prepare_mint_claim(
        request.block_hash,
        request.extrinsic_index,
        ss58,
        evm
    )

@app.get("/queue/status", response_model=QueueStatusResponse)
async def get_queue_status(address: str):
    """Get queue status for an address"""
    return await api.get_queue_status(address)

@app.get("/deposits/{deposit_id}", response_model=DepositRecord)
async def get_deposit(deposit_id: str):
    """Get deposit status"""
    deposit = db.get_deposit(deposit_id)
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return deposit

@app.get("/claims/{address}", response_model=List[ClaimRecord])
async def get_user_claims(address: str):
    """Get all claims for a user address"""
    return db.get_claims_by_address(address)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check contract connection
        queue_length = api.contract.functions.getQueueLength().call()
        
        return {
            "status": "healthy",
            "queue_length": queue_length,
            "contract_address": api.contract_address,
            "vault_ss58": api.vault_ss58
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "subnet.api.concrete_mint_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
