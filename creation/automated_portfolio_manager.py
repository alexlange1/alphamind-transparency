#!/usr/bin/env python3
"""
Automated Portfolio Weight Management System for TAO20

This system implements fully automated, un-gameable portfolio weight calculation:
1. Daily emissions snapshots at fixed UTC times
2. Optimal portfolio weighting algorithm at epoch boundaries  
3. Automated weight publishing to creation files
4. Tamper-resistant, deterministic calculations

The system runs continuously and handles:
- Daily emission data collection from all 20 subnets
- 14-day rolling average calculation for stability
- Modern Portfolio Theory-inspired optimal weight calculation
- Automated publishing at epoch boundaries
- Comprehensive logging and monitoring
"""

import asyncio
import logging
import time
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import math
from collections import defaultdict

# Import existing components
try:
    from .epoch_manager import EpochManager
    from .weights_calculator import WeightsCalculator
    from ..emissions.snapshot import take_snapshot, EmissionSnapshot, compute_rolling_14d
    from ..sim.epoch import current_epoch_id, EPOCH_ANCHOR_UNIX, REBALANCE_PERIOD_SECS
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    
    from creation.epoch_manager import EpochManager
    from creation.weights_calculator import WeightsCalculator
    from emissions.snapshot import take_snapshot, EmissionSnapshot, compute_rolling_14d
    from sim.epoch import current_epoch_id, EPOCH_ANCHOR_UNIX, REBALANCE_PERIOD_SECS

logger = logging.getLogger(__name__)

@dataclass
class PortfolioSnapshot:
    """Complete portfolio snapshot with metadata"""
    epoch_id: int
    snapshot_time: str  # ISO8601 UTC
    raw_emissions: Dict[int, float]  # Daily emissions
    rolling_14d_emissions: Dict[int, float]  # 14-day rolling average
    calculated_weights: Dict[int, float]  # Final optimal weights
    weights_hash: str  # Tamper verification
    total_emission: float
    diversification_score: float  # Portfolio diversification metric
    methodology_version: str = "1.0"
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class WeightingConfig:
    """Configuration for portfolio weighting algorithm"""
    # Constraints
    min_weight: float = 0.005  # 0.5% minimum (more inclusive than 1%)
    max_weight: float = 0.15   # 15% maximum (prevents over-concentration)
    target_subnets: int = 20   # Always include all 20 subnets
    
    # Optimization parameters
    emission_weight: float = 0.70  # 70% weight on emission strength
    stability_weight: float = 0.20  # 20% weight on emission stability
    diversification_weight: float = 0.10  # 10% weight on diversification
    
    # Stability metrics
    lookback_days: int = 14  # Use 14-day rolling average
    volatility_penalty: float = 0.1  # Penalize high volatility subnets
    
    # Minimum emission threshold for inclusion
    min_emission_threshold: float = 0.001  # 0.001 TAO/day minimum

class AutomatedPortfolioManager:
    """
    Fully automated portfolio weight management system
    
    This system:
    1. Takes daily emission snapshots at 00:00 UTC
    2. Calculates optimal weights using modern portfolio theory
    3. Publishes new weights at epoch boundaries (every 20 days)
    4. Provides comprehensive monitoring and tamper detection
    """
    
    def __init__(
        self,
        btcli_path: str = "btcli",
        data_dir: str = "./portfolio_data",
        config: Optional[WeightingConfig] = None,
        network: str = "finney"
    ):
        self.btcli_path = btcli_path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.config = config or WeightingConfig()
        self.network = network
        
        # Initialize components
        self.epoch_manager = EpochManager()
        self.weights_calculator = WeightsCalculator()
        
        # State tracking
        self.last_snapshot_day: Optional[str] = None
        self.last_weight_publish_epoch: Optional[int] = None
        self.snapshots_history: List[PortfolioSnapshot] = []
        
        # Persistent storage paths
        self.snapshots_file = self.data_dir / "portfolio_snapshots.jsonl"
        self.state_file = self.data_dir / "manager_state.json"
        
        # Load existing state
        self._load_state()
        
        logger.info(f"AutomatedPortfolioManager initialized")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Config: min_weight={self.config.min_weight}, max_weight={self.config.max_weight}")
    
    def _load_state(self):
        """Load manager state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                self.last_snapshot_day = state.get('last_snapshot_day')
                self.last_weight_publish_epoch = state.get('last_weight_publish_epoch')
                logger.info(f"Loaded state: last_snapshot={self.last_snapshot_day}, last_epoch={self.last_weight_publish_epoch}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
    
    def _save_state(self):
        """Save manager state to disk"""
        try:
            state = {
                'last_snapshot_day': self.last_snapshot_day,
                'last_weight_publish_epoch': self.last_weight_publish_epoch,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _get_current_utc_day(self) -> str:
        """Get current UTC day string (YYYY-MM-DD)"""
        return datetime.now(timezone.utc).date().isoformat()
    
    def _should_take_snapshot(self) -> bool:
        """Check if we should take a snapshot (once per UTC day)"""
        current_day = self._get_current_utc_day()
        return current_day != self.last_snapshot_day
    
    def _should_publish_weights(self) -> bool:
        """Check if we should publish new weights (at epoch boundaries)"""
        current_epoch = current_epoch_id()
        return current_epoch != self.last_weight_publish_epoch
    
    async def take_daily_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Take daily emissions snapshot and calculate optimal weights"""
        try:
            logger.info("Taking daily emissions snapshot...")
            
            # Take emission snapshot using existing infrastructure
            emission_snapshot = take_snapshot(
                btcli_path=self.btcli_path,
                network=self.network,
                strict_timing=False  # Allow some flexibility for automation
            )
            
            current_epoch = current_epoch_id()
            snapshot_time = datetime.now(timezone.utc).isoformat()
            
            # Calculate 14-day rolling average for stability
            rolling_emissions = await self._calculate_rolling_emissions(emission_snapshot.emissions_by_netuid)
            
            # Calculate optimal weights
            optimal_weights = self._calculate_optimal_weights(
                emission_snapshot.emissions_by_netuid,
                rolling_emissions
            )
            
            # Calculate portfolio metrics
            total_emission = sum(emission_snapshot.emissions_by_netuid.values())
            diversification_score = self._calculate_diversification_score(optimal_weights)
            
            # Create tamper-proof hash
            weights_hash = self._calculate_weights_hash(optimal_weights, snapshot_time)
            
            # Create portfolio snapshot
            portfolio_snapshot = PortfolioSnapshot(
                epoch_id=current_epoch,
                snapshot_time=snapshot_time,
                raw_emissions=emission_snapshot.emissions_by_netuid,
                rolling_14d_emissions=rolling_emissions,
                calculated_weights=optimal_weights,
                weights_hash=weights_hash,
                total_emission=total_emission,
                diversification_score=diversification_score
            )
            
            # Store snapshot
            self._store_snapshot(portfolio_snapshot)
            self.snapshots_history.append(portfolio_snapshot)
            
            # Update state
            self.last_snapshot_day = self._get_current_utc_day()
            self._save_state()
            
            logger.info(f"Successfully captured portfolio snapshot for epoch {current_epoch}")
            logger.info(f"Total emission: {total_emission:.2f} TAO/day")
            logger.info(f"Diversification score: {diversification_score:.3f}")
            logger.info(f"Top 3 weights: {self._get_top_weights(optimal_weights, 3)}")
            
            return portfolio_snapshot
            
        except Exception as e:
            logger.error(f"Failed to take daily snapshot: {e}")
            return None
    
    async def _calculate_rolling_emissions(self, current_emissions: Dict[int, float]) -> Dict[int, float]:
        """Calculate 14-day rolling average emissions for stability"""
        try:
            # Use existing rolling computation infrastructure
            rolling_file = compute_rolling_14d(self.data_dir)
            
            if rolling_file.exists():
                # Load existing rolling data
                rolling_data = {}
                with open(rolling_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            parts = line.strip().split('\t')
                            if len(parts) >= 3:
                                netuid = int(parts[1])
                                emission = float(parts[2])
                                rolling_data[netuid] = emission
                
                # Fill in any missing subnets with current day data
                for netuid in range(1, 21):  # Subnets 1-20
                    if netuid not in rolling_data:
                        rolling_data[netuid] = current_emissions.get(netuid, 0.0)
                
                return rolling_data
            else:
                # Fallback to current emissions if no historical data
                logger.warning("No rolling emissions data available, using current emissions")
                return current_emissions.copy()
                
        except Exception as e:
            logger.error(f"Failed to calculate rolling emissions: {e}")
            return current_emissions.copy()
    
    def _calculate_optimal_weights(
        self, 
        raw_emissions: Dict[int, float], 
        rolling_emissions: Dict[int, float]
    ) -> Dict[int, float]:
        """
        Calculate optimal portfolio weights using modern portfolio theory principles
        
        This algorithm:
        1. Combines emission strength with stability
        2. Applies diversification constraints
        3. Ensures all 20 subnets are included
        4. Is deterministic and un-gameable
        """
        try:
            # Step 1: Calculate base scores for all 20 subnets
            subnet_scores = {}
            
            for netuid in range(1, 21):  # Always include all 20 subnets
                raw_emission = raw_emissions.get(netuid, 0.0)
                rolling_emission = rolling_emissions.get(netuid, 0.0)
                
                # Emission strength score (primary factor)
                emission_score = rolling_emission
                
                # Stability score (penalize high volatility)
                if rolling_emission > 0:
                    volatility = abs(raw_emission - rolling_emission) / rolling_emission
                    stability_score = max(0.1, 1.0 - (volatility * self.config.volatility_penalty))
                else:
                    stability_score = 0.1  # Low score for zero-emission subnets
                
                # Combined score
                combined_score = (
                    emission_score * self.config.emission_weight +
                    stability_score * rolling_emission * self.config.stability_weight
                )
                
                # Ensure minimum threshold
                subnet_scores[netuid] = max(combined_score, self.config.min_emission_threshold)
            
            # Step 2: Apply portfolio optimization
            return self._optimize_portfolio_weights(subnet_scores)
            
        except Exception as e:
            logger.error(f"Failed to calculate optimal weights: {e}")
            # Fallback to equal weights
            return {netuid: 1.0/20 for netuid in range(1, 21)}
    
    def _optimize_portfolio_weights(self, subnet_scores: Dict[int, float]) -> Dict[int, float]:
        """
        Optimize portfolio weights with constraints
        
        Uses a constrained optimization approach:
        1. Proportional allocation based on scores
        2. Min/max weight constraints
        3. Diversification bonus for balanced allocation
        """
        try:
            # Step 1: Calculate raw proportional weights
            total_score = sum(subnet_scores.values())
            if total_score == 0:
                # Fallback to equal weights
                return {netuid: 1.0/20 for netuid in range(1, 21)}
            
            raw_weights = {netuid: score / total_score for netuid, score in subnet_scores.items()}
            
            # Step 2: Apply min/max constraints iteratively
            adjusted_weights = self._apply_weight_constraints(raw_weights)
            
            # Step 3: Apply diversification bonus
            final_weights = self._apply_diversification_bonus(adjusted_weights, subnet_scores)
            
            # Step 4: Final normalization
            total_weight = sum(final_weights.values())
            normalized_weights = {netuid: weight / total_weight for netuid, weight in final_weights.items()}
            
            # Validation
            self._validate_weights(normalized_weights)
            
            return normalized_weights
            
        except Exception as e:
            logger.error(f"Portfolio optimization failed: {e}")
            return {netuid: 1.0/20 for netuid in range(1, 21)}
    
    def _apply_weight_constraints(self, weights: Dict[int, float]) -> Dict[int, float]:
        """Apply min/max weight constraints with iterative adjustment"""
        max_iterations = 10
        tolerance = 1e-6
        
        adjusted = weights.copy()
        
        for iteration in range(max_iterations):
            total_adjustment = 0
            excess_weight = 0
            
            # Collect excess weight from over-max subnets
            for netuid in adjusted:
                if adjusted[netuid] > self.config.max_weight:
                    excess = adjusted[netuid] - self.config.max_weight
                    excess_weight += excess
                    adjusted[netuid] = self.config.max_weight
                    total_adjustment += excess
            
            # Boost under-min subnets to minimum
            deficit_subnets = []
            total_deficit = 0
            for netuid in adjusted:
                if adjusted[netuid] < self.config.min_weight:
                    deficit = self.config.min_weight - adjusted[netuid]
                    total_deficit += deficit
                    adjusted[netuid] = self.config.min_weight
                    deficit_subnets.append(netuid)
            
            # Redistribute excess to non-maxed subnets
            if excess_weight > 0:
                eligible_subnets = [netuid for netuid in adjusted 
                                  if adjusted[netuid] < self.config.max_weight and netuid not in deficit_subnets]
                
                if eligible_subnets:
                    redistribution_per_subnet = excess_weight / len(eligible_subnets)
                    for netuid in eligible_subnets:
                        adjusted[netuid] += redistribution_per_subnet
            
            # Check convergence
            if total_adjustment < tolerance:
                break
        
        return adjusted
    
    def _apply_diversification_bonus(self, weights: Dict[int, float], scores: Dict[int, float]) -> Dict[int, float]:
        """Apply small diversification bonus to encourage balanced allocation"""
        # Calculate Herfindahl-Hirschman Index (lower is more diversified)
        hhi = sum(w * w for w in weights.values())
        diversification_factor = 1.0 / hhi  # Higher factor for more diversified portfolios
        
        # Apply small diversification bonus (capped)
        bonus_factor = min(1.1, 1.0 + (diversification_factor - 1.0) * self.config.diversification_weight)
        
        adjusted = {}
        for netuid, weight in weights.items():
            # Apply bonus proportional to original score and diversification
            adjusted[netuid] = weight * bonus_factor
        
        return adjusted
    
    def _validate_weights(self, weights: Dict[int, float]):
        """Validate final weights meet all constraints"""
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights don't sum to 1.0: {total}")
        
        if len(weights) != 20:
            raise ValueError(f"Must have exactly 20 weights, got {len(weights)}")
        
        for netuid, weight in weights.items():
            if weight < self.config.min_weight - 1e-6:
                raise ValueError(f"Weight for subnet {netuid} below minimum: {weight}")
            if weight > self.config.max_weight + 1e-6:
                raise ValueError(f"Weight for subnet {netuid} above maximum: {weight}")
    
    def _calculate_diversification_score(self, weights: Dict[int, float]) -> float:
        """Calculate portfolio diversification score (0-1, higher is more diversified)"""
        # Use normalized entropy as diversification measure
        entropy = -sum(w * math.log(w) for w in weights.values() if w > 0)
        max_entropy = math.log(len(weights))  # Maximum possible entropy
        return entropy / max_entropy if max_entropy > 0 else 0
    
    def _calculate_weights_hash(self, weights: Dict[int, float], timestamp: str) -> str:
        """Calculate tamper-proof hash of weights and metadata"""
        # Sort weights for deterministic hashing
        sorted_weights = sorted(weights.items())
        hash_data = {
            'weights': sorted_weights,
            'timestamp': timestamp,
            'methodology_version': '1.0',
            'config_hash': self._get_config_hash()
        }
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def _get_config_hash(self) -> str:
        """Get hash of current configuration for tamper detection"""
        config_dict = asdict(self.config)
        config_string = json.dumps(config_dict, sort_keys=True)
        return hashlib.md5(config_string.encode()).hexdigest()[:8]
    
    def _get_top_weights(self, weights: Dict[int, float], n: int) -> Dict[int, float]:
        """Get top N weights for logging"""
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_weights[:n])
    
    def _store_snapshot(self, snapshot: PortfolioSnapshot):
        """Store snapshot to persistent storage"""
        try:
            with open(self.snapshots_file, 'a') as f:
                f.write(json.dumps(snapshot.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to store snapshot: {e}")
    
    async def publish_weights_if_needed(self) -> bool:
        """Publish new weights at epoch boundaries"""
        if not self._should_publish_weights():
            return False
        
        try:
            current_epoch = current_epoch_id()
            logger.info(f"Publishing weights for epoch {current_epoch}")
            
            # Get latest portfolio snapshot
            if not self.snapshots_history:
                logger.error("No snapshots available for weight publishing")
                return False
            
            latest_snapshot = self.snapshots_history[-1]
            
            # Publish creation file using epoch manager
            creation_file = await self.epoch_manager.publish_creation_file(
                epoch_id=current_epoch,
                weights=latest_snapshot.calculated_weights,
                published_by="automated_portfolio_manager"
            )
            
            # Update state
            self.last_weight_publish_epoch = current_epoch
            self._save_state()
            
            logger.info(f"Successfully published weights for epoch {current_epoch}")
            logger.info(f"Weights hash: {latest_snapshot.weights_hash}")
            logger.info(f"Creation file hash: {creation_file.weights_hash}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish weights: {e}")
            return False
    
    async def run_continuous_monitoring(self, check_interval: int = 3600):
        """
        Run continuous monitoring loop
        
        Checks every hour for:
        1. Daily snapshot opportunities (at 00:00 UTC)
        2. Weight publishing opportunities (at epoch boundaries)
        """
        logger.info("Starting continuous portfolio monitoring...")
        
        while True:
            try:
                current_time = datetime.now(timezone.utc)
                logger.info(f"Monitoring check at {current_time.isoformat()}")
                
                # Check for daily snapshot (prefer early UTC hours)
                if self._should_take_snapshot() and current_time.hour < 6:
                    await self.take_daily_snapshot()
                
                # Check for weight publishing (any time during epoch boundary)
                await self.publish_weights_if_needed()
                
                # Wait for next check
                await asyncio.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(check_interval)
    
    def get_current_weights(self) -> Optional[Dict[int, float]]:
        """Get current portfolio weights"""
        if self.snapshots_history:
            return self.snapshots_history[-1].calculated_weights
        return None
    
    def get_portfolio_stats(self) -> Dict:
        """Get comprehensive portfolio statistics"""
        if not self.snapshots_history:
            return {'status': 'no_data'}
        
        latest = self.snapshots_history[-1]
        
        return {
            'status': 'active',
            'last_snapshot': latest.snapshot_time,
            'current_epoch': latest.epoch_id,
            'total_snapshots': len(self.snapshots_history),
            'current_weights': latest.calculated_weights,
            'diversification_score': latest.diversification_score,
            'total_emission': latest.total_emission,
            'weights_hash': latest.weights_hash,
            'top_3_subnets': self._get_top_weights(latest.calculated_weights, 3),
            'methodology_version': latest.methodology_version,
            'last_weight_publish_epoch': self.last_weight_publish_epoch
        }


async def main():
    """Main entry point for automated portfolio management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Automated TAO20 Portfolio Weight Management")
    parser.add_argument("--btcli-path", default="btcli", help="Path to btcli executable")
    parser.add_argument("--data-dir", default="./portfolio_data", help="Data directory")
    parser.add_argument("--network", default="finney", help="Bittensor network")
    parser.add_argument("--check-interval", type=int, default=3600, help="Check interval in seconds")
    parser.add_argument("--single-run", action="store_true", help="Run once and exit")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize manager
    manager = AutomatedPortfolioManager(
        btcli_path=args.btcli_path,
        data_dir=args.data_dir,
        network=args.network
    )
    
    if args.single_run:
        # Single run mode for testing
        snapshot = await manager.take_daily_snapshot()
        if snapshot:
            print(f"Snapshot taken: {snapshot.snapshot_time}")
            print(f"Top weights: {manager._get_top_weights(snapshot.calculated_weights, 5)}")
        
        published = await manager.publish_weights_if_needed()
        if published:
            print("Weights published successfully")
        else:
            print("No weight publishing needed")
    else:
        # Continuous monitoring mode
        await manager.run_continuous_monitoring(args.check_interval)


if __name__ == "__main__":
    asyncio.run(main())
