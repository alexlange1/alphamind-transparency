#!/usr/bin/env python3
"""
FastAPI Server for TAO20 Minting System
Provides REST endpoints for deposit tracking and minting
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from .tao20_minting_api import TAO20MintingAPI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class DepositRequest(BaseModel):
    user_address: str
    netuid: int
    amount: float

class MintRequest(BaseModel):
    user_address: str
    deposit_info: Dict
    signature: str
    message: str

class BatchMintRequest(BaseModel):
    mint_requests: List[MintRequest]

class DepositStatusResponse(BaseModel):
    deposit_id: str
    status: str
    user_address: str
    netuid: int
    amount: float
    timestamp: float
    nav_at_deposit: float
    tao20_amount: Optional[float] = None
    transaction_hash: Optional[str] = None
    error_message: Optional[str] = None

class MintResponse(BaseModel):
    success: bool
    deposit_id: Optional[str] = None
    tao20_amount: Optional[float] = None
    transaction_hash: Optional[str] = None
    nav_at_deposit: Optional[float] = None
    error: Optional[str] = None

class VaultSummaryResponse(BaseModel):
    total_deposits_value: float
    total_tao20_minted: float
    current_nav: float
    fees_accrued: float
    deposits_by_subnet: Dict[int, float]
    total_deposits_count: int

# Initialize FastAPI app
app = FastAPI(
    title="TAO20 Minting API",
    description="API for TAO20 index token minting and vault operations",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global API instance
api: Optional[TAO20MintingAPI] = None

def get_api() -> TAO20MintingAPI:
    """Get the global API instance"""
    if api is None:
        raise HTTPException(status_code=500, detail="API not initialized")
    return api

@app.on_event("startup")
async def startup_event():
    """Initialize the API on startup"""
    global api
    
    # Load configuration from environment variables
    vault_coldkey = os.environ.get("TAO20_VAULT_COLDKEY")
    vault_hotkey = os.environ.get("TAO20_VAULT_HOTKEY")
    contract_address = os.environ.get("TAO20_CONTRACT_ADDRESS")
    rpc_url = os.environ.get("TAO20_RPC_URL", "http://127.0.0.1:9944")
    miner_wallet_path = os.environ.get("TAO20_MINER_WALLET_PATH")
    miner_hotkey_path = os.environ.get("TAO20_MINER_HOTKEY_PATH")
    subtensor_network = os.environ.get("TAO20_SUBTENSOR_NETWORK", "finney")
    
    # Validate required environment variables
    required_vars = [
        "TAO20_VAULT_COLDKEY",
        "TAO20_VAULT_HOTKEY", 
        "TAO20_CONTRACT_ADDRESS",
        "TAO20_MINER_WALLET_PATH",
        "TAO20_MINER_HOTKEY_PATH"
    ]
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    # Initialize API
    api = TAO20MintingAPI(
        vault_coldkey=vault_coldkey,
        vault_hotkey=vault_hotkey,
        contract_address=contract_address,
        rpc_url=rpc_url,
        miner_wallet_path=miner_wallet_path,
        miner_hotkey_path=miner_hotkey_path,
        subtensor_network=subtensor_network
    )
    
    logger.info("TAO20 Minting API initialized successfully")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "TAO20 Minting API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        api_instance = get_api()
        vault_summary = await api_instance.get_vault_summary()
        
        return {
            "status": "healthy",
            "vault_summary": vault_summary
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deposits/track", response_model=Dict[str, str])
async def track_deposit(request: DepositRequest):
    """Track a new deposit"""
    try:
        api_instance = get_api()
        deposit_id = await api_instance.track_new_deposit(
            user_address=request.user_address,
            netuid=request.netuid,
            amount=request.amount
        )
        
        return {
            "deposit_id": deposit_id,
            "message": "Deposit tracked successfully"
        }
    except Exception as e:
        logger.error(f"Error tracking deposit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mint", response_model=MintResponse)
async def mint_tao20(request: MintRequest):
    """Mint TAO20 tokens for a deposit"""
    try:
        api_instance = get_api()
        result = await api_instance.process_mint_request(
            user_address=request.user_address,
            deposit_info=request.deposit_info,
            signature=request.signature,
            message=request.message
        )
        
        return MintResponse(**result)
    except Exception as e:
        logger.error(f"Error processing mint request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mint/batch", response_model=List[MintResponse])
async def batch_mint_tao20(request: BatchMintRequest):
    """Process multiple mint requests in batch"""
    try:
        api_instance = get_api()
        
        # Convert to list of dictionaries
        mint_requests = [
            {
                'user_address': req.user_address,
                'deposit_info': req.deposit_info,
                'signature': req.signature,
                'message': req.message
            }
            for req in request.mint_requests
        ]
        
        results = await api_instance.process_batch_mints(mint_requests)
        
        return [MintResponse(**result) for result in results]
    except Exception as e:
        logger.error(f"Error processing batch mint requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/deposits/{deposit_id}", response_model=DepositStatusResponse)
async def get_deposit_status(deposit_id: str):
    """Get status of a specific deposit"""
    try:
        api_instance = get_api()
        status = await api_instance.get_deposit_status(deposit_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="Deposit not found")
        
        return DepositStatusResponse(**status)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deposit status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/deposits/user/{user_address}", response_model=List[DepositStatusResponse])
async def get_user_deposits(user_address: str):
    """Get all deposits for a specific user"""
    try:
        api_instance = get_api()
        deposits = await api_instance.get_user_deposits(user_address)
        
        return [DepositStatusResponse(**deposit) for deposit in deposits]
    except Exception as e:
        logger.error(f"Error getting user deposits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vault/summary", response_model=VaultSummaryResponse)
async def get_vault_summary():
    """Get summary of vault state"""
    try:
        api_instance = get_api()
        summary = await api_instance.get_vault_summary()
        
        return VaultSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Error getting vault summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deposits/validate")
async def validate_deposits(deposit_ids: List[str]):
    """Validate a batch of deposits"""
    try:
        api_instance = get_api()
        valid_deposits, invalid_deposits = await api_instance.validate_deposit_batch(deposit_ids)
        
        return {
            "valid_deposits": valid_deposits,
            "invalid_deposits": invalid_deposits,
            "total_valid": len(valid_deposits),
            "total_invalid": len(invalid_deposits)
        }
    except Exception as e:
        logger.error(f"Error validating deposits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/maintenance/cleanup")
async def cleanup_old_deposits(days_old: int = 30, background_tasks: BackgroundTasks = None):
    """Clean up old completed deposits"""
    try:
        api_instance = get_api()
        
        if background_tasks:
            # Run cleanup in background
            background_tasks.add_task(api_instance.cleanup_old_deposits, days_old)
            return {"message": f"Cleanup scheduled for deposits older than {days_old} days"}
        else:
            # Run cleanup synchronously
            await api_instance.cleanup_old_deposits(days_old)
            return {"message": f"Cleanup completed for deposits older than {days_old} days"}
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/nav/current")
async def get_current_nav():
    """Get current NAV for TAO20 index"""
    try:
        api_instance = get_api()
        nav = await api_instance.vault_manager.get_current_nav()
        
        return {
            "nav": nav,
            "timestamp": asyncio.get_event_loop().time()
        }
    except Exception as e:
        logger.error(f"Error getting current NAV: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run the server
    port = int(os.environ.get("TAO20_API_PORT", "8000"))
    host = os.environ.get("TAO20_API_HOST", "0.0.0.0")
    
    uvicorn.run(
        "subnet.api.fastapi_server:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
