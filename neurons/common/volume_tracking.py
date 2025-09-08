#!/usr/bin/env python3
"""
TAO20 Volume Tracking and Miner Ranking System

This module implements the comprehensive volume tracking and miner ranking
system for TAO20 validators. It provides transparent, un-gameable scoring
based on transaction volume with multi-tiered reward allocation.

Key Features:
- Real-time volume tracking per miner
- Multi-tiered scoring with mint bonus (1.10x mint, 1.00x redeem)
- Top miner bonus allocation system
- Historical performance tracking
- Transparent ranking algorithms
- Anti-gaming measures
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from collections import defaultdict, deque
import json
import statistics

logger = logging.getLogger(__name__)


@dataclass
class VolumeMetrics:
    """Individual volume metrics for a miner"""
    miner_address: str
    hotkey_ss58: str
    
    # Volume tracking
    total_volume: int = 0
    mint_volume: int = 0
    redeem_volume: int = 0
    epoch_volume: int = 0
    
    # Transaction tracking
    total_transactions: int = 0
    mint_transactions: int = 0
    redeem_transactions: int = 0
    
    # Time-based metrics
    last_activity_timestamp: int = 0
    first_activity_timestamp: int = 0
    active_days: int = 0
    
    # Performance indicators
    average_transaction_size: Decimal = Decimal('0')
    transaction_frequency: Decimal = Decimal('0')  # Transactions per hour
    consistency_score: Decimal = Decimal('0')     # Volume consistency over time
    
    # Historical data (sliding windows)
    hourly_volumes: deque = field(default_factory=lambda: deque(maxlen=24))      # 24 hours
    daily_volumes: deque = field(default_factory=lambda: deque(maxlen=30))       # 30 days
    transaction_timestamps: deque = field(default_factory=lambda: deque(maxlen=1000))  # Last 1000 txs


@dataclass
class RankingResult:
    """Miner ranking result"""
    miner_address: str
    rank: int
    weighted_score: Decimal
    base_reward_weight: Decimal
    bonus_reward_weight: Decimal
    final_reward_weight: Decimal
    performance_breakdown: Dict[str, Decimal]


@dataclass
class EpochSummary:
    """Summary of epoch performance"""
    epoch_number: int
    start_timestamp: int
    end_timestamp: int
    duration_hours: Decimal
    
    # Volume statistics
    total_volume: int
    total_mint_volume: int
    total_redeem_volume: int
    total_transactions: int
    
    # Miner statistics
    active_miners: int
    total_miners: int
    top_miner_address: str
    top_miner_volume: int
    
    # Rankings
    miner_rankings: List[RankingResult]
    reward_distribution: Dict[str, Decimal]


class VolumeTracker:
    """
    Comprehensive volume tracking system for TAO20 miners
    
    Tracks all miner activity, calculates performance metrics,
    and provides transparent ranking algorithms.
    """
    
    def __init__(self, config: dict):
        self.config = config
        
        # Configuration parameters
        self.mint_bonus_multiplier = Decimal(config.get('mint_bonus_multiplier', '1.10'))
        self.redeem_multiplier = Decimal(config.get('redeem_multiplier', '1.00'))
        self.top_miner_count = config.get('top_miner_count', 10)
        self.base_reward_pool = Decimal(config.get('base_reward_pool', '0.8'))
        self.bonus_reward_pool = Decimal(config.get('bonus_reward_pool', '0.2'))
        
        # Performance weights
        self.volume_weight = Decimal(config.get('volume_weight', '0.7'))
        self.frequency_weight = Decimal(config.get('frequency_weight', '0.2'))
        self.consistency_weight = Decimal(config.get('consistency_weight', '0.1'))
        
        # Time windows
        self.epoch_duration = config.get('epoch_duration', 3600)  # 1 hour epochs
        self.activity_window = config.get('activity_window', 86400)  # 24 hours
        
        # State
        self.miner_metrics: Dict[str, VolumeMetrics] = {}
        self.epoch_summaries: List[EpochSummary] = []
        self.current_epoch = 0
        self.epoch_start_time = int(time.time())
        
        # Anti-gaming measures
        self.min_transaction_size = config.get('min_transaction_size', int(0.01 * 1e18))
        self.max_transaction_frequency = config.get('max_transaction_frequency', 10)  # per minute
        self.suspicious_patterns: Dict[str, List] = defaultdict(list)
        
        logger.info("Volume Tracker initialized")
        logger.info(f"Mint bonus: {self.mint_bonus_multiplier}x, Redeem: {self.redeem_multiplier}x")
        logger.info(f"Top miners: {self.top_miner_count}, Base pool: {self.base_reward_pool}")
    
    def record_transaction(
        self,
        miner_address: str,
        hotkey_ss58: str,
        amount: int,
        is_mint: bool,
        timestamp: Optional[int] = None
    ):
        """Record a new transaction"""
        try:
            if timestamp is None:
                timestamp = int(time.time())
            
            # Get or create miner metrics
            if miner_address not in self.miner_metrics:
                self.miner_metrics[miner_address] = VolumeMetrics(
                    miner_address=miner_address,
                    hotkey_ss58=hotkey_ss58,
                    first_activity_timestamp=timestamp
                )
            
            metrics = self.miner_metrics[miner_address]
            
            # Update volume metrics
            metrics.total_volume += amount
            metrics.epoch_volume += amount
            
            if is_mint:
                metrics.mint_volume += amount
                metrics.mint_transactions += 1
            else:
                metrics.redeem_volume += amount
                metrics.redeem_transactions += 1
            
            # Update transaction metrics
            metrics.total_transactions += 1
            metrics.last_activity_timestamp = timestamp
            
            # Add to time-based tracking
            metrics.transaction_timestamps.append(timestamp)
            
            # Update hourly volume (simplified - would need proper time bucketing)
            current_hour = timestamp // 3600
            if not metrics.hourly_volumes or metrics.hourly_volumes[-1][0] != current_hour:
                metrics.hourly_volumes.append((current_hour, amount))
            else:
                # Add to current hour
                hour, volume = metrics.hourly_volumes[-1]
                metrics.hourly_volumes[-1] = (hour, volume + amount)
            
            # Calculate derived metrics
            self._update_derived_metrics(metrics)
            
            # Check for suspicious patterns
            self._check_suspicious_activity(miner_address, amount, timestamp)
            
            logger.debug(f"Recorded transaction: {miner_address[:10]}... "
                        f"{'mint' if is_mint else 'redeem'} {amount/1e18:.2f} TAO")
            
        except Exception as e:
            logger.error(f"Error recording transaction: {e}")
    
    def _update_derived_metrics(self, metrics: VolumeMetrics):
        """Update derived performance metrics"""
        try:
            # Calculate average transaction size
            if metrics.total_transactions > 0:
                metrics.average_transaction_size = Decimal(metrics.total_volume) / Decimal(metrics.total_transactions)
            
            # Calculate transaction frequency (transactions per hour)
            if metrics.transaction_timestamps:
                recent_timestamps = [
                    ts for ts in metrics.transaction_timestamps
                    if int(time.time()) - ts < 3600  # Last hour
                ]
                metrics.transaction_frequency = Decimal(len(recent_timestamps))
            
            # Calculate consistency score based on volume distribution
            if len(metrics.hourly_volumes) >= 2:
                volumes = [volume for _, volume in metrics.hourly_volumes]
                if volumes:
                    # Use coefficient of variation (lower is more consistent)
                    mean_vol = statistics.mean(volumes)
                    if mean_vol > 0:
                        std_vol = statistics.stdev(volumes) if len(volumes) > 1 else 0
                        cv = std_vol / mean_vol
                        # Convert to consistency score (higher is better)
                        metrics.consistency_score = max(Decimal('0'), Decimal('1') - Decimal(str(cv)))
            
        except Exception as e:
            logger.error(f"Error updating derived metrics: {e}")
    
    def _check_suspicious_activity(self, miner_address: str, amount: int, timestamp: int):
        """Check for suspicious activity patterns"""
        try:
            # Check transaction size
            if amount < self.min_transaction_size:
                self.suspicious_patterns[miner_address].append({
                    'type': 'small_transaction',
                    'amount': amount,
                    'timestamp': timestamp
                })
            
            # Check transaction frequency
            metrics = self.miner_metrics[miner_address]
            recent_count = len([
                ts for ts in metrics.transaction_timestamps
                if timestamp - ts < 60  # Last minute
            ])
            
            if recent_count > self.max_transaction_frequency:
                self.suspicious_patterns[miner_address].append({
                    'type': 'high_frequency',
                    'count': recent_count,
                    'timestamp': timestamp
                })
            
            # Cleanup old suspicious patterns
            cutoff = timestamp - 3600  # Keep last hour
            for patterns in self.suspicious_patterns.values():
                patterns[:] = [p for p in patterns if p['timestamp'] > cutoff]
            
        except Exception as e:
            logger.error(f"Error checking suspicious activity: {e}")
    
    def calculate_miner_rankings(self) -> List[RankingResult]:
        """Calculate comprehensive miner rankings"""
        try:
            if not self.miner_metrics:
                return []
            
            ranking_results = []
            
            # Calculate weighted scores for all miners
            for miner_address, metrics in self.miner_metrics.items():
                weighted_score = self._calculate_weighted_score(metrics)
                
                ranking_results.append(RankingResult(
                    miner_address=miner_address,
                    rank=0,  # Will be set after sorting
                    weighted_score=weighted_score,
                    base_reward_weight=Decimal('0'),
                    bonus_reward_weight=Decimal('0'),
                    final_reward_weight=Decimal('0'),
                    performance_breakdown=self._get_performance_breakdown(metrics)
                ))
            
            # Sort by weighted score
            ranking_results.sort(key=lambda x: x.weighted_score, reverse=True)
            
            # Assign ranks
            for i, result in enumerate(ranking_results):
                result.rank = i + 1
            
            # Calculate reward weights
            self._calculate_reward_weights(ranking_results)
            
            logger.debug(f"Calculated rankings for {len(ranking_results)} miners")
            
            return ranking_results
            
        except Exception as e:
            logger.error(f"Error calculating miner rankings: {e}")
            return []
    
    def _calculate_weighted_score(self, metrics: VolumeMetrics) -> Decimal:
        """Calculate weighted score for a miner"""
        try:
            # Base volume score with mint bonus
            volume_score = (
                self.mint_bonus_multiplier * Decimal(metrics.mint_volume) +
                self.redeem_multiplier * Decimal(metrics.redeem_volume)
            )
            
            # Normalize volume score
            max_volume = max(
                (m.mint_volume + m.redeem_volume) for m in self.miner_metrics.values()
            ) if self.miner_metrics else 1
            
            normalized_volume = volume_score / Decimal(max_volume) if max_volume > 0 else Decimal('0')
            
            # Frequency score (normalized)
            max_frequency = max(
                m.transaction_frequency for m in self.miner_metrics.values()
            ) if self.miner_metrics else Decimal('1')
            
            normalized_frequency = metrics.transaction_frequency / max_frequency if max_frequency > 0 else Decimal('0')
            
            # Consistency score (already normalized 0-1)
            normalized_consistency = metrics.consistency_score
            
            # Calculate final weighted score
            final_score = (
                self.volume_weight * normalized_volume +
                self.frequency_weight * normalized_frequency +
                self.consistency_weight * normalized_consistency
            )
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating weighted score: {e}")
            return Decimal('0')
    
    def _get_performance_breakdown(self, metrics: VolumeMetrics) -> Dict[str, Decimal]:
        """Get detailed performance breakdown"""
        try:
            return {
                'total_volume_tao': Decimal(metrics.total_volume) / Decimal(1e18),
                'mint_volume_tao': Decimal(metrics.mint_volume) / Decimal(1e18),
                'redeem_volume_tao': Decimal(metrics.redeem_volume) / Decimal(1e18),
                'total_transactions': Decimal(metrics.total_transactions),
                'average_tx_size_tao': metrics.average_transaction_size / Decimal(1e18),
                'transaction_frequency': metrics.transaction_frequency,
                'consistency_score': metrics.consistency_score,
                'active_hours': Decimal(len(metrics.hourly_volumes)),
                'mint_ratio': (
                    Decimal(metrics.mint_volume) / Decimal(max(metrics.total_volume, 1))
                )
            }
        except Exception as e:
            logger.error(f"Error getting performance breakdown: {e}")
            return {}
    
    def _calculate_reward_weights(self, ranking_results: List[RankingResult]):
        """Calculate multi-tiered reward weights"""
        try:
            if not ranking_results:
                return
            
            total_score = sum(result.weighted_score for result in ranking_results)
            if total_score == 0:
                return
            
            # Phase 1: Base proportional rewards
            for result in ranking_results:
                result.base_reward_weight = (
                    result.weighted_score / total_score * self.base_reward_pool
                )
            
            # Phase 2: Top miner bonuses
            top_miners = ranking_results[:self.top_miner_count]
            
            if top_miners:
                # Define bonus percentages for top ranks
                bonus_percentages = [
                    Decimal('0.50'), Decimal('0.30'), Decimal('0.20'), 
                    Decimal('0.15'), Decimal('0.12'), Decimal('0.10'), 
                    Decimal('0.08'), Decimal('0.06'), Decimal('0.04'), 
                    Decimal('0.02')
                ]
                
                # Calculate bonus distribution
                total_bonus_factor = sum(
                    bonus_percentages[i] for i in range(len(top_miners))
                )
                
                for i, result in enumerate(top_miners):
                    if i < len(bonus_percentages):
                        bonus_factor = bonus_percentages[i] / total_bonus_factor
                        result.bonus_reward_weight = bonus_factor * self.bonus_reward_pool
            
            # Phase 3: Calculate final weights
            for result in ranking_results:
                result.final_reward_weight = (
                    result.base_reward_weight + result.bonus_reward_weight
                )
            
            # Normalize final weights to sum to 1.0
            total_final_weight = sum(result.final_reward_weight for result in ranking_results)
            if total_final_weight > 0:
                for result in ranking_results:
                    result.final_reward_weight /= total_final_weight
            
        except Exception as e:
            logger.error(f"Error calculating reward weights: {e}")
    
    def advance_epoch(self) -> EpochSummary:
        """Advance to next epoch and create summary"""
        try:
            current_time = int(time.time())
            
            # Calculate current epoch summary
            rankings = self.calculate_miner_rankings()
            
            total_volume = sum(metrics.epoch_volume for metrics in self.miner_metrics.values())
            total_mint_volume = sum(metrics.mint_volume for metrics in self.miner_metrics.values())
            total_redeem_volume = sum(metrics.redeem_volume for metrics in self.miner_metrics.values())
            total_transactions = sum(metrics.total_transactions for metrics in self.miner_metrics.values())
            
            active_miners = len([
                metrics for metrics in self.miner_metrics.values()
                if metrics.epoch_volume > 0
            ])
            
            top_miner = rankings[0] if rankings else None
            
            epoch_summary = EpochSummary(
                epoch_number=self.current_epoch,
                start_timestamp=self.epoch_start_time,
                end_timestamp=current_time,
                duration_hours=Decimal(current_time - self.epoch_start_time) / Decimal(3600),
                total_volume=total_volume,
                total_mint_volume=total_mint_volume,
                total_redeem_volume=total_redeem_volume,
                total_transactions=total_transactions,
                active_miners=active_miners,
                total_miners=len(self.miner_metrics),
                top_miner_address=top_miner.miner_address if top_miner else "",
                top_miner_volume=self.miner_metrics[top_miner.miner_address].epoch_volume if top_miner else 0,
                miner_rankings=rankings,
                reward_distribution={
                    result.miner_address: result.final_reward_weight
                    for result in rankings
                }
            )
            
            self.epoch_summaries.append(epoch_summary)
            
            # Keep only recent epochs
            if len(self.epoch_summaries) > 100:
                self.epoch_summaries = self.epoch_summaries[-100:]
            
            # Reset epoch volumes
            for metrics in self.miner_metrics.values():
                metrics.epoch_volume = 0
            
            # Advance epoch
            self.current_epoch += 1
            self.epoch_start_time = current_time
            
            logger.info(f"Epoch {self.current_epoch - 1} completed: "
                       f"{total_volume/1e18:.1f} TAO volume, {active_miners} active miners")
            
            return epoch_summary
            
        except Exception as e:
            logger.error(f"Error advancing epoch: {e}")
            return None
    
    def get_miner_metrics(self, miner_address: Optional[str] = None) -> Dict:
        """Get miner metrics"""
        if miner_address:
            return self.miner_metrics.get(miner_address)
        return self.miner_metrics
    
    def get_epoch_summaries(self, count: Optional[int] = None) -> List[EpochSummary]:
        """Get epoch summaries"""
        if count:
            return self.epoch_summaries[-count:]
        return self.epoch_summaries
    
    def get_suspicious_patterns(self, miner_address: Optional[str] = None) -> Dict:
        """Get suspicious activity patterns"""
        if miner_address:
            return {miner_address: self.suspicious_patterns.get(miner_address, [])}
        return dict(self.suspicious_patterns)
    
    def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        try:
            current_time = int(time.time())
            
            # Calculate active miners
            active_miners = len([
                metrics for metrics in self.miner_metrics.values()
                if current_time - metrics.last_activity_timestamp < self.activity_window
            ])
            
            # Calculate total volumes
            total_volume = sum(metrics.total_volume for metrics in self.miner_metrics.values())
            epoch_volume = sum(metrics.epoch_volume for metrics in self.miner_metrics.values())
            total_transactions = sum(metrics.total_transactions for metrics in self.miner_metrics.values())
            
            # Calculate suspicious activity
            total_suspicious = sum(len(patterns) for patterns in self.suspicious_patterns.values())
            
            return {
                'current_epoch': self.current_epoch,
                'epoch_start_time': self.epoch_start_time,
                'epoch_duration_hours': (current_time - self.epoch_start_time) / 3600,
                'total_miners': len(self.miner_metrics),
                'active_miners': active_miners,
                'total_volume_tao': total_volume / 1e18,
                'epoch_volume_tao': epoch_volume / 1e18,
                'total_transactions': total_transactions,
                'epochs_completed': len(self.epoch_summaries),
                'suspicious_patterns': total_suspicious,
                'config': {
                    'mint_bonus': float(self.mint_bonus_multiplier),
                    'redeem_multiplier': float(self.redeem_multiplier),
                    'top_miner_count': self.top_miner_count,
                    'base_reward_pool': float(self.base_reward_pool),
                    'bonus_reward_pool': float(self.bonus_reward_pool)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def export_rankings_json(self) -> str:
        """Export current rankings as JSON"""
        try:
            rankings = self.calculate_miner_rankings()
            
            export_data = {
                'timestamp': int(time.time()),
                'epoch': self.current_epoch,
                'total_miners': len(rankings),
                'rankings': [
                    {
                        'rank': result.rank,
                        'miner_address': result.miner_address,
                        'weighted_score': float(result.weighted_score),
                        'final_reward_weight': float(result.final_reward_weight),
                        'base_reward': float(result.base_reward_weight),
                        'bonus_reward': float(result.bonus_reward_weight),
                        'performance': {
                            k: float(v) for k, v in result.performance_breakdown.items()
                        }
                    }
                    for result in rankings
                ]
            }
            
            return json.dumps(export_data, indent=2)
            
        except Exception as e:
            logger.error(f"Error exporting rankings: {e}")
            return "{}"


class RankingAnalyzer:
    """
    Analyzer for ranking system performance and fairness
    """
    
    def __init__(self, volume_tracker: VolumeTracker):
        self.volume_tracker = volume_tracker
    
    def analyze_ranking_fairness(self) -> Dict:
        """Analyze ranking system fairness"""
        try:
            rankings = self.volume_tracker.calculate_miner_rankings()
            
            if not rankings:
                return {'error': 'No rankings available'}
            
            # Calculate reward concentration
            top_10_rewards = sum(
                r.final_reward_weight for r in rankings[:10]
            )
            
            # Calculate Gini coefficient for reward distribution
            weights = [float(r.final_reward_weight) for r in rankings]
            gini = self._calculate_gini_coefficient(weights)
            
            # Analyze volume vs reward correlation
            volumes = [float(r.weighted_score) for r in rankings]
            rewards = [float(r.final_reward_weight) for r in rankings]
            correlation = self._calculate_correlation(volumes, rewards)
            
            return {
                'total_miners': len(rankings),
                'top_10_reward_share': float(top_10_rewards),
                'gini_coefficient': gini,
                'volume_reward_correlation': correlation,
                'reward_distribution': {
                    'min': min(weights),
                    'max': max(weights),
                    'mean': statistics.mean(weights),
                    'median': statistics.median(weights)
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing ranking fairness: {e}")
            return {'error': str(e)}
    
    def _calculate_gini_coefficient(self, values: List[float]) -> float:
        """Calculate Gini coefficient for inequality measurement"""
        try:
            if not values or all(v == 0 for v in values):
                return 0.0
            
            sorted_values = sorted(values)
            n = len(sorted_values)
            
            # Calculate Gini coefficient
            numerator = sum(
                (i + 1) * value for i, value in enumerate(sorted_values)
            )
            
            denominator = n * sum(sorted_values)
            
            if denominator == 0:
                return 0.0
            
            gini = (2 * numerator / denominator) - (n + 1) / n
            return max(0.0, min(1.0, gini))
            
        except Exception as e:
            logger.error(f"Error calculating Gini coefficient: {e}")
            return 0.0
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        try:
            if len(x) != len(y) or len(x) < 2:
                return 0.0
            
            mean_x = statistics.mean(x)
            mean_y = statistics.mean(y)
            
            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
            
            sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
            sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)
            
            denominator = (sum_sq_x * sum_sq_y) ** 0.5
            
            if denominator == 0:
                return 0.0
            
            correlation = numerator / denominator
            return max(-1.0, min(1.0, correlation))
            
        except Exception as e:
            logger.error(f"Error calculating correlation: {e}")
            return 0.0


def main():
    """Example usage of volume tracking system"""
    config = {
        'mint_bonus_multiplier': '1.10',
        'redeem_multiplier': '1.00',
        'top_miner_count': 10,
        'base_reward_pool': '0.8',
        'bonus_reward_pool': '0.2',
        'volume_weight': '0.7',
        'frequency_weight': '0.2',
        'consistency_weight': '0.1'
    }
    
    # Initialize tracker
    tracker = VolumeTracker(config)
    
    # Simulate some transactions
    miners = [f"miner_{i}" for i in range(20)]
    
    for i in range(100):
        import random
        miner = random.choice(miners)
        amount = random.randint(int(0.1 * 1e18), int(10 * 1e18))
        is_mint = random.random() > 0.4  # 60% mint, 40% redeem
        
        tracker.record_transaction(miner, f"hotkey_{miner}", amount, is_mint)
    
    # Calculate rankings
    rankings = tracker.calculate_miner_rankings()
    
    print("Top 10 Miners:")
    for i, result in enumerate(rankings[:10]):
        print(f"{i+1:2d}. {result.miner_address} - "
              f"Score: {result.weighted_score:.6f} - "
              f"Weight: {result.final_reward_weight:.4f}")
    
    # Advance epoch
    summary = tracker.advance_epoch()
    print(f"\nEpoch Summary: {summary.total_volume/1e18:.1f} TAO volume")
    
    # Analyze fairness
    analyzer = RankingAnalyzer(tracker)
    fairness = analyzer.analyze_ranking_fairness()
    print(f"Gini Coefficient: {fairness.get('gini_coefficient', 0):.3f}")


if __name__ == "__main__":
    main()
