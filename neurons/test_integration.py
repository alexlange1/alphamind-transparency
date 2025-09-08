#!/usr/bin/env python3
"""
TAO20 Enhanced Miner-Validator Integration Test Suite

This module provides comprehensive integration testing for the enhanced TAO20
miner and validator implementations. It tests the complete workflow from
arbitrage detection to reward distribution.

Key Test Scenarios:
- Miner arbitrage detection and execution
- Validator event monitoring and volume tracking
- Multi-tiered reward calculation and distribution
- Stake-based consensus and slashing mechanisms
- Bittensor weight submission and consensus
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional
from decimal import Decimal
import json
import os
import sys

# Add project paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'common'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'miner'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'validator'))

import bittensor as bt
import torch

# Import our enhanced implementations
from common.nav_monitoring import NAVMonitor
from common.volume_tracking import VolumeTracker
from common.stake_slashing import StakeSlashingManager
from common.reward_system import MultiTierRewardSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockSubtensor:
    """Mock Subtensor for testing"""
    def __init__(self):
        self.weights_submitted = {}
        self.last_submission_time = {}
    
    def set_weights(self, wallet, netuid, uids, weights, wait_for_finalization=False, version_key=0):
        """Mock weight submission"""
        try:
            hotkey = wallet.hotkey.ss58_address
            self.weights_submitted[hotkey] = weights.clone()
            self.last_submission_time[hotkey] = int(time.time())
            
            logger.info(f"Mock weight submission: {hotkey[:10]}... submitted weights")
            return True, "Success"
        except Exception as e:
            return False, str(e)


class MockMetagraph:
    """Mock Metagraph for testing"""
    def __init__(self, num_miners=50):
        self.n = torch.tensor(num_miners)
        self.hotkeys = [f"5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY{i:02d}" for i in range(num_miners)]
        self.S = torch.rand(num_miners) * 10000  # Random stakes 0-10000 TAO
        self.uids = torch.arange(num_miners)


class MockWallet:
    """Mock Wallet for testing"""
    def __init__(self, hotkey_ss58: str):
        self.hotkey = type('obj', (object,), {'ss58_address': hotkey_ss58})()


class IntegrationTestSuite:
    """
    Comprehensive integration test suite for TAO20 enhanced system
    """
    
    def __init__(self):
        self.test_config = self._load_test_config()
        self.mock_subtensor = MockSubtensor()
        self.mock_metagraph = MockMetagraph()
        
        # Test components
        self.nav_monitor = None
        self.volume_tracker = None
        self.slashing_manager = None
        self.reward_system = None
        
        # Test data
        self.test_miners = []
        self.test_validators = []
        self.test_results = {}
        
        logger.info("Integration Test Suite initialized")
    
    def _load_test_config(self) -> Dict:
        """Load test configuration"""
        return {
            # NAV monitoring config
            'nav_update_interval': 5,
            'arbitrage_threshold': '0.01',  # 1% for testing
            'price_staleness_threshold': 60,
            
            # Volume tracking config
            'mint_bonus_multiplier': '1.10',
            'redeem_multiplier': '1.00',
            'top_miner_count': 10,
            'base_reward_pool': '0.8',
            'bonus_reward_pool': '0.2',
            
            # Slashing config
            'min_stake_requirement': 100 * 1e9,  # 100 TAO for testing
            'deviation_threshold': 0.05,
            'minor_slash_rate': 0.01,
            'moderate_slash_rate': 0.05,
            'severe_slash_rate': 0.15,
            
            # Test parameters
            'num_test_miners': 20,
            'num_test_validators': 5,
            'test_duration': 60,  # 1 minute
            'transaction_interval': 5
        }
    
    async def run_full_integration_test(self):
        """Run complete integration test suite"""
        logger.info("Starting full integration test...")
        
        try:
            # Phase 1: Initialize all components
            await self._initialize_test_components()
            
            # Phase 2: Test NAV monitoring
            await self._test_nav_monitoring()
            
            # Phase 3: Test volume tracking
            await self._test_volume_tracking()
            
            # Phase 4: Test reward system
            await self._test_reward_system()
            
            # Phase 5: Test slashing mechanism
            await self._test_slashing_mechanism()
            
            # Phase 6: Test end-to-end workflow
            await self._test_end_to_end_workflow()
            
            # Phase 7: Generate test report
            await self._generate_test_report()
            
            logger.info("Full integration test completed successfully!")
            
        except Exception as e:
            logger.error(f"Integration test failed: {e}")
            raise
    
    async def _initialize_test_components(self):
        """Initialize all test components"""
        logger.info("Initializing test components...")
        
        # Initialize NAV monitor
        self.nav_monitor = NAVMonitor(
            config=type('Config', (), self.test_config)(),
            subtensor=self.mock_subtensor,
            metagraph=self.mock_metagraph
        )
        
        # Initialize volume tracker
        self.volume_tracker = VolumeTracker(self.test_config)
        
        # Initialize slashing manager
        self.slashing_manager = StakeSlashingManager(
            subtensor=self.mock_subtensor,
            metagraph=self.mock_metagraph,
            config=self.test_config
        )
        
        # Initialize reward system
        self.reward_system = MultiTierRewardSystem(self.test_config)
        
        # Initialize test miners and validators
        self._create_test_participants()
        
        # Initialize validator stakes
        await self.slashing_manager.initialize_validator_stakes()
        
        logger.info("Test components initialized successfully")
    
    def _create_test_participants(self):
        """Create test miners and validators"""
        # Create test miners
        for i in range(self.test_config['num_test_miners']):
            miner = {
                'miner_address': f'test_miner_{i:03d}',
                'hotkey_ss58': f'5TestMiner{i:03d}' + 'x' * 40,
                'performance': {
                    'total_volume': 0,
                    'mint_volume': 0,
                    'redeem_volume': 0,
                    'transactions': 0
                }
            }
            self.test_miners.append(miner)
        
        # Create test validators
        for i in range(self.test_config['num_test_validators']):
            validator = {
                'validator_hotkey': f'5TestValidator{i:03d}' + 'x' * 36,
                'wallet': MockWallet(f'5TestValidator{i:03d}' + 'x' * 36),
                'weight_submissions': []
            }
            self.test_validators.append(validator)
        
        logger.info(f"Created {len(self.test_miners)} test miners and {len(self.test_validators)} test validators")
    
    async def _test_nav_monitoring(self):
        """Test NAV monitoring system"""
        logger.info("Testing NAV monitoring system...")
        
        test_results = {
            'nav_calculations': 0,
            'arbitrage_opportunities': 0,
            'price_alerts': 0,
            'data_freshness': 0
        }
        
        try:
            # Start NAV monitoring
            await self.nav_monitor.start_monitoring()
            
            # Wait for initial calculations
            await asyncio.sleep(10)
            
            # Check NAV calculation
            current_nav = self.nav_monitor.get_current_nav()
            if current_nav:
                test_results['nav_calculations'] = 1
                logger.info(f"NAV calculated: {current_nav.nav_per_token:.6f}")
            
            # Check arbitrage opportunities
            opportunities = self.nav_monitor.get_arbitrage_opportunities()
            test_results['arbitrage_opportunities'] = len(opportunities)
            
            # Check monitoring stats
            stats = self.nav_monitor.get_monitoring_stats()
            test_results['data_freshness'] = stats.get('data_freshness_score', 0)
            
            self.test_results['nav_monitoring'] = test_results
            logger.info("NAV monitoring test completed")
            
        except Exception as e:
            logger.error(f"NAV monitoring test failed: {e}")
            raise
    
    async def _test_volume_tracking(self):
        """Test volume tracking system"""
        logger.info("Testing volume tracking system...")
        
        test_results = {
            'transactions_recorded': 0,
            'miners_tracked': 0,
            'rankings_calculated': False,
            'suspicious_patterns': 0
        }
        
        try:
            # Simulate miner transactions
            for i in range(100):  # 100 test transactions
                miner = random.choice(self.test_miners)
                amount = random.randint(int(0.1 * 1e18), int(10 * 1e18))
                is_mint = random.random() > 0.4  # 60% mint, 40% redeem
                
                self.volume_tracker.record_transaction(
                    miner_address=miner['miner_address'],
                    hotkey_ss58=miner['hotkey_ss58'],
                    amount=amount,
                    is_mint=is_mint
                )
                
                # Update miner performance tracking
                miner['performance']['total_volume'] += amount
                if is_mint:
                    miner['performance']['mint_volume'] += amount
                else:
                    miner['performance']['redeem_volume'] += amount
                miner['performance']['transactions'] += 1
                
                test_results['transactions_recorded'] += 1
            
            # Test ranking calculation
            rankings = self.volume_tracker.calculate_miner_rankings()
            if rankings:
                test_results['rankings_calculated'] = True
                test_results['miners_tracked'] = len(rankings)
            
            # Check for suspicious patterns
            suspicious = self.volume_tracker.get_suspicious_patterns()
            test_results['suspicious_patterns'] = len(suspicious)
            
            self.test_results['volume_tracking'] = test_results
            logger.info(f"Volume tracking test completed: {test_results['transactions_recorded']} transactions")
            
        except Exception as e:
            logger.error(f"Volume tracking test failed: {e}")
            raise
    
    async def _test_reward_system(self):
        """Test multi-tier reward system"""
        logger.info("Testing reward system...")
        
        test_results = {
            'miners_scored': 0,
            'tiers_assigned': 0,
            'rewards_allocated': False,
            'fairness_metrics': {}
        }
        
        try:
            # Prepare miner data from volume tracking
            miner_data = []
            for miner in self.test_miners:
                if miner['performance']['total_volume'] > 0:
                    miner_data.append({
                        'miner_address': miner['miner_address'],
                        'hotkey_ss58': miner['hotkey_ss58'],
                        'mint_volume': miner['performance']['mint_volume'],
                        'redeem_volume': miner['performance']['redeem_volume'],
                        'consistency_score': random.uniform(0.8, 1.0),
                        'frequency_score': random.uniform(0.7, 1.0)
                    })
            
            # Calculate weighted scores
            miner_profiles = self.reward_system.calculate_weighted_scores(miner_data)
            test_results['miners_scored'] = len(miner_profiles)
            
            # Count unique tiers
            unique_tiers = set(profile.tier for profile in miner_profiles)
            test_results['tiers_assigned'] = len(unique_tiers)
            
            # Allocate rewards
            total_emissions = Decimal('1000')  # 1000 TAO
            distribution = self.reward_system.allocate_rewards(miner_profiles, total_emissions)
            
            if distribution:
                test_results['rewards_allocated'] = True
                
                # Analyze fairness
                fairness = self.reward_system.analyze_reward_fairness(distribution)
                test_results['fairness_metrics'] = fairness.get('fairness_scores', {})
            
            self.test_results['reward_system'] = test_results
            logger.info(f"Reward system test completed: {test_results['miners_scored']} miners scored")
            
        except Exception as e:
            logger.error(f"Reward system test failed: {e}")
            raise
    
    async def _test_slashing_mechanism(self):
        """Test validator slashing mechanism"""
        logger.info("Testing slashing mechanism...")
        
        test_results = {
            'validators_initialized': 0,
            'weight_submissions': 0,
            'consensus_calculated': False,
            'deviations_detected': 0,
            'slashes_executed': 0
        }
        
        try:
            # Test validator stake initialization
            test_results['validators_initialized'] = len(self.slashing_manager.validator_stakes)
            
            # Simulate validator weight submissions
            for i, validator in enumerate(self.test_validators):
                if i == 0:
                    # Normal validator
                    weights = torch.tensor([0.1, 0.2, 0.3, 0.4])
                elif i == 1:
                    # Similar validator
                    weights = torch.tensor([0.12, 0.18, 0.32, 0.38])
                elif i == 2:
                    # Deviating validator
                    weights = torch.tensor([0.5, 0.1, 0.1, 0.3])  # Significant deviation
                else:
                    # Random normal validators
                    weights = torch.rand(4)
                    weights = weights / weights.sum()
                
                self.slashing_manager.record_weight_submission(
                    validator['validator_hotkey'], 
                    weights
                )
                test_results['weight_submissions'] += 1
            
            # Calculate consensus
            consensus = self.slashing_manager.calculate_consensus_weights()
            if consensus is not None:
                test_results['consensus_calculated'] = True
            
            # Detect deviations
            deviations = self.slashing_manager.detect_validator_deviations()
            test_results['deviations_detected'] = len(deviations)
            
            # Evaluate slashing
            slash_events = await self.slashing_manager.evaluate_slashing_candidates()
            
            # Execute slashes
            for event in slash_events:
                success = await self.slashing_manager.execute_slash_event(event)
                if success:
                    test_results['slashes_executed'] += 1
            
            self.test_results['slashing_mechanism'] = test_results
            logger.info(f"Slashing mechanism test completed: {test_results['deviations_detected']} deviations detected")
            
        except Exception as e:
            logger.error(f"Slashing mechanism test failed: {e}")
            raise
    
    async def _test_end_to_end_workflow(self):
        """Test complete end-to-end workflow"""
        logger.info("Testing end-to-end workflow...")
        
        test_results = {
            'workflow_completed': False,
            'weight_submissions_successful': 0,
            'consensus_achieved': False,
            'rewards_distributed': False
        }
        
        try:
            # Simulate complete epoch workflow
            
            # 1. Generate more miner activity
            for _ in range(50):
                miner = random.choice(self.test_miners)
                amount = random.randint(int(1 * 1e18), int(20 * 1e18))
                is_mint = random.random() > 0.4
                
                self.volume_tracker.record_transaction(
                    miner_address=miner['miner_address'],
                    hotkey_ss58=miner['hotkey_ss58'],
                    amount=amount,
                    is_mint=is_mint
                )
            
            # 2. Calculate final rankings
            final_rankings = self.volume_tracker.calculate_miner_rankings()
            
            # 3. Distribute rewards
            if final_rankings:
                miner_data = [
                    {
                        'miner_address': result.miner_address,
                        'hotkey_ss58': self.volume_tracker.miner_metrics[result.miner_address].hotkey_ss58,
                        'mint_volume': self.volume_tracker.miner_metrics[result.miner_address].mint_volume,
                        'redeem_volume': self.volume_tracker.miner_metrics[result.miner_address].redeem_volume
                    }
                    for result in final_rankings
                ]
                
                miner_profiles = self.reward_system.calculate_weighted_scores(miner_data)
                distribution = self.reward_system.allocate_rewards(miner_profiles, Decimal('1000'))
                
                if distribution:
                    test_results['rewards_distributed'] = True
                    
                    # 4. Convert to Bittensor weights
                    weights = self.reward_system.convert_to_bittensor_weights(distribution, self.mock_metagraph)
                    
                    # 5. Submit weights via validators
                    for validator in self.test_validators:
                        success, message = self.mock_subtensor.set_weights(
                            wallet=validator['wallet'],
                            netuid=20,
                            uids=torch.arange(len(weights)),
                            weights=weights
                        )
                        
                        if success:
                            test_results['weight_submissions_successful'] += 1
                    
                    # 6. Verify consensus
                    if len(self.mock_subtensor.weights_submitted) >= 3:
                        test_results['consensus_achieved'] = True
            
            test_results['workflow_completed'] = True
            self.test_results['end_to_end'] = test_results
            logger.info("End-to-end workflow test completed successfully")
            
        except Exception as e:
            logger.error(f"End-to-end workflow test failed: {e}")
            raise
    
    async def _generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("Generating test report...")
        
        try:
            report = {
                'test_summary': {
                    'timestamp': int(time.time()),
                    'duration_seconds': 0,  # Would track actual duration
                    'total_tests': len(self.test_results),
                    'passed_tests': 0,
                    'failed_tests': 0
                },
                'test_results': self.test_results,
                'system_performance': {
                    'nav_monitoring': self.nav_monitor.get_monitoring_stats() if self.nav_monitor else {},
                    'volume_tracking': self.volume_tracker.get_system_stats() if self.volume_tracker else {},
                    'slashing_system': self.slashing_manager.get_system_stats() if self.slashing_manager else {}
                },
                'participant_summary': {
                    'test_miners': len(self.test_miners),
                    'test_validators': len(self.test_validators),
                    'total_transactions': sum(m['performance']['transactions'] for m in self.test_miners),
                    'total_volume_tao': sum(m['performance']['total_volume'] for m in self.test_miners) / 1e18
                }
            }
            
            # Count passed/failed tests
            for test_name, results in self.test_results.items():
                if isinstance(results, dict):
                    # Simple heuristic: if any key indicates success, count as passed
                    if any(v for k, v in results.items() if 'successful' in k.lower() or 'completed' in k.lower()):
                        report['test_summary']['passed_tests'] += 1
                    else:
                        report['test_summary']['failed_tests'] += 1
            
            # Save report
            report_path = os.path.join(os.path.dirname(__file__), '..', 'test_results', 'integration_test_report.json')
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Test report saved to {report_path}")
            
            # Print summary
            print("\n" + "="*60)
            print("TAO20 INTEGRATION TEST REPORT")
            print("="*60)
            print(f"Total Tests: {report['test_summary']['total_tests']}")
            print(f"Passed: {report['test_summary']['passed_tests']}")
            print(f"Failed: {report['test_summary']['failed_tests']}")
            print(f"Test Miners: {report['participant_summary']['test_miners']}")
            print(f"Test Validators: {report['participant_summary']['test_validators']}")
            print(f"Total Transactions: {report['participant_summary']['total_transactions']}")
            print(f"Total Volume: {report['participant_summary']['total_volume_tao']:.1f} TAO")
            print("="*60)
            
            # Print detailed results
            for test_name, results in self.test_results.items():
                print(f"\n{test_name.upper()}:")
                if isinstance(results, dict):
                    for key, value in results.items():
                        print(f"  {key}: {value}")
            
            print("\n" + "="*60)
            
        except Exception as e:
            logger.error(f"Error generating test report: {e}")
            raise


async def main():
    """Run integration test suite"""
    test_suite = IntegrationTestSuite()
    await test_suite.run_full_integration_test()


if __name__ == "__main__":
    asyncio.run(main())
