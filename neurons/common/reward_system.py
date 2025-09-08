#!/usr/bin/env python3
"""
TAO20 Multi-Tiered Reward Allocation System

This module implements the sophisticated multi-tiered reward system for TAO20
miners as specified in the implementation plan. It provides both base proportional
rewards and competitive top-miner bonuses to maximize volume generation.

Key Features:
- Base proportional reward distribution
- Top miner bonus tiers with competitive allocation
- Volume-based scoring with mint bonus (1.10x mint, 1.00x redeem)
- Dynamic reward pool management
- Performance incentive alignment
- Transparent reward calculation
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import json
import statistics

import torch
import bittensor as bt

logger = logging.getLogger(__name__)


class RewardTier(Enum):
    """Reward tier classifications"""
    BASE = "base"           # All miners get proportional base rewards
    BRONZE = "bronze"       # Ranks 11-20
    SILVER = "silver"       # Ranks 6-10
    GOLD = "gold"          # Ranks 3-5
    PLATINUM = "platinum"   # Rank 2
    DIAMOND = "diamond"     # Rank 1


@dataclass
class MinerRewardProfile:
    """Individual miner reward profile"""
    miner_address: str
    hotkey_ss58: str
    
    # Performance metrics
    total_volume: int = 0
    mint_volume: int = 0
    redeem_volume: int = 0
    weighted_score: Decimal = Decimal('0')
    
    # Ranking
    rank: int = 0
    tier: RewardTier = RewardTier.BASE
    
    # Reward allocation
    base_reward_share: Decimal = Decimal('0')
    tier_bonus_share: Decimal = Decimal('0')
    total_reward_share: Decimal = Decimal('0')
    
    # Historical performance
    reward_history: List[Dict] = field(default_factory=list)
    average_rank: Decimal = Decimal('0')
    rank_stability: Decimal = Decimal('0')


@dataclass
class RewardPool:
    """Reward pool configuration and state"""
    total_emissions: Decimal
    
    # Pool allocation
    base_pool_percentage: Decimal = Decimal('0.70')      # 70% for base rewards
    tier_bonus_percentage: Decimal = Decimal('0.25')     # 25% for tier bonuses
    validator_pool_percentage: Decimal = Decimal('0.05')  # 5% for validators
    
    # Calculated amounts
    base_pool_amount: Decimal = Decimal('0')
    tier_bonus_amount: Decimal = Decimal('0')
    validator_pool_amount: Decimal = Decimal('0')
    
    # Tier bonus distribution
    diamond_bonus_percentage: Decimal = Decimal('0.40')   # 40% of tier bonus
    platinum_bonus_percentage: Decimal = Decimal('0.25')  # 25% of tier bonus
    gold_bonus_percentage: Decimal = Decimal('0.20')      # 20% of tier bonus
    silver_bonus_percentage: Decimal = Decimal('0.10')    # 10% of tier bonus
    bronze_bonus_percentage: Decimal = Decimal('0.05')    # 5% of tier bonus


@dataclass
class EpochRewardDistribution:
    """Complete epoch reward distribution"""
    epoch_number: int
    timestamp: int
    
    # Pool information
    reward_pool: RewardPool
    
    # Miner rewards
    miner_rewards: List[MinerRewardProfile]
    total_miners: int
    active_miners: int
    
    # Distribution statistics
    gini_coefficient: Decimal
    reward_concentration_top10: Decimal
    average_reward: Decimal
    median_reward: Decimal
    
    # Performance metrics
    total_volume_rewarded: int
    volume_to_reward_ratio: Decimal


class MultiTierRewardSystem:
    """
    Comprehensive multi-tiered reward allocation system
    
    Implements the sophisticated reward mechanism that balances
    proportional fairness with competitive incentives for top performers.
    """
    
    def __init__(self, config: dict):
        self.config = config
        
        # Reward system parameters
        self.mint_bonus_multiplier = Decimal(config.get('mint_bonus_multiplier', '1.10'))
        self.redeem_multiplier = Decimal(config.get('redeem_multiplier', '1.00'))
        
        # Tier configuration
        self.tier_thresholds = {
            RewardTier.DIAMOND: (1, 1),      # Rank 1
            RewardTier.PLATINUM: (2, 2),     # Rank 2
            RewardTier.GOLD: (3, 5),         # Ranks 3-5
            RewardTier.SILVER: (6, 10),      # Ranks 6-10
            RewardTier.BRONZE: (11, 20),     # Ranks 11-20
            RewardTier.BASE: (21, float('inf'))  # All others
        }
        
        # Performance weighting
        self.volume_weight = Decimal(config.get('volume_weight', '0.8'))
        self.consistency_weight = Decimal(config.get('consistency_weight', '0.1'))
        self.frequency_weight = Decimal(config.get('frequency_weight', '0.1'))
        
        # Anti-gaming measures
        self.min_volume_threshold = int(config.get('min_volume_threshold', 1e18))  # 1 TAO minimum
        self.max_reward_concentration = Decimal(config.get('max_reward_concentration', '0.5'))  # 50% max for top 10
        
        # State
        self.current_epoch = 0
        self.reward_distributions: List[EpochRewardDistribution] = []
        
        logger.info("Multi-Tier Reward System initialized")
        logger.info(f"Mint bonus: {self.mint_bonus_multiplier}x, Redeem: {self.redeem_multiplier}x")
        logger.info(f"Tier structure: Diamond(1), Platinum(2), Gold(3-5), Silver(6-10), Bronze(11-20)")
    
    def calculate_weighted_scores(self, miner_data: List[Dict]) -> List[MinerRewardProfile]:
        """Calculate weighted scores for all miners"""
        try:
            miner_profiles = []
            
            for data in miner_data:
                # Extract miner data
                miner_address = data['miner_address']
                hotkey_ss58 = data.get('hotkey_ss58', '')
                mint_volume = data.get('mint_volume', 0)
                redeem_volume = data.get('redeem_volume', 0)
                total_volume = mint_volume + redeem_volume
                
                # Skip miners below minimum threshold
                if total_volume < self.min_volume_threshold:
                    continue
                
                # Calculate weighted score with mint bonus
                weighted_score = (
                    self.mint_bonus_multiplier * Decimal(mint_volume) +
                    self.redeem_multiplier * Decimal(redeem_volume)
                )
                
                # Apply additional performance weights if available
                consistency_score = Decimal(data.get('consistency_score', '1.0'))
                frequency_score = Decimal(data.get('frequency_score', '1.0'))
                
                final_score = (
                    weighted_score * self.volume_weight +
                    weighted_score * consistency_score * self.consistency_weight +
                    weighted_score * frequency_score * self.frequency_weight
                )
                
                # Create miner profile
                profile = MinerRewardProfile(
                    miner_address=miner_address,
                    hotkey_ss58=hotkey_ss58,
                    total_volume=total_volume,
                    mint_volume=mint_volume,
                    redeem_volume=redeem_volume,
                    weighted_score=final_score
                )
                
                miner_profiles.append(profile)
            
            # Sort by weighted score (highest first)
            miner_profiles.sort(key=lambda x: x.weighted_score, reverse=True)
            
            # Assign ranks and tiers
            for i, profile in enumerate(miner_profiles):
                profile.rank = i + 1
                profile.tier = self._determine_tier(profile.rank)
            
            logger.debug(f"Calculated weighted scores for {len(miner_profiles)} miners")
            return miner_profiles
            
        except Exception as e:
            logger.error(f"Error calculating weighted scores: {e}")
            return []
    
    def _determine_tier(self, rank: int) -> RewardTier:
        """Determine reward tier based on rank"""
        for tier, (min_rank, max_rank) in self.tier_thresholds.items():
            if min_rank <= rank <= max_rank:
                return tier
        return RewardTier.BASE
    
    def allocate_rewards(
        self, 
        miner_profiles: List[MinerRewardProfile], 
        total_emissions: Decimal
    ) -> EpochRewardDistribution:
        """Allocate rewards using multi-tiered system"""
        try:
            # Initialize reward pool
            reward_pool = RewardPool(total_emissions=total_emissions)
            self._calculate_pool_amounts(reward_pool)
            
            # Phase 1: Base proportional rewards
            self._allocate_base_rewards(miner_profiles, reward_pool)
            
            # Phase 2: Tier bonus rewards
            self._allocate_tier_bonuses(miner_profiles, reward_pool)
            
            # Phase 3: Calculate final reward shares
            self._calculate_final_rewards(miner_profiles)
            
            # Create distribution record
            distribution = EpochRewardDistribution(
                epoch_number=self.current_epoch,
                timestamp=int(time.time()),
                reward_pool=reward_pool,
                miner_rewards=miner_profiles,
                total_miners=len(miner_profiles),
                active_miners=len([p for p in miner_profiles if p.total_volume > 0]),
                gini_coefficient=self._calculate_gini_coefficient(miner_profiles),
                reward_concentration_top10=self._calculate_top10_concentration(miner_profiles),
                average_reward=self._calculate_average_reward(miner_profiles),
                median_reward=self._calculate_median_reward(miner_profiles),
                total_volume_rewarded=sum(p.total_volume for p in miner_profiles),
                volume_to_reward_ratio=self._calculate_volume_reward_ratio(miner_profiles, total_emissions)
            )
            
            self.reward_distributions.append(distribution)
            self.current_epoch += 1
            
            logger.info(f"Allocated rewards for epoch {self.current_epoch - 1}: "
                       f"{len(miner_profiles)} miners, {total_emissions:.2f} TAO total")
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error allocating rewards: {e}")
            return None
    
    def _calculate_pool_amounts(self, reward_pool: RewardPool):
        """Calculate actual pool amounts from percentages"""
        reward_pool.base_pool_amount = reward_pool.total_emissions * reward_pool.base_pool_percentage
        reward_pool.tier_bonus_amount = reward_pool.total_emissions * reward_pool.tier_bonus_percentage
        reward_pool.validator_pool_amount = reward_pool.total_emissions * reward_pool.validator_pool_percentage
    
    def _allocate_base_rewards(self, miner_profiles: List[MinerRewardProfile], reward_pool: RewardPool):
        """Allocate base proportional rewards"""
        try:
            total_weighted_score = sum(profile.weighted_score for profile in miner_profiles)
            
            if total_weighted_score == 0:
                # Equal distribution if no volume
                base_share = reward_pool.base_pool_amount / len(miner_profiles)
                for profile in miner_profiles:
                    profile.base_reward_share = base_share
            else:
                # Proportional distribution based on weighted scores
                for profile in miner_profiles:
                    proportion = profile.weighted_score / total_weighted_score
                    profile.base_reward_share = reward_pool.base_pool_amount * proportion
            
        except Exception as e:
            logger.error(f"Error allocating base rewards: {e}")
    
    def _allocate_tier_bonuses(self, miner_profiles: List[MinerRewardProfile], reward_pool: RewardPool):
        """Allocate tier-based bonus rewards"""
        try:
            # Group miners by tier
            tier_groups = {tier: [] for tier in RewardTier}
            for profile in miner_profiles:
                tier_groups[profile.tier].append(profile)
            
            # Allocate bonuses by tier
            tier_allocations = {
                RewardTier.DIAMOND: reward_pool.tier_bonus_amount * reward_pool.diamond_bonus_percentage,
                RewardTier.PLATINUM: reward_pool.tier_bonus_amount * reward_pool.platinum_bonus_percentage,
                RewardTier.GOLD: reward_pool.tier_bonus_amount * reward_pool.gold_bonus_percentage,
                RewardTier.SILVER: reward_pool.tier_bonus_amount * reward_pool.silver_bonus_percentage,
                RewardTier.BRONZE: reward_pool.tier_bonus_amount * reward_pool.bronze_bonus_percentage,
                RewardTier.BASE: Decimal('0')  # No bonus for base tier
            }
            
            for tier, tier_amount in tier_allocations.items():
                miners_in_tier = tier_groups[tier]
                if not miners_in_tier or tier_amount == 0:
                    continue
                
                if tier == RewardTier.DIAMOND:
                    # Single winner takes all
                    miners_in_tier[0].tier_bonus_share = tier_amount
                elif tier == RewardTier.PLATINUM:
                    # Single winner takes all
                    miners_in_tier[0].tier_bonus_share = tier_amount
                else:
                    # Distribute within tier based on performance
                    self._distribute_tier_bonus(miners_in_tier, tier_amount)
            
        except Exception as e:
            logger.error(f"Error allocating tier bonuses: {e}")
    
    def _distribute_tier_bonus(self, miners: List[MinerRewardProfile], tier_amount: Decimal):
        """Distribute bonus within a tier"""
        try:
            if not miners:
                return
            
            # Within-tier distribution based on weighted scores
            tier_total_score = sum(miner.weighted_score for miner in miners)
            
            if tier_total_score == 0:
                # Equal distribution within tier
                bonus_per_miner = tier_amount / len(miners)
                for miner in miners:
                    miner.tier_bonus_share = bonus_per_miner
            else:
                # Proportional distribution within tier
                for miner in miners:
                    proportion = miner.weighted_score / tier_total_score
                    miner.tier_bonus_share = tier_amount * proportion
            
        except Exception as e:
            logger.error(f"Error distributing tier bonus: {e}")
    
    def _calculate_final_rewards(self, miner_profiles: List[MinerRewardProfile]):
        """Calculate final reward shares"""
        try:
            for profile in miner_profiles:
                profile.total_reward_share = profile.base_reward_share + profile.tier_bonus_share
            
            # Normalize to ensure total equals 100% (minus validator pool)
            total_miner_rewards = sum(profile.total_reward_share for profile in miner_profiles)
            
            # The remaining should equal base_pool + tier_bonus_pool
            expected_total = sum(profile.base_reward_share for profile in miner_profiles) + \
                           sum(profile.tier_bonus_share for profile in miner_profiles)
            
            if total_miner_rewards > 0 and abs(total_miner_rewards - expected_total) > Decimal('0.001'):
                # Normalize if there's a significant discrepancy
                normalization_factor = expected_total / total_miner_rewards
                for profile in miner_profiles:
                    profile.total_reward_share *= normalization_factor
            
        except Exception as e:
            logger.error(f"Error calculating final rewards: {e}")
    
    def _calculate_gini_coefficient(self, miner_profiles: List[MinerRewardProfile]) -> Decimal:
        """Calculate Gini coefficient for reward inequality"""
        try:
            rewards = [float(profile.total_reward_share) for profile in miner_profiles]
            
            if not rewards or all(r == 0 for r in rewards):
                return Decimal('0')
            
            # Sort rewards
            sorted_rewards = sorted(rewards)
            n = len(sorted_rewards)
            
            # Calculate Gini coefficient
            numerator = sum((i + 1) * reward for i, reward in enumerate(sorted_rewards))
            denominator = n * sum(sorted_rewards)
            
            if denominator == 0:
                return Decimal('0')
            
            gini = Decimal(str((2 * numerator / denominator) - (n + 1) / n))
            return max(Decimal('0'), min(Decimal('1'), gini))
            
        except Exception as e:
            logger.error(f"Error calculating Gini coefficient: {e}")
            return Decimal('0')
    
    def _calculate_top10_concentration(self, miner_profiles: List[MinerRewardProfile]) -> Decimal:
        """Calculate reward concentration in top 10 miners"""
        try:
            if len(miner_profiles) < 10:
                top_miners = miner_profiles
            else:
                top_miners = miner_profiles[:10]
            
            top10_rewards = sum(profile.total_reward_share for profile in top_miners)
            total_rewards = sum(profile.total_reward_share for profile in miner_profiles)
            
            if total_rewards == 0:
                return Decimal('0')
            
            return top10_rewards / total_rewards
            
        except Exception as e:
            logger.error(f"Error calculating top 10 concentration: {e}")
            return Decimal('0')
    
    def _calculate_average_reward(self, miner_profiles: List[MinerRewardProfile]) -> Decimal:
        """Calculate average reward"""
        try:
            if not miner_profiles:
                return Decimal('0')
            
            total_rewards = sum(profile.total_reward_share for profile in miner_profiles)
            return total_rewards / len(miner_profiles)
            
        except Exception as e:
            logger.error(f"Error calculating average reward: {e}")
            return Decimal('0')
    
    def _calculate_median_reward(self, miner_profiles: List[MinerRewardProfile]) -> Decimal:
        """Calculate median reward"""
        try:
            if not miner_profiles:
                return Decimal('0')
            
            rewards = [profile.total_reward_share for profile in miner_profiles]
            rewards.sort()
            
            n = len(rewards)
            if n % 2 == 0:
                median = (rewards[n//2 - 1] + rewards[n//2]) / 2
            else:
                median = rewards[n//2]
            
            return median
            
        except Exception as e:
            logger.error(f"Error calculating median reward: {e}")
            return Decimal('0')
    
    def _calculate_volume_reward_ratio(
        self, 
        miner_profiles: List[MinerRewardProfile], 
        total_emissions: Decimal
    ) -> Decimal:
        """Calculate volume to reward ratio"""
        try:
            total_volume = sum(profile.total_volume for profile in miner_profiles)
            
            if total_volume == 0:
                return Decimal('0')
            
            # Volume in TAO, rewards in TAO
            volume_tao = Decimal(total_volume) / Decimal(1e18)
            return volume_tao / total_emissions
            
        except Exception as e:
            logger.error(f"Error calculating volume reward ratio: {e}")
            return Decimal('0')
    
    def convert_to_bittensor_weights(
        self, 
        distribution: EpochRewardDistribution,
        metagraph: bt.metagraph
    ) -> torch.Tensor:
        """Convert reward distribution to Bittensor weight tensor"""
        try:
            # Initialize weight tensor
            weights = torch.zeros(metagraph.n.item())
            
            # Map miner addresses to UIDs and set weights
            for profile in distribution.miner_rewards:
                # Find UID for this miner (simplified mapping)
                uid = self._find_miner_uid(profile.hotkey_ss58, metagraph)
                if uid is not None and uid < len(weights):
                    weights[uid] = float(profile.total_reward_share)
            
            # Normalize weights to sum to 1.0
            if weights.sum() > 0:
                weights = weights / weights.sum()
            
            return weights
            
        except Exception as e:
            logger.error(f"Error converting to Bittensor weights: {e}")
            return torch.zeros(metagraph.n.item())
    
    def _find_miner_uid(self, hotkey_ss58: str, metagraph: bt.metagraph) -> Optional[int]:
        """Find miner UID from hotkey"""
        try:
            for uid, hotkey in enumerate(metagraph.hotkeys):
                if hotkey == hotkey_ss58:
                    return uid
            return None
        except Exception as e:
            logger.error(f"Error finding miner UID: {e}")
            return None
    
    def get_tier_statistics(self, distribution: EpochRewardDistribution) -> Dict:
        """Get detailed tier statistics"""
        try:
            tier_stats = {tier.value: {
                'count': 0,
                'total_reward': Decimal('0'),
                'total_volume': 0,
                'avg_reward': Decimal('0'),
                'reward_share': Decimal('0')
            } for tier in RewardTier}
            
            total_rewards = sum(profile.total_reward_share for profile in distribution.miner_rewards)
            
            for profile in distribution.miner_rewards:
                tier_key = profile.tier.value
                tier_stats[tier_key]['count'] += 1
                tier_stats[tier_key]['total_reward'] += profile.total_reward_share
                tier_stats[tier_key]['total_volume'] += profile.total_volume
            
            # Calculate averages and shares
            for tier_key, stats in tier_stats.items():
                if stats['count'] > 0:
                    stats['avg_reward'] = stats['total_reward'] / stats['count']
                
                if total_rewards > 0:
                    stats['reward_share'] = stats['total_reward'] / total_rewards
            
            return {
                'tier_breakdown': tier_stats,
                'total_miners': len(distribution.miner_rewards),
                'total_rewards': float(total_rewards),
                'reward_concentration': {
                    'top_1': float(tier_stats['diamond']['reward_share']),
                    'top_2': float(tier_stats['diamond']['reward_share'] + tier_stats['platinum']['reward_share']),
                    'top_10': float(distribution.reward_concentration_top10),
                    'gini_coefficient': float(distribution.gini_coefficient)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting tier statistics: {e}")
            return {}
    
    def analyze_reward_fairness(self, distribution: EpochRewardDistribution) -> Dict:
        """Analyze reward system fairness"""
        try:
            # Volume vs reward correlation
            volumes = [profile.total_volume for profile in distribution.miner_rewards]
            rewards = [float(profile.total_reward_share) for profile in distribution.miner_rewards]
            
            correlation = self._calculate_correlation(volumes, rewards)
            
            # Rank mobility analysis (if we have historical data)
            rank_stability = self._analyze_rank_stability(distribution.miner_rewards)
            
            # Reward efficiency
            efficiency_metrics = self._calculate_efficiency_metrics(distribution)
            
            return {
                'fairness_scores': {
                    'volume_reward_correlation': correlation,
                    'rank_stability': rank_stability,
                    'gini_coefficient': float(distribution.gini_coefficient),
                    'top10_concentration': float(distribution.reward_concentration_top10)
                },
                'efficiency_metrics': efficiency_metrics,
                'system_health': {
                    'active_participation_rate': distribution.active_miners / distribution.total_miners,
                    'volume_per_tao_reward': float(distribution.volume_to_reward_ratio),
                    'tier_distribution_balance': self._assess_tier_balance(distribution)
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing reward fairness: {e}")
            return {}
    
    def _calculate_correlation(self, x: List, y: List) -> float:
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
            
            return numerator / denominator
            
        except Exception as e:
            logger.error(f"Error calculating correlation: {e}")
            return 0.0
    
    def _analyze_rank_stability(self, miner_profiles: List[MinerRewardProfile]) -> float:
        """Analyze rank stability across epochs"""
        try:
            # Simplified rank stability - would need historical data for full analysis
            if len(self.reward_distributions) < 2:
                return 1.0  # Perfect stability if no history
            
            # Compare with previous epoch
            prev_distribution = self.reward_distributions[-2]
            prev_ranks = {profile.miner_address: profile.rank for profile in prev_distribution.miner_rewards}
            
            rank_changes = []
            for profile in miner_profiles:
                prev_rank = prev_ranks.get(profile.miner_address)
                if prev_rank is not None:
                    rank_change = abs(profile.rank - prev_rank)
                    rank_changes.append(rank_change)
            
            if not rank_changes:
                return 1.0
            
            # Calculate stability score (lower average change = higher stability)
            avg_change = statistics.mean(rank_changes)
            max_possible_change = len(miner_profiles)
            stability = max(0.0, 1.0 - (avg_change / max_possible_change))
            
            return stability
            
        except Exception as e:
            logger.error(f"Error analyzing rank stability: {e}")
            return 0.5
    
    def _calculate_efficiency_metrics(self, distribution: EpochRewardDistribution) -> Dict:
        """Calculate reward system efficiency metrics"""
        try:
            return {
                'volume_incentive_efficiency': float(distribution.volume_to_reward_ratio),
                'participation_efficiency': distribution.active_miners / distribution.total_miners,
                'reward_distribution_efficiency': 1.0 - float(distribution.gini_coefficient),
                'tier_utilization': self._calculate_tier_utilization(distribution)
            }
        except Exception as e:
            logger.error(f"Error calculating efficiency metrics: {e}")
            return {}
    
    def _calculate_tier_utilization(self, distribution: EpochRewardDistribution) -> float:
        """Calculate how well tier system is utilized"""
        try:
            tier_counts = {tier: 0 for tier in RewardTier}
            for profile in distribution.miner_rewards:
                tier_counts[profile.tier] += 1
            
            # Ideal would be some miners in each tier
            utilized_tiers = sum(1 for count in tier_counts.values() if count > 0)
            total_tiers = len(RewardTier)
            
            return utilized_tiers / total_tiers
            
        except Exception as e:
            logger.error(f"Error calculating tier utilization: {e}")
            return 0.0
    
    def _assess_tier_balance(self, distribution: EpochRewardDistribution) -> float:
        """Assess balance of tier distribution"""
        try:
            tier_counts = {tier: 0 for tier in RewardTier}
            for profile in distribution.miner_rewards:
                tier_counts[profile.tier] += 1
            
            # Check if distribution follows expected pattern
            # (fewer miners in higher tiers)
            expected_pattern = [
                tier_counts[RewardTier.DIAMOND],
                tier_counts[RewardTier.PLATINUM], 
                tier_counts[RewardTier.GOLD],
                tier_counts[RewardTier.SILVER],
                tier_counts[RewardTier.BRONZE],
                tier_counts[RewardTier.BASE]
            ]
            
            # Simple balance check - higher tiers should have fewer or equal miners
            balance_score = 1.0
            for i in range(len(expected_pattern) - 1):
                if expected_pattern[i] > expected_pattern[i + 1]:
                    balance_score *= 0.8  # Penalty for inverted distribution
            
            return balance_score
            
        except Exception as e:
            logger.error(f"Error assessing tier balance: {e}")
            return 0.5
    
    def export_reward_report(self, distribution: EpochRewardDistribution) -> str:
        """Export comprehensive reward distribution report"""
        try:
            tier_stats = self.get_tier_statistics(distribution)
            fairness_analysis = self.analyze_reward_fairness(distribution)
            
            report_data = {
                'epoch_info': {
                    'epoch_number': distribution.epoch_number,
                    'timestamp': distribution.timestamp,
                    'total_emissions_tao': float(distribution.reward_pool.total_emissions)
                },
                'distribution_summary': {
                    'total_miners': distribution.total_miners,
                    'active_miners': distribution.active_miners,
                    'total_volume_tao': distribution.total_volume_rewarded / 1e18,
                    'volume_to_reward_ratio': float(distribution.volume_to_reward_ratio)
                },
                'reward_pools': {
                    'base_pool_tao': float(distribution.reward_pool.base_pool_amount),
                    'tier_bonus_tao': float(distribution.reward_pool.tier_bonus_amount),
                    'validator_pool_tao': float(distribution.reward_pool.validator_pool_amount)
                },
                'tier_statistics': tier_stats,
                'fairness_analysis': fairness_analysis,
                'top_performers': [
                    {
                        'rank': profile.rank,
                        'miner_address': profile.miner_address,
                        'tier': profile.tier.value,
                        'total_volume_tao': profile.total_volume / 1e18,
                        'weighted_score': float(profile.weighted_score),
                        'total_reward_tao': float(profile.total_reward_share),
                        'base_reward_tao': float(profile.base_reward_share),
                        'tier_bonus_tao': float(profile.tier_bonus_share)
                    }
                    for profile in distribution.miner_rewards[:20]  # Top 20
                ]
            }
            
            return json.dumps(report_data, indent=2)
            
        except Exception as e:
            logger.error(f"Error exporting reward report: {e}")
            return "{}"


def main():
    """Example usage of multi-tier reward system"""
    config = {
        'mint_bonus_multiplier': '1.10',
        'redeem_multiplier': '1.00',
        'volume_weight': '0.8',
        'consistency_weight': '0.1',
        'frequency_weight': '0.1',
        'min_volume_threshold': int(1e18)  # 1 TAO minimum
    }
    
    # Initialize reward system
    reward_system = MultiTierRewardSystem(config)
    
    # Simulate miner data
    import random
    miner_data = []
    
    for i in range(50):
        mint_volume = random.randint(int(0.1 * 1e18), int(100 * 1e18))
        redeem_volume = random.randint(int(0.1 * 1e18), int(80 * 1e18))
        
        miner_data.append({
            'miner_address': f'miner_{i:03d}',
            'hotkey_ss58': f'5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY{i:02d}',
            'mint_volume': mint_volume,
            'redeem_volume': redeem_volume,
            'consistency_score': random.uniform(0.7, 1.0),
            'frequency_score': random.uniform(0.8, 1.0)
        })
    
    # Calculate scores
    miner_profiles = reward_system.calculate_weighted_scores(miner_data)
    
    # Allocate rewards
    total_emissions = Decimal('1000')  # 1000 TAO total
    distribution = reward_system.allocate_rewards(miner_profiles, total_emissions)
    
    # Print results
    print(f"Reward Distribution for Epoch {distribution.epoch_number}")
    print(f"Total Emissions: {total_emissions} TAO")
    print(f"Total Miners: {distribution.total_miners}")
    print(f"Active Miners: {distribution.active_miners}")
    print(f"Gini Coefficient: {distribution.gini_coefficient:.3f}")
    print(f"Top 10 Concentration: {distribution.reward_concentration_top10:.1%}")
    
    print("\nTop 10 Miners:")
    for i, profile in enumerate(distribution.miner_rewards[:10]):
        print(f"{i+1:2d}. {profile.miner_address} ({profile.tier.value.upper()}) - "
              f"Volume: {profile.total_volume/1e18:.1f} TAO - "
              f"Reward: {profile.total_reward_share:.2f} TAO "
              f"(Base: {profile.base_reward_share:.2f} + Bonus: {profile.tier_bonus_share:.2f})")
    
    # Tier statistics
    tier_stats = reward_system.get_tier_statistics(distribution)
    print(f"\nTier Statistics:")
    for tier, stats in tier_stats['tier_breakdown'].items():
        if stats['count'] > 0:
            print(f"{tier.upper()}: {stats['count']} miners, "
                  f"{stats['reward_share']:.1%} of rewards, "
                  f"avg {stats['avg_reward']:.2f} TAO")
    
    # Export report
    report = reward_system.export_reward_report(distribution)
    print(f"\nReport exported: {len(report)} characters")


if __name__ == "__main__":
    main()
