"""
Creation File Specification for TAO20 Creation Unit System

Defines the structure and validation for creation files.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from .epoch_manager import CreationFile, AssetSpecification

logger = logging.getLogger(__name__)

@dataclass
class CreationFileSpec:
    """Specification for creation file structure and validation"""
    
    # Required fields
    required_fields = [
        'epoch_id', 'weights_hash', 'valid_from', 'valid_until',
        'creation_unit_size', 'cash_component_bps', 'tolerance_bps',
        'min_creation_size', 'assets', 'published_at', 'published_by'
    ]
    
    # Field types and constraints
    field_constraints = {
        'epoch_id': {'type': int, 'min': 1},
        'weights_hash': {'type': str, 'pattern': r'^0x[a-fA-F0-9]{64}$'},
        'valid_from': {'type': int, 'min': 0},
        'valid_until': {'type': int, 'min': 0},
        'creation_unit_size': {'type': int, 'min': 1},
        'cash_component_bps': {'type': int, 'min': 0, 'max': 1000},
        'tolerance_bps': {'type': int, 'min': 0, 'max': 100},
        'min_creation_size': {'type': int, 'min': 1},
        'published_at': {'type': int, 'min': 0},
        'published_by': {'type': str, 'min_length': 1}
    }

class CreationFileValidator:
    """Validates creation files against specifications"""
    
    def __init__(self):
        self.spec = CreationFileSpec()
    
    def validate_creation_file(self, creation_file: CreationFile) -> List[str]:
        """
        Validate a creation file and return list of errors
        
        Args:
            creation_file: CreationFile object to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Convert to dict for validation
        data = asdict(creation_file)
        
        # Validate required fields
        for field in self.spec.required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return errors
        
        # Validate field types and constraints
        for field, value in data.items():
            if field in self.spec.field_constraints:
                constraint = self.spec.field_constraints[field]
                field_errors = self._validate_field(field, value, constraint)
                errors.extend(field_errors)
        
        # Validate assets
        if 'assets' in data:
            asset_errors = self._validate_assets(data['assets'])
            errors.extend(asset_errors)
        
        # Validate epoch consistency
        epoch_errors = self._validate_epoch_consistency(data)
        errors.extend(epoch_errors)
        
        # Validate weights consistency
        weights_errors = self._validate_weights_consistency(data)
        errors.extend(weights_errors)
        
        return errors
    
    def _validate_field(self, field: str, value: Any, constraint: Dict) -> List[str]:
        """Validate a single field against its constraints"""
        errors = []
        
        # Type validation
        if 'type' in constraint:
            if not isinstance(value, constraint['type']):
                errors.append(f"Field {field} must be {constraint['type'].__name__}, got {type(value).__name__}")
                return errors
        
        # Range validation
        if 'min' in constraint and value < constraint['min']:
            errors.append(f"Field {field} must be >= {constraint['min']}, got {value}")
        
        if 'max' in constraint and value > constraint['max']:
            errors.append(f"Field {field} must be <= {constraint['max']}, got {value}")
        
        # String length validation
        if 'min_length' in constraint and isinstance(value, str):
            if len(value) < constraint['min_length']:
                errors.append(f"Field {field} must have length >= {constraint['min_length']}, got {len(value)}")
        
        # Pattern validation
        if 'pattern' in constraint and isinstance(value, str):
            import re
            if not re.match(constraint['pattern'], value):
                errors.append(f"Field {field} does not match pattern {constraint['pattern']}")
        
        return errors
    
    def _validate_assets(self, assets: List[Dict]) -> List[str]:
        """Validate assets list"""
        errors = []
        
        if not isinstance(assets, list):
            errors.append("Assets must be a list")
            return errors
        
        if len(assets) != 20:
            errors.append(f"Must have exactly 20 assets, got {len(assets)}")
        
        # Validate each asset
        for i, asset in enumerate(assets):
            asset_errors = self._validate_asset(asset, i)
            errors.extend(asset_errors)
        
        # Check for duplicate netuids
        netuids = [asset.get('netuid') for asset in assets if isinstance(asset, dict)]
        if len(netuids) != len(set(netuids)):
            errors.append("Duplicate netuids found in assets")
        
        return errors
    
    def _validate_asset(self, asset: Dict, index: int) -> List[str]:
        """Validate a single asset"""
        errors = []
        
        if not isinstance(asset, dict):
            errors.append(f"Asset {index} must be a dictionary")
            return errors
        
        # Required asset fields
        required_fields = ['netuid', 'asset_id', 'qty_per_creation_unit', 'weight_bps']
        for field in required_fields:
            if field not in asset:
                errors.append(f"Asset {index} missing required field: {field}")
        
        if errors:
            return errors
        
        # Validate netuid
        netuid = asset.get('netuid')
        if not isinstance(netuid, int) or netuid < 0:
            errors.append(f"Asset {index} netuid must be non-negative integer")
        
        # Validate asset_id
        asset_id = asset.get('asset_id')
        if not isinstance(asset_id, str) or not asset_id.startswith('0x'):
            errors.append(f"Asset {index} asset_id must be hex string starting with 0x")
        
        # Validate qty_per_creation_unit
        qty = asset.get('qty_per_creation_unit')
        if not isinstance(qty, int) or qty <= 0:
            errors.append(f"Asset {index} qty_per_creation_unit must be positive integer")
        
        # Validate weight_bps
        weight_bps = asset.get('weight_bps')
        if not isinstance(weight_bps, int) or weight_bps < 0 or weight_bps > 10000:
            errors.append(f"Asset {index} weight_bps must be between 0 and 10000")
        
        return errors
    
    def _validate_epoch_consistency(self, data: Dict) -> List[str]:
        """Validate epoch consistency"""
        errors = []
        
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        
        if valid_from is not None and valid_until is not None:
            if valid_from >= valid_until:
                errors.append("valid_from must be before valid_until")
            
            if valid_until - valid_from != 1209600:  # 14 days
                errors.append("Epoch duration must be exactly 14 days (1209600 seconds)")
        
        return errors
    
    def _validate_weights_consistency(self, data: Dict) -> List[str]:
        """Validate weights consistency"""
        errors = []
        
        assets = data.get('assets', [])
        if not assets:
            return errors
        
        # Check total weight
        total_weight_bps = sum(asset.get('weight_bps', 0) for asset in assets)
        if total_weight_bps != 10000:
            errors.append(f"Total weight must be 10000 basis points, got {total_weight_bps}")
        
        return errors

class CreationFileSerializer:
    """Handles serialization and deserialization of creation files"""
    
    def __init__(self):
        self.validator = CreationFileValidator()
    
    def to_json(self, creation_file: CreationFile, indent: int = 2) -> str:
        """Convert creation file to JSON string"""
        data = asdict(creation_file)
        data['assets'] = [asdict(asset) for asset in creation_file.assets]
        return json.dumps(data, indent=indent)
    
    def from_json(self, json_str: str) -> CreationFile:
        """Create creation file from JSON string"""
        data = json.loads(json_str)
        return self.from_dict(data)
    
    def from_dict(self, data: Dict) -> CreationFile:
        """Create creation file from dictionary"""
        assets_data = data.pop('assets', [])
        assets = [AssetSpecification(**asset_data) for asset_data in assets_data]
        
        data['assets'] = assets
        creation_file = CreationFile(**data)
        
        # Validate the creation file
        errors = self.validator.validate_creation_file(creation_file)
        if errors:
            raise ValueError(f"Invalid creation file: {'; '.join(errors)}")
        
        return creation_file
    
    def save_to_file(self, creation_file: CreationFile, filepath: str):
        """Save creation file to JSON file"""
        json_str = self.to_json(creation_file)
        
        with open(filepath, 'w') as f:
            f.write(json_str)
        
        logger.info(f"Saved creation file to {filepath}")
    
    def load_from_file(self, filepath: str) -> CreationFile:
        """Load creation file from JSON file"""
        with open(filepath, 'r') as f:
            json_str = f.read()
        
        creation_file = self.from_json(json_str)
        logger.info(f"Loaded creation file from {filepath}")
        return creation_file

# Removed sample creation file function - production launch ready
