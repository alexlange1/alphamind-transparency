"""
Epoch Manager for TAO20 Creation Unit System

Handles epoch transitions, creation file publishing, and epoch boundary enforcement.
"""

import time
import hashlib
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class AssetSpecification:
    """Specification for a single asset in the creation file"""
    netuid: int
    asset_id: str
    qty_per_creation_unit: int
    weight_bps: int  # Weight in basis points (1/10000)

@dataclass
class CreationFile:
    """Creation file specification for an epoch"""
    epoch_id: int
    weights_hash: str
    valid_from: int
    valid_until: int
    creation_unit_size: int
    cash_component_bps: int
    tolerance_bps: int
    min_creation_size: int
    assets: List[AssetSpecification]
    published_at: int
    published_by: str

class EpochManager:
    """
    Manages epochs and creation files for the TAO20 creation unit system.
    
    Epochs are 14 days long and contain frozen weight specifications.
    """
    
    def __init__(self):
        self.epoch_duration = 1209600  # 14 days in seconds
        self.creation_files: Dict[int, CreationFile] = {}
        self.current_epoch_id: Optional[int] = None
        self.epoch_start_time: Optional[int] = None
        
        # Default parameters
        self.default_creation_unit_size = 1000
        self.default_cash_component_bps = 50  # 0.5%
        self.default_tolerance_bps = 5  # 0.05%
        self.default_min_creation_size = 1000
        
        logger.info("EpochManager initialized")
    
    def get_current_epoch_id(self) -> int:
        """Get the current epoch ID based on time"""
        if self.epoch_start_time is None:
            # Initialize with current time
            self.epoch_start_time = int(time.time())
        
        current_time = int(time.time())
        epoch_start = self.epoch_start_time
        
        # Calculate epoch ID
        epoch_id = ((current_time - epoch_start) // self.epoch_duration) + 1
        return epoch_id
    
    def get_epoch_start(self, epoch_id: int) -> int:
        """Get the start timestamp for a given epoch"""
        if self.epoch_start_time is None:
            self.epoch_start_time = int(time.time())
        
        epoch_start = self.epoch_start_time + (epoch_id - 1) * self.epoch_duration
        return epoch_start
    
    def get_epoch_end(self, epoch_id: int) -> int:
        """Get the end timestamp for a given epoch"""
        return self.get_epoch_start(epoch_id) + self.epoch_duration
    
    def is_epoch_active(self, epoch_id: int) -> bool:
        """Check if an epoch is currently active"""
        current_time = int(time.time())
        epoch_start = self.get_epoch_start(epoch_id)
        epoch_end = self.get_epoch_end(epoch_id)
        
        return epoch_start <= current_time < epoch_end
    
    def calculate_weights_hash(self, weights: Dict[int, float]) -> str:
        """Calculate hash of weights for verification"""
        # Sort weights by netuid for consistent hashing
        sorted_weights = sorted(weights.items())
        weights_str = json.dumps(sorted_weights, sort_keys=True)
        
        # Calculate SHA256 hash
        weights_hash = hashlib.sha256(weights_str.encode()).hexdigest()
        return f"0x{weights_hash}"
    
    def calculate_qty_per_unit(self, netuid: int, weight: float, total_value: float = 1e18) -> int:
        """
        Calculate quantity per creation unit for a given asset
        
        Args:
            netuid: Subnet ID
            weight: Weight as fraction (0.0 to 1.0)
            total_value: Total value per creation unit (default 1e18)
        
        Returns:
            Quantity per creation unit in smallest units
        """
        # For now, use a simple calculation
        # In production, this would use actual price data
        qty_per_unit = int(total_value * weight)
        return qty_per_unit
    
    def get_asset_id(self, netuid: int) -> str:
        """Get asset ID for a given subnet"""
        # For now, use a simple mapping
        # In production, this would query the actual asset registry
        return f"0x{netuid:064x}"
    
    def calculate_asset_specifications(self, weights: Dict[int, float]) -> List[AssetSpecification]:
        """Calculate asset specifications for creation file"""
        assets = []
        
        for netuid, weight in weights.items():
            # Calculate quantity per creation unit based on weight
            qty_per_unit = self.calculate_qty_per_unit(netuid, weight)
            
            asset_spec = AssetSpecification(
                netuid=netuid,
                asset_id=self.get_asset_id(netuid),
                qty_per_creation_unit=qty_per_unit,
                weight_bps=int(weight * 10000)
            )
            assets.append(asset_spec)
        
        return assets
    
    async def publish_creation_file(
        self, 
        epoch_id: int, 
        weights: Dict[int, float],
        published_by: str = "system"
    ) -> CreationFile:
        """
        Publish creation file for a new epoch
        
        Args:
            epoch_id: Epoch ID
            weights: Dictionary mapping netuid to weight (0.0 to 1.0)
            published_by: Identifier of who published the file
        
        Returns:
            CreationFile object
        """
        logger.info(f"Publishing creation file for epoch {epoch_id}")
        
        # Validate weights
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.001:  # Allow small rounding errors
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")
        
        if len(weights) != 20:
            raise ValueError(f"Must have exactly 20 subnets, got {len(weights)}")
        
        # Calculate weights hash
        weights_hash = self.calculate_weights_hash(weights)
        
        # Calculate epoch timestamps
        valid_from = self.get_epoch_start(epoch_id)
        valid_until = self.get_epoch_end(epoch_id)
        
        # Calculate asset specifications
        assets = self.calculate_asset_specifications(weights)
        
        # Create creation file
        creation_file = CreationFile(
            epoch_id=epoch_id,
            weights_hash=weights_hash,
            valid_from=valid_from,
            valid_until=valid_until,
            creation_unit_size=self.default_creation_unit_size,
            cash_component_bps=self.default_cash_component_bps,
            tolerance_bps=self.default_tolerance_bps,
            min_creation_size=self.default_min_creation_size,
            assets=assets,
            published_at=int(time.time()),
            published_by=published_by
        )
        
        # Store creation file
        self.creation_files[epoch_id] = creation_file
        
        # Update current epoch if this is the current epoch
        current_epoch = self.get_current_epoch_id()
        if epoch_id == current_epoch:
            self.current_epoch_id = epoch_id
        
        logger.info(f"Published creation file for epoch {epoch_id} with {len(assets)} assets")
        return creation_file
    
    def get_creation_file(self, epoch_id: int) -> Optional[CreationFile]:
        """Get creation file for a specific epoch"""
        return self.creation_files.get(epoch_id)
    
    def get_current_creation_file(self) -> Optional[CreationFile]:
        """Get creation file for the current epoch"""
        current_epoch = self.get_current_epoch_id()
        return self.get_creation_file(current_epoch)
    
    def is_creation_file_valid(self, epoch_id: int) -> bool:
        """Check if creation file is valid for the given epoch"""
        creation_file = self.get_creation_file(epoch_id)
        if not creation_file:
            return False
        
        current_time = int(time.time())
        return creation_file.valid_from <= current_time < creation_file.valid_until
    
    def get_expired_epochs(self) -> List[int]:
        """Get list of expired epochs"""
        current_time = int(time.time())
        expired_epochs = []
        
        for epoch_id, creation_file in self.creation_files.items():
            if current_time >= creation_file.valid_until:
                expired_epochs.append(epoch_id)
        
        return expired_epochs
    
    def cleanup_expired_epochs(self) -> int:
        """Clean up expired epochs and return number of cleaned epochs"""
        expired_epochs = self.get_expired_epochs()
        
        for epoch_id in expired_epochs:
            del self.creation_files[epoch_id]
            logger.info(f"Cleaned up expired epoch {epoch_id}")
        
        return len(expired_epochs)
    
    def to_dict(self, creation_file: CreationFile) -> Dict:
        """Convert creation file to dictionary for serialization"""
        data = asdict(creation_file)
        data['assets'] = [asdict(asset) for asset in creation_file.assets]
        return data
    
    def from_dict(self, data: Dict) -> CreationFile:
        """Create creation file from dictionary"""
        assets_data = data.pop('assets', [])
        assets = [AssetSpecification(**asset_data) for asset_data in assets_data]
        
        data['assets'] = assets
        return CreationFile(**data)
    
    async def save_creation_file(self, epoch_id: int, filepath: str):
        """Save creation file to disk"""
        creation_file = self.get_creation_file(epoch_id)
        if not creation_file:
            raise ValueError(f"No creation file found for epoch {epoch_id}")
        
        data = self.to_dict(creation_file)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved creation file for epoch {epoch_id} to {filepath}")
    
    async def load_creation_file(self, filepath: str) -> CreationFile:
        """Load creation file from disk"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        creation_file = self.from_dict(data)
        self.creation_files[creation_file.epoch_id] = creation_file
        
        logger.info(f"Loaded creation file for epoch {creation_file.epoch_id} from {filepath}")
        return creation_file
