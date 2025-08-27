"""
Weights Calculator for TAO20 Creation Unit System

Handles weight calculations, validation, and updates for the creation unit system.
"""

import hashlib
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class WeightUpdate:
    """Represents a weight update for an epoch"""
    epoch_id: int
    weights: Dict[int, float]
    weights_hash: str
    updated_at: int
    updated_by: str
    reason: str
    metadata: Dict

class WeightsCalculator:
    """
    Calculates and validates weights for TAO20 creation units.
    
    Handles weight normalization, validation, and hash calculation.
    """
    
    def __init__(self):
        self.min_weight = 0.01  # 1% minimum weight
        self.max_weight = 0.20  # 20% maximum weight
        self.total_weight_tolerance = 0.001  # 0.1% tolerance for total weight
    
    def calculate_weights_from_stake(self, stake_data: Dict[int, float]) -> Dict[int, float]:
        """
        Calculate weights based on stake data
        
        Args:
            stake_data: Dictionary mapping netuid to stake amount
            
        Returns:
            Dictionary mapping netuid to normalized weight
        """
        total_stake = sum(stake_data.values())
        
        if total_stake == 0:
            raise ValueError("Total stake cannot be zero")
        
        # Calculate raw weights
        raw_weights = {}
        for netuid, stake in stake_data.items():
            raw_weights[netuid] = stake / total_stake
        
        # Normalize weights
        normalized_weights = self.normalize_weights(raw_weights)
        
        return normalized_weights
    
    def calculate_weights_from_market_cap(self, market_cap_data: Dict[int, float]) -> Dict[int, float]:
        """
        Calculate weights based on market capitalization
        
        Args:
            market_cap_data: Dictionary mapping netuid to market cap
            
        Returns:
            Dictionary mapping netuid to normalized weight
        """
        total_market_cap = sum(market_cap_data.values())
        
        if total_market_cap == 0:
            raise ValueError("Total market cap cannot be zero")
        
        # Calculate raw weights
        raw_weights = {}
        for netuid, market_cap in market_cap_data.items():
            raw_weights[netuid] = market_cap / total_market_cap
        
        # Normalize weights
        normalized_weights = self.normalize_weights(raw_weights)
        
        return normalized_weights
    
    def calculate_weights_from_performance(self, performance_data: Dict[int, float]) -> Dict[int, float]:
        """
        Calculate weights based on performance metrics
        
        Args:
            performance_data: Dictionary mapping netuid to performance score
            
        Returns:
            Dictionary mapping netuid to normalized weight
        """
        # Apply performance adjustments
        adjusted_weights = {}
        for netuid, performance in performance_data.items():
            # Simple performance adjustment (can be made more sophisticated)
            adjusted_weights[netuid] = max(0.01, performance)  # Minimum 1%
        
        # Normalize weights
        normalized_weights = self.normalize_weights(adjusted_weights)
        
        return normalized_weights
    
    def normalize_weights(self, raw_weights: Dict[int, float]) -> Dict[int, float]:
        """
        Normalize weights to sum to 1.0 and apply constraints
        
        Args:
            raw_weights: Raw weights dictionary
            
        Returns:
            Normalized weights dictionary
        """
        total_weight = sum(raw_weights.values())
        
        if total_weight == 0:
            raise ValueError("Total weight cannot be zero")
        
        # Normalize to sum to 1.0
        normalized = {}
        for netuid, weight in raw_weights.items():
            normalized[netuid] = weight / total_weight
        
        # Apply minimum and maximum constraints
        constrained = self.apply_weight_constraints(normalized)
        
        # Re-normalize after applying constraints
        final_weights = self.renormalize_weights(constrained)
        
        return final_weights
    
    def apply_weight_constraints(self, weights: Dict[int, float]) -> Dict[int, float]:
        """
        Apply minimum and maximum weight constraints
        
        Args:
            weights: Input weights dictionary
            
        Returns:
            Constrained weights dictionary
        """
        constrained = {}
        
        for netuid, weight in weights.items():
            # Apply minimum weight constraint
            if weight < self.min_weight:
                constrained[netuid] = self.min_weight
            # Apply maximum weight constraint
            elif weight > self.max_weight:
                constrained[netuid] = self.max_weight
            else:
                constrained[netuid] = weight
        
        return constrained
    
    def renormalize_weights(self, weights: Dict[int, float]) -> Dict[int, float]:
        """
        Re-normalize weights after applying constraints
        
        Args:
            weights: Constrained weights dictionary
            
        Returns:
            Re-normalized weights dictionary
        """
        total_weight = sum(weights.values())
        
        if total_weight == 0:
            raise ValueError("Total weight cannot be zero after constraints")
        
        # Re-normalize
        renormalized = {}
        for netuid, weight in weights.items():
            renormalized[netuid] = weight / total_weight
        
        return renormalized
    
    def validate_weights(self, weights: Dict[int, float]) -> List[str]:
        """
        Validate weights and return list of errors
        
        Args:
            weights: Weights dictionary to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check if weights is a dictionary
        if not isinstance(weights, dict):
            errors.append("Weights must be a dictionary")
            return errors
        
        # Check for empty weights
        if not weights:
            errors.append("Weights cannot be empty")
            return errors
        
        # Check for exactly 20 subnets
        if len(weights) != 20:
            errors.append(f"Must have exactly 20 subnets, got {len(weights)}")
        
        # Check each weight
        total_weight = 0
        for netuid, weight in weights.items():
            # Check netuid type
            if not isinstance(netuid, int) or netuid < 0:
                errors.append(f"Netuid must be non-negative integer, got {netuid}")
            
            # Check weight type and range
            if not isinstance(weight, (int, float)):
                errors.append(f"Weight must be numeric, got {type(weight).__name__}")
            elif weight < 0:
                errors.append(f"Weight must be non-negative, got {weight}")
            elif weight > 1:
                errors.append(f"Weight must be <= 1.0, got {weight}")
            else:
                total_weight += weight
        
        # Check total weight
        if abs(total_weight - 1.0) > self.total_weight_tolerance:
            errors.append(f"Total weight must be 1.0, got {total_weight}")
        
        # Check minimum and maximum constraints
        for netuid, weight in weights.items():
            if weight < self.min_weight:
                errors.append(f"Weight for subnet {netuid} below minimum {self.min_weight}")
            elif weight > self.max_weight:
                errors.append(f"Weight for subnet {netuid} above maximum {self.max_weight}")
        
        return errors
    
    def calculate_weights_hash(self, weights: Dict[int, float]) -> str:
        """
        Calculate hash of weights for verification
        
        Args:
            weights: Weights dictionary
            
        Returns:
            SHA256 hash of weights
        """
        # Sort weights by netuid for consistent hashing
        sorted_weights = sorted(weights.items())
        weights_str = json.dumps(sorted_weights, sort_keys=True)
        
        # Calculate SHA256 hash
        weights_hash = hashlib.sha256(weights_str.encode()).hexdigest()
        return f"0x{weights_hash}"
    
    def get_weight_statistics(self, weights: Dict[int, float]) -> Dict:
        """
        Get statistics about weights
        
        Args:
            weights: Weights dictionary
            
        Returns:
            Dictionary with weight statistics
        """
        if not weights:
            return {}
        
        weight_values = list(weights.values())
        
        stats = {
            'total_subnets': len(weights),
            'total_weight': sum(weight_values),
            'min_weight': min(weight_values),
            'max_weight': max(weight_values),
            'avg_weight': sum(weight_values) / len(weight_values),
            'weight_variance': self._calculate_variance(weight_values),
            'subnets_at_min': sum(1 for w in weight_values if w <= self.min_weight + 0.001),
            'subnets_at_max': sum(1 for w in weight_values if w >= self.max_weight - 0.001)
        }
        
        return stats
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values"""
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance
    
    def create_equal_weight_distribution(self, subnet_count: int = 20) -> Dict[int, float]:
        """
        Create equal weight distribution for testing
        
        Args:
            subnet_count: Number of subnets
            
        Returns:
            Dictionary with equal weights
        """
        weight_per_subnet = 1.0 / subnet_count
        
        weights = {}
        for i in range(1, subnet_count + 1):
            weights[i] = weight_per_subnet
        
        return weights
    
    def create_market_cap_weighted_distribution(self, market_caps: Dict[int, float]) -> Dict[int, float]:
        """
        Create market cap weighted distribution
        
        Args:
            market_caps: Dictionary mapping netuid to market cap
            
        Returns:
            Dictionary with market cap weighted distribution
        """
        return self.calculate_weights_from_market_cap(market_caps)
    
    def create_performance_weighted_distribution(self, performance_scores: Dict[int, float]) -> Dict[int, float]:
        """
        Create performance weighted distribution
        
        Args:
            performance_scores: Dictionary mapping netuid to performance score
            
        Returns:
            Dictionary with performance weighted distribution
        """
        return self.calculate_weights_from_performance(performance_scores)

class WeightUpdateManager:
    """Manages weight updates and their history"""
    
    def __init__(self):
        self.weight_updates: List[WeightUpdate] = []
        self.calculator = WeightsCalculator()
    
    def add_weight_update(
        self,
        epoch_id: int,
        weights: Dict[int, float],
        updated_by: str,
        reason: str,
        metadata: Optional[Dict] = None
    ) -> WeightUpdate:
        """
        Add a new weight update
        
        Args:
            epoch_id: Epoch ID for the update
            weights: New weights dictionary
            updated_by: Who made the update
            reason: Reason for the update
            metadata: Additional metadata
            
        Returns:
            WeightUpdate object
        """
        # Validate weights
        errors = self.calculator.validate_weights(weights)
        if errors:
            raise ValueError(f"Weight validation failed: {'; '.join(errors)}")
        
        # Calculate weights hash
        weights_hash = self.calculator.calculate_weights_hash(weights)
        
        # Create weight update
        weight_update = WeightUpdate(
            epoch_id=epoch_id,
            weights=weights.copy(),
            weights_hash=weights_hash,
            updated_at=int(datetime.now().timestamp()),
            updated_by=updated_by,
            reason=reason,
            metadata=metadata or {}
        )
        
        # Add to history
        self.weight_updates.append(weight_update)
        
        logger.info(f"Added weight update for epoch {epoch_id} by {updated_by}")
        return weight_update
    
    def get_weight_update(self, epoch_id: int) -> Optional[WeightUpdate]:
        """Get weight update for a specific epoch"""
        for update in reversed(self.weight_updates):
            if update.epoch_id == epoch_id:
                return update
        return None
    
    def get_latest_weight_update(self) -> Optional[WeightUpdate]:
        """Get the most recent weight update"""
        if self.weight_updates:
            return self.weight_updates[-1]
        return None
    
    def get_weight_history(self, start_epoch: Optional[int] = None, end_epoch: Optional[int] = None) -> List[WeightUpdate]:
        """Get weight update history within a range"""
        filtered_updates = []
        
        for update in self.weight_updates:
            if start_epoch and update.epoch_id < start_epoch:
                continue
            if end_epoch and update.epoch_id > end_epoch:
                continue
            filtered_updates.append(update)
        
        return filtered_updates
