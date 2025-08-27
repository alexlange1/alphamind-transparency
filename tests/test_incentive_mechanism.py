#!/usr/bin/env python3
"""
Test the sophisticated incentive mechanism for TAO20 miners and validators
"""

import pytest
import time
from unittest.mock import Mock, patch

from neurons.validator.incentive_manager import IncentiveManager, VolumeType, VolumeRecord

class TestIncentiveMechanism:
    """Test the incentive mechanism for miners and validators"""
    
    @pytest.fixture
    def incentive_manager(self):
        """Create incentive manager for testing"""
        return IncentiveManager(
            total_emissions_per_epoch=1000000000000000000000,  # 1000 TAO
            miner_emissions_share=0.41,  # 41% to miners
            validator_emissions_share=0.41,  # 41% to validators
            mint_multiplier=1.10,  # 10% bonus for minting
            gas_compensation_bps=50,  # 0.5% gas compensation
            min_volume_threshold=1000000000000000000  # 1 TAO minimum
        )
    
    def test_tier_system(self, incentive_manager):
        """Test the tier system for volume-based rewards"""
        # Test different volume levels and their tiers
        test_cases = [
            (5000000000000000000, 1.0, "Bronze"),    # 5 TAO (< 10 TAO)
            (20000000000000000000, 1.2, "Silver"),   # 20 TAO (< 50 TAO)
            (60000000000000000000, 1.5, "Gold"),     # 60 TAO (< 100 TAO)
            (200000000000000000000, 2.0, "Platinum"), # 200 TAO (< 500 TAO)
            (800000000000000000000, 3.0, "Diamond"), # 800 TAO (>= 500 TAO)
            (2000000000000000000000, 3.0, "Diamond") # 2000 TAO (>= 500 TAO)
        ]
        
        for volume, expected_multiplier, expected_tier in test_cases:
            multiplier = incentive_manager._get_tier_multiplier(volume)
            tier_name = incentive_manager._get_tier_name(multiplier)
            
            assert multiplier == expected_multiplier, f"Volume {volume} should have multiplier {expected_multiplier}"
            assert tier_name == expected_tier, f"Volume {volume} should be {expected_tier} tier"
    
    def test_volume_recording(self, incentive_manager):
        """Test recording volume for miners"""
        miner_ss58 = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        volume_amount = 100000000000000000000  # 100 TAO
        
        # Record minting volume
        incentive_manager.record_volume(
            miner_ss58=miner_ss58,
            volume_type=VolumeType.MINT,
            volume_amount=volume_amount,
            creation_id="creation123",
            nav_at_time=1000000000000000000,  # 1 TAO NAV
            gas_cost=1000000000000000000  # 1 TAO gas
        )
        
        # Record redemption volume
        incentive_manager.record_volume(
            miner_ss58=miner_ss58,
            volume_type=VolumeType.REDEEM,
            volume_amount=volume_amount // 2,  # 50 TAO
            creation_id="creation124",
            nav_at_time=1000000000000000000,
            gas_cost=500000000000000000  # 0.5 TAO gas
        )
        
        # Check volume tracking
        volumes = incentive_manager.miner_volumes[miner_ss58]
        assert volumes[VolumeType.MINT] == volume_amount
        assert volumes[VolumeType.REDEEM] == volume_amount // 2
        assert len(incentive_manager.volume_records) == 2
    
    def test_miner_reward_calculation(self, incentive_manager):
        """Test miner reward calculation with multiple miners"""
        # Create multiple miners with different volumes
        miners = [
            ("miner1", 1000000000000000000000, 0.8, 0.2),   # 1000 TAO total, 80% mint, 20% redeem
            ("miner2", 500000000000000000000, 0.6, 0.4),    # 500 TAO total, 60% mint, 40% redeem
            ("miner3", 100000000000000000000, 0.9, 0.1),    # 100 TAO total, 90% mint, 10% redeem
        ]
        
        # Record volumes for each miner
        for miner_ss58, total_volume, mint_ratio, redeem_ratio in miners:
            mint_volume = int(total_volume * mint_ratio)
            redeem_volume = int(total_volume * redeem_ratio)
            
            if mint_volume > 0:
                incentive_manager.record_volume(
                    miner_ss58=miner_ss58,
                    volume_type=VolumeType.MINT,
                    volume_amount=mint_volume,
                    creation_id=f"creation_{miner_ss58}_mint",
                    nav_at_time=1000000000000000000,
                    gas_cost=mint_volume // 1000
                )
            
            if redeem_volume > 0:
                incentive_manager.record_volume(
                    miner_ss58=miner_ss58,
                    volume_type=VolumeType.REDEEM,
                    volume_amount=redeem_volume,
                    creation_id=f"creation_{miner_ss58}_redeem",
                    nav_at_time=1000000000000000000,
                    gas_cost=redeem_volume // 1000
                )
        
        # Calculate rewards
        rewards = incentive_manager.calculate_miner_rewards()
        
        # Verify we have 3 rewards
        assert len(rewards) == 3
        
        # Verify ranking (should be by total volume)
        assert rewards[0].miner_ss58 == "miner1"  # Highest volume
        assert rewards[1].miner_ss58 == "miner2"  # Medium volume
        assert rewards[2].miner_ss58 == "miner3"  # Lowest volume
        
        # Verify tier multipliers
        assert rewards[0].tier_multiplier == 3.0  # Diamond tier (1000+ TAO)
        assert rewards[1].tier_multiplier == 3.0  # Diamond tier (500+ TAO, but 500 is the threshold for Diamond)
        assert rewards[2].tier_multiplier == 2.0  # Platinum tier (100 TAO is Platinum)
        
        # Verify minting bonuses (10% multiplier)
        for reward in rewards:
            mint_ratio = reward.mint_volume / reward.total_volume
            expected_mint_bonus = int(reward.base_reward * mint_ratio * 0.10)  # 10% of base reward
            assert abs(reward.mint_bonus - expected_mint_bonus) < 1000000000000000  # Allow small rounding differences
        
        # Verify total rewards are positive and reasonable
        total_emissions = incentive_manager.total_emissions_per_epoch * incentive_manager.miner_emissions_share
        total_rewards = sum(reward.total_reward for reward in rewards)
        
        assert total_rewards > 0
        assert total_rewards <= total_emissions * 3.5  # Allow for tier bonuses (Diamond = 3x) + gas compensation
    
    def test_validator_reward_calculation(self, incentive_manager):
        """Test validator reward calculation"""
        validator_ss58 = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        stake_amount = 2000000000000000000000  # 2000 TAO stake
        
        # Record multiple attestations with different accuracy scores
        for i in range(10):
            accuracy_score = 0.8 + (i * 0.02)  # 0.8 to 0.98
            incentive_manager.record_validator_attestation(
                validator_ss58=validator_ss58,
                accuracy_score=accuracy_score,
                stake_amount=stake_amount
            )
        
        # Calculate rewards
        rewards = incentive_manager.calculate_validator_rewards()
        
        # Verify we have 1 validator reward
        assert len(rewards) == 1
        reward = rewards[0]
        
        # Verify attestation count
        assert reward.attestations_provided == 10
        
        # Verify accuracy score (should be average of all scores)
        expected_accuracy = sum(0.8 + (i * 0.02) for i in range(10)) / 10
        assert abs(reward.accuracy_score - expected_accuracy) < 0.01
        
        # Verify stake amount
        assert reward.stake_amount == stake_amount
        
        # Verify rewards are positive
        assert reward.base_reward > 0
        assert reward.accuracy_bonus > 0
        assert reward.stake_bonus > 0
        assert reward.total_reward > 0
    
    def test_leaderboard_functionality(self, incentive_manager):
        """Test leaderboard functionality"""
        # Add some test data
        test_miners = [
            ("miner1", 1000000000000000000000),  # 1000 TAO
            ("miner2", 500000000000000000000),   # 500 TAO
            ("miner3", 100000000000000000000),   # 100 TAO
            ("miner4", 50),                      # Below threshold
        ]
        
        for miner_ss58, volume in test_miners:
            if volume >= incentive_manager.min_volume_threshold:
                incentive_manager.record_volume(
                    miner_ss58=miner_ss58,
                    volume_type=VolumeType.MINT,
                    volume_amount=volume,
                    creation_id=f"creation_{miner_ss58}",
                    nav_at_time=1000000000000000000,
                    gas_cost=volume // 1000
                )
        
        # Get leaderboard
        leaderboard = incentive_manager.get_leaderboard()
        
        # Verify structure
        assert 'leaderboard' in leaderboard
        assert 'total_miners' in leaderboard
        assert 'epoch_start' in leaderboard
        assert 'epoch_end' in leaderboard
        
        # Verify we have 3 miners (miner4 is below threshold)
        assert leaderboard['total_miners'] == 3
        
        # Verify leaderboard entries
        lb_entries = leaderboard['leaderboard']
        assert len(lb_entries) == 3  # Top 3 miners
        
        # Verify ranking
        assert lb_entries[0]['rank'] == 1
        assert lb_entries[0]['miner_ss58'] == "miner1"
        assert lb_entries[1]['rank'] == 2
        assert lb_entries[1]['miner_ss58'] == "miner2"
        assert lb_entries[2]['rank'] == 3
        assert lb_entries[2]['miner_ss58'] == "miner3"
        
        # Verify tier information
        assert lb_entries[0]['tier_name'] == "Diamond"
        assert lb_entries[0]['tier_multiplier'] == 3.0
        assert lb_entries[1]['tier_name'] == "Diamond"  # 500 TAO is Diamond tier
        assert lb_entries[1]['tier_multiplier'] == 3.0
        assert lb_entries[2]['tier_name'] == "Platinum"
        assert lb_entries[2]['tier_multiplier'] == 2.0
    
    def test_miner_stats(self, incentive_manager):
        """Test miner statistics calculation"""
        miner_ss58 = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        
        # Record mixed volume
        incentive_manager.record_volume(
            miner_ss58=miner_ss58,
            volume_type=VolumeType.MINT,
            volume_amount=800000000000000000000,  # 800 TAO mint
            creation_id="creation_mint",
            nav_at_time=1000000000000000000,
            gas_cost=800000000000000000000 // 1000
        )
        
        incentive_manager.record_volume(
            miner_ss58=miner_ss58,
            volume_type=VolumeType.REDEEM,
            volume_amount=200000000000000000000,  # 200 TAO redeem
            creation_id="creation_redeem",
            nav_at_time=1000000000000000000,
            gas_cost=200000000000000000000 // 1000
        )
        
        # Get stats
        stats = incentive_manager.get_miner_stats(miner_ss58)
        
        # Verify stats
        assert stats['miner_ss58'] == miner_ss58
        assert stats['total_volume'] == 1000000000000000000000  # 1000 TAO
        assert stats['mint_volume'] == 800000000000000000000   # 800 TAO
        assert stats['redeem_volume'] == 200000000000000000000 # 200 TAO
        assert stats['mint_ratio'] == 0.8  # 80% mint
        assert stats['redeem_ratio'] == 0.2  # 20% redeem
        assert stats['tier_name'] == "Diamond"
        assert stats['tier_multiplier'] == 3.0
        
        # Calculate effective multiplier: tier_multiplier * (1 + mint_ratio * (mint_multiplier - 1))
        # 3.0 * (1 + 0.8 * 0.1) = 3.0 * 1.08 = 3.24
        expected_effective = 3.0 * (1 + 0.8 * 0.1)
        assert abs(stats['effective_multiplier'] - expected_effective) < 0.01
    
    def test_epoch_management(self, incentive_manager):
        """Test epoch management functionality"""
        # Record some data
        incentive_manager.record_volume(
            miner_ss58="test_miner",
            volume_type=VolumeType.MINT,
            volume_amount=100000000000000000000,
            creation_id="test_creation",
            nav_at_time=1000000000000000000,
            gas_cost=100000000000000000000 // 1000
        )
        
        # Verify data exists
        assert len(incentive_manager.volume_records) > 0
        assert len(incentive_manager.miner_volumes) > 0
        
        # Reset epoch
        incentive_manager.reset_epoch()
        
        # Verify data is cleared
        assert len(incentive_manager.volume_records) == 0
        assert len(incentive_manager.miner_volumes) == 0
        assert len(incentive_manager.validator_attestations) == 0
        assert len(incentive_manager.validator_accuracy) == 0
        
        # Verify epoch start time is updated
        assert incentive_manager.epoch_start_time > 0
    
    def test_epoch_progress(self, incentive_manager):
        """Test epoch progress calculation"""
        # Get initial progress
        initial_progress = incentive_manager.get_epoch_progress()
        assert 0 <= initial_progress <= 1
        
        # Simulate time passing
        with patch('time.time') as mock_time:
            mock_time.return_value = incentive_manager.epoch_start_time + incentive_manager.epoch_duration // 2
            mid_progress = incentive_manager.get_epoch_progress()
            assert abs(mid_progress - 0.5) < 0.01
            
            # Test end of epoch
            mock_time.return_value = incentive_manager.epoch_start_time + incentive_manager.epoch_duration
            end_progress = incentive_manager.get_epoch_progress()
            assert abs(end_progress - 1.0) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
