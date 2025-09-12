#!/usr/bin/env python3
"""
Simple TAO20 Validator
Only scores and ranks miners - no NAV calculations
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from decimal import Decimal

import bittensor as bt
import torch
from aiohttp import web

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ValidatorConfig:
    """Simple validator configuration"""
    wallet_name: str
    wallet_hotkey: str
    wallet_path: str = "~/.bittensor/wallets"
    
    # Validator settings
    netuid: int = 20
    api_port: int = 8093
    scoring_interval: int = 300  # Score miners every 5 minutes
    
    # Scoring parameters
    min_stake_threshold: Decimal = Decimal("1000.0")  # Minimum stake to be active

@dataclass
class MinerPerformance:
    """Miner performance metrics"""
    miner_uid: int
    hotkey: str
    
    # Volume metrics
    total_volume: Decimal = Decimal("0")
    successful_operations: int = 0
    failed_operations: int = 0
    
    # Speed metrics
    avg_response_time: float = 0.0
    uptime_percentage: float = 0.0
    
    # Quality metrics
    accuracy_rate: float = 0.0
    fee_competitiveness: float = 0.0
    
    # Time tracking
    last_activity: int = 0
    evaluation_period: int = 86400  # 24 hours

class SimpleTAO20Validator:
    """
    Simple TAO20 Validator
    
    Responsibilities:
    1. Score miners based on performance metrics
    2. Rank miners for reward distribution
    3. Submit weights to Bittensor network
    4. Provide API for miner performance data
    
    NOT responsible for:
    - NAV calculations (automated)
    - Consensus mechanisms
    - Smart contract interactions
    - Complex monitoring
    """
    
    def __init__(self, config: ValidatorConfig):
        self.config = config
        self.running = False
        
        # Initialize Bittensor
        self.wallet = bt.wallet(
            name=config.wallet_name,
            hotkey=config.wallet_hotkey,
            path=config.wallet_path
        )
        self.subtensor = bt.subtensor()
        self.metagraph = self.subtensor.metagraph(netuid=config.netuid)
        
        # Miner tracking
        self.miner_performances: Dict[int, MinerPerformance] = {}
        self.current_scores: torch.Tensor = torch.zeros(self.metagraph.n)
        
        # API server
        self.app = web.Application()
        self._setup_api_routes()
        
        logger.info(f"Simple TAO20 Validator initialized")
        logger.info(f"Validator hotkey: {self.wallet.hotkey.ss58_address}")
        logger.info(f"Monitoring {self.metagraph.n} neurons")
    
    # ===================== MAIN VALIDATOR LOOP =====================
    
    async def run(self):
        """Main validator loop - focused on scoring"""
        logger.info("Starting simple TAO20 validator...")
        self.running = True
        
        # Start API server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.config.api_port)
        await site.start()
        logger.info(f"API server started on port {self.config.api_port}")
        
        try:
            while self.running:
                try:
                    # Update metagraph
                    self.metagraph.sync(subtensor=self.subtensor)
                    
                    # Collect miner performance data
                    await self._collect_miner_data()
                    
                    # Score miners based on performance
                    await self._score_miners()
                    
                    # Submit weights to network
                    await self._submit_weights()
                    
                    # Wait before next scoring cycle
                    await asyncio.sleep(self.config.scoring_interval)
                    
                except KeyboardInterrupt:
                    logger.info("Validator interrupted")
                    break
                except Exception as e:
                    logger.error(f"Error in validator loop: {e}")
                    await asyncio.sleep(60)  # Wait longer on error
        
        finally:
            await runner.cleanup()
            logger.info("Validator stopped")
    
    # ===================== MINER SCORING SYSTEM =====================
    
    async def _collect_miner_data(self):
        """Collect performance data from all miners"""
        try:
            logger.debug("Collecting miner performance data...")
            
            for uid in range(self.metagraph.n):
                hotkey = self.metagraph.hotkeys[uid]
                
                # Initialize if new miner
                if uid not in self.miner_performances:
                    self.miner_performances[uid] = MinerPerformance(
                        miner_uid=uid,
                        hotkey=hotkey
                    )
                
                # Collect current performance metrics
                await self._update_miner_performance(uid)
            
            logger.debug(f"Updated performance data for {len(self.miner_performances)} miners")
            
        except Exception as e:
            logger.error(f"Error collecting miner data: {e}")
    
    async def _update_miner_performance(self, uid: int):
        """Update performance metrics for a specific miner"""
        try:
            performance = self.miner_performances[uid]
            
            # Get miner's recent activity
            # This would typically involve:
            # 1. Checking on-chain transactions
            # 2. Monitoring API responses
            # 3. Tracking success/failure rates
            
            # Volume metrics (from on-chain data)
            volume_data = await self._get_miner_volume(uid)
            performance.total_volume = volume_data.get('total_volume', Decimal("0"))
            performance.successful_operations = volume_data.get('successful_ops', 0)
            performance.failed_operations = volume_data.get('failed_ops', 0)
            
            # Speed metrics (from API monitoring)
            speed_data = await self._get_miner_speed(uid)
            performance.avg_response_time = speed_data.get('avg_response_time', 0.0)
            performance.uptime_percentage = speed_data.get('uptime', 0.0)
            
            # Quality metrics (from transaction analysis)
            quality_data = await self._get_miner_quality(uid)
            performance.accuracy_rate = quality_data.get('accuracy', 0.0)
            performance.fee_competitiveness = quality_data.get('fee_score', 0.0)
            
            performance.last_activity = int(time.time())
            
        except Exception as e:
            logger.error(f"Error updating performance for miner {uid}: {e}")
    
    async def _score_miners(self):
        """Score all miners based on performance metrics"""
        try:
            logger.info("Scoring miners based on performance...")
            
            scores = torch.zeros(self.metagraph.n)
            
            for uid, performance in self.miner_performances.items():
                if uid >= self.metagraph.n:
                    continue
                
                # Calculate composite score
                score = self._calculate_miner_score(performance)
                scores[uid] = score
            
            # Normalize scores
            if scores.sum() > 0:
                scores = scores / scores.sum()
            
            self.current_scores = scores
            
            # Log top performers
            top_performers = torch.topk(scores, min(5, len(scores)))
            logger.info("Top performing miners:")
            for i, (score, uid) in enumerate(zip(top_performers.values, top_performers.indices)):
                if score > 0:
                    logger.info(f"  {i+1}. UID {uid}: {score:.4f}")
            
        except Exception as e:
            logger.error(f"Error scoring miners: {e}")
    
    def _calculate_miner_score(self, performance: MinerPerformance) -> float:
        """Calculate score for a single miner"""
        try:
            # Multi-factor scoring algorithm
            
            # 1. Volume Score (40% weight)
            volume_score = float(min(performance.total_volume / Decimal("1000"), Decimal("1")))
            
            # 2. Reliability Score (25% weight)
            total_ops = performance.successful_operations + performance.failed_operations
            reliability_score = (
                performance.successful_operations / max(total_ops, 1) 
                if total_ops > 0 else 0
            )
            
            # 3. Speed Score (20% weight)
            # Lower response time = higher score
            speed_score = max(0, (5.0 - performance.avg_response_time) / 5.0)
            uptime_score = performance.uptime_percentage / 100.0
            combined_speed = (speed_score + uptime_score) / 2
            
            # 4. Quality Score (15% weight)
            quality_score = (
                performance.accuracy_rate * 0.6 + 
                performance.fee_competitiveness * 0.4
            )
            
            # Combine scores with weights
            final_score = (
                volume_score * 0.40 +
                reliability_score * 0.25 +
                combined_speed * 0.20 +
                quality_score * 0.15
            )
            
            # Apply recency penalty for inactive miners
            time_since_activity = time.time() - performance.last_activity
            if time_since_activity > 3600:  # More than 1 hour inactive
                recency_penalty = max(0, 1 - (time_since_activity / 86400))  # 24 hour decay
                final_score *= recency_penalty
            
            return max(0, min(1, final_score))
            
        except Exception as e:
            logger.error(f"Error calculating score for miner {performance.miner_uid}: {e}")
            return 0.0
    
    async def _submit_weights(self):
        """Submit weights to Bittensor network"""
        try:
            if self.current_scores.sum() == 0:
                logger.warning("No scores to submit")
                return
            
            # Convert to UIDs and weights
            uids = torch.arange(self.metagraph.n)
            weights = self.current_scores.clone()
            
            # Filter out zero weights for efficiency
            non_zero_mask = weights > 0
            if non_zero_mask.sum() == 0:
                logger.warning("No non-zero weights to submit")
                return
                
            filtered_uids = uids[non_zero_mask]
            filtered_weights = weights[non_zero_mask]
            
            # Submit to network
            success, message = self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=filtered_uids,
                weights=filtered_weights,
                wait_for_finalization=False,
            )
            
            if success:
                logger.info(f"Successfully submitted weights for {len(filtered_uids)} miners")
            else:
                logger.error(f"Failed to submit weights: {message}")
                
        except Exception as e:
            logger.error(f"Error submitting weights: {e}")
    
    # ===================== DATA COLLECTION =====================
    
    async def _get_miner_volume(self, uid: int) -> Dict[str, any]:
        """Get miner volume metrics from on-chain data"""
        try:
            # This would analyze:
            # 1. TAO20 mint/redeem transactions
            # 2. Volume processed by this miner
            # 3. Success/failure rates
            
            # Placeholder - real implementation would query blockchain
            return {
                'total_volume': Decimal("100"),  # Mock data
                'successful_ops': 10,
                'failed_ops': 1,
            }
            
        except Exception as e:
            logger.error(f"Error getting volume for miner {uid}: {e}")
            return {'total_volume': Decimal("0"), 'successful_ops': 0, 'failed_ops': 0}
    
    async def _get_miner_speed(self, uid: int) -> Dict[str, float]:
        """Get miner speed metrics from API monitoring"""
        try:
            # This would monitor:
            # 1. API response times
            # 2. Transaction confirmation speed
            # 3. Uptime percentage
            
            # Placeholder - real implementation would ping miner APIs
            return {
                'avg_response_time': 2.5,  # Mock data
                'uptime': 95.0,
            }
            
        except Exception as e:
            logger.error(f"Error getting speed for miner {uid}: {e}")
            return {'avg_response_time': 10.0, 'uptime': 0.0}
    
    async def _get_miner_quality(self, uid: int) -> Dict[str, float]:
        """Get miner quality metrics from transaction analysis"""
        try:
            # This would analyze:
            # 1. Transaction accuracy
            # 2. Fee competitiveness
            # 3. Error rates
            
            # Placeholder - real implementation would analyze transactions
            return {
                'accuracy': 0.98,  # Mock data
                'fee_score': 0.85,
            }
            
        except Exception as e:
            logger.error(f"Error getting quality for miner {uid}: {e}")
            return {'accuracy': 0.0, 'fee_score': 0.0}
    
    # ===================== API ENDPOINTS =====================
    
    def _setup_api_routes(self):
        """Setup API routes for validator"""
        self.app.router.add_get('/health', self._api_health)
        self.app.router.add_get('/scores', self._api_scores)
        self.app.router.add_get('/miners', self._api_miners)
        self.app.router.add_get('/miner/{uid}', self._api_miner_detail)
    
    async def _api_health(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'validator_uid': self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address) if self.wallet.hotkey.ss58_address in self.metagraph.hotkeys else -1,
            'miners_tracked': len(self.miner_performances),
            'last_scoring': int(time.time())
        })
    
    async def _api_scores(self, request):
        """Current miner scores endpoint"""
        scores_dict = {}
        for uid in range(len(self.current_scores)):
            if self.current_scores[uid] > 0:
                scores_dict[uid] = float(self.current_scores[uid])
        
        return web.json_response({
            'scores': scores_dict,
            'total_miners': len(self.current_scores),
            'active_miners': len(scores_dict)
        })
    
    async def _api_miners(self, request):
        """Miner performance summary endpoint"""
        miners_data = []
        
        for uid, performance in self.miner_performances.items():
            miners_data.append({
                'uid': uid,
                'hotkey': performance.hotkey,
                'score': float(self.current_scores[uid]) if uid < len(self.current_scores) else 0,
                'total_volume': str(performance.total_volume),
                'success_rate': performance.successful_operations / max(performance.successful_operations + performance.failed_operations, 1),
                'uptime': performance.uptime_percentage,
                'last_activity': performance.last_activity
            })
        
        # Sort by score descending
        miners_data.sort(key=lambda x: x['score'], reverse=True)
        
        return web.json_response({'miners': miners_data})
    
    async def _api_miner_detail(self, request):
        """Detailed miner performance endpoint"""
        try:
            uid = int(request.match_info['uid'])
            
            if uid not in self.miner_performances:
                return web.json_response({'error': 'Miner not found'}, status=404)
            
            performance = self.miner_performances[uid]
            
            return web.json_response({
                'uid': uid,
                'hotkey': performance.hotkey,
                'score': float(self.current_scores[uid]) if uid < len(self.current_scores) else 0,
                'metrics': {
                    'volume': {
                        'total': str(performance.total_volume),
                        'successful_operations': performance.successful_operations,
                        'failed_operations': performance.failed_operations
                    },
                    'speed': {
                        'avg_response_time': performance.avg_response_time,
                        'uptime_percentage': performance.uptime_percentage
                    },
                    'quality': {
                        'accuracy_rate': performance.accuracy_rate,
                        'fee_competitiveness': performance.fee_competitiveness
                    }
                },
                'last_activity': performance.last_activity
            })
            
        except ValueError:
            return web.json_response({'error': 'Invalid UID'}, status=400)
        except Exception as e:
            logger.error(f"Error in miner detail API: {e}")
            return web.json_response({'error': 'Internal error'}, status=500)
    
    def stop(self):
        """Stop the validator"""
        self.running = False
        logger.info("Validator stop requested")

# ===================== MAIN ENTRY POINT =====================

async def main():
    """Main entry point for simple validator"""
    
    config = ValidatorConfig(
        wallet_name=os.getenv("WALLET_NAME", "default"),
        wallet_hotkey=os.getenv("WALLET_HOTKEY", "default"),
    )
    
    # Create and run validator
    validator = SimpleTAO20Validator(config)
    
    try:
        await validator.run()
    except KeyboardInterrupt:
        logger.info("Validator interrupted by user")
    finally:
        validator.stop()

if __name__ == "__main__":
    asyncio.run(main())
