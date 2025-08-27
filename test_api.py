#!/usr/bin/env python3
"""
Simple test API server for TAO20 simulation
"""

import asyncio
import time
from typing import Dict, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="TAO20 Test API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for testing
creations = {}
current_epoch = 1

class CreationRequest(BaseModel):
    epoch_id: int
    source_ss58: str
    evm_addr: str
    unit_count: int
    weights_hash: str

class TransferUpdate(BaseModel):
    transfers: List[Dict]

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/creations")
async def register_creation(request: CreationRequest):
    creation_id = f"creation_{len(creations) + 1}_{int(time.time())}"
    deadline_ts = int(time.time()) + 600  # 10 minutes from now
    
    creations[creation_id] = {
        "creation_id": creation_id,
        "epoch_id": request.epoch_id,
        "source_ss58": request.source_ss58,
        "evm_addr": request.evm_addr,
        "unit_count": request.unit_count,
        "weights_hash": request.weights_hash,
        "deadline_ts": deadline_ts,
        "status": "registered",
        "transfers": [],
        "created_at": time.time()
    }
    
    return {
        "creation_id": creation_id,
        "deadline_ts": deadline_ts,
        "epoch_id": request.epoch_id,
        "weights_hash": request.weights_hash
    }

@app.post("/creations/{creation_id}/transfers")
async def update_transfers(creation_id: str, update: TransferUpdate):
    if creation_id not in creations:
        return {"error": "Creation not found"}, 404
    
    creations[creation_id]["transfers"] = update.transfers
    creations[creation_id]["status"] = "transfers_submitted"
    
    # Simulate processing delay
    await asyncio.sleep(2)
    creations[creation_id]["status"] = "receipt_valid"
    
    return {"status": "success", "creation_id": creation_id}

@app.get("/creations/{creation_id}/status")
async def get_creation_status(creation_id: str):
    if creation_id not in creations:
        return {"error": "Creation not found"}, 404
    
    creation = creations[creation_id]
    
    # Simulate status progression
    current_time = time.time()
    age = current_time - creation["created_at"]
    
    if age > 60:  # After 1 minute, mark as receipt_valid
        creation["status"] = "receipt_valid"
    elif age > 30:  # After 30 seconds, mark as processing
        creation["status"] = "processing"
    
    return {
        "status": creation["status"],
        "creation_id": creation_id,
        "deadline_ts": creation["deadline_ts"]
    }

@app.get("/epoch/current")
async def get_current_epoch():
    return {
        "epoch_id": current_epoch,
        "weights_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "valid_until": int(time.time()) + 3600  # Valid for 1 hour
    }

@app.get("/creations")
async def list_creations():
    return {"creations": list(creations.values())}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
