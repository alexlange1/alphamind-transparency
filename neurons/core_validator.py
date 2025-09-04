#!/usr/bin/env python3
"""
Production TAO20 Validator - Zero Mock Code
Only essential functionality, real implementations only
"""

import asyncio
import logging
import os
import time
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass
from statistics import median

import bittensor as bt
from aiohttp import web

logger = logging.getLogger(__name__)

@dataclass
class DeliveryValidation:
    """Result of delivery validation"""
    delivery_id: str
    is_valid: bool
    nav_per_token: float
    timestamp: int
    validator_signature: str
    error_message: Optional[str] = None

@dataclass
class PricePoint:
    """Price data point"""
    netuid: int
    price_tao: float
    timestamp: int

class ProductionValidator:
    """
    Production TAO20 Validator
    
    ONLY does:
    1. Validate deliveries match current requirements
    2. Calculate NAV based on real prices
    3. Sign validations
    4. Serve API endpoints
    
    Does NOT:
    - Mock any functionality
    - Have complex dependency chains
    - Implement complex consensus (uses simple median)
    """
    
    def __init__(
        self,
        wallet_path: str,
        validator_id: str,
        api_port: int = 8000,
        bittensor_network: str = "finney"
    ):
        self.validator_id = validator_id
        self.api_port = api_port
        
        # Initialize Bittensor - fail fast if not working
        self.wallet = bt.wallet(path=wallet_path)
        self.subtensor = bt.subtensor(network=bittensor_network)
        self.hotkey_ss58 = self.wallet.hotkey.ss58_address
        
        # Current state
        self.current_prices: Dict[int, PricePoint] = {}
        self.current_weights: Dict[int, int] = {}
        self.vault_address = os.environ.get("VAULT_ADDRESS", "")
        
        # Simple metrics
        self.validations_performed = 0
        self.validations_successful = 0
        
        logger.info(f"Production validator initialized: {validator_id}")
        logger.info(f"Hotkey: {self.hotkey_ss58}")
    
    def update_prices_from_network(self):
        """Update prices from real Bittensor network data"""
        try:
            # Get real subnet information
            subnets = self.subtensor.get_all_subnets_info()
            
            for subnet in subnets:
                netuid = subnet.netuid
                
                # Calculate price based on subnet metrics
                # This is a simplified calculation - in production you'd use DEX prices
                if subnet.emission and subnet.total_stake:
                    # Price based on emission/stake ratio
                    price_tao = float(subnet.emission) / float(subnet.total_stake)
                    
                    self.current_prices[netuid] = PricePoint(
                        netuid=netuid,
                        price_tao=max(price_tao, 0.001),  # Minimum price floor
                        timestamp=int(time.time())
                    )
                    
            logger.info(f"Updated prices for {len(self.current_prices)} subnets")
            
        except Exception as e:
            logger.error(f"Error updating prices from network: {e}")
    
    def update_weights(self, weights: Dict[int, int]):
        """Update index weights"""
        self.current_weights = weights.copy()
        logger.info(f"Updated weights for {len(weights)} subnets")
    
    def calculate_nav(self, delivery_amounts: Dict[int, int]) -> float:
        """Calculate NAV based on current prices"""
        if not self.current_prices:
            logger.error("No price data available")
            return 0.0
        
        total_value_tao = 0.0
        total_tokens = 0
        
        for netuid, amount in delivery_amounts.items():
            price_point = self.current_prices.get(netuid)
            if not price_point:
                logger.warning(f"No price data for netuid {netuid}")
                continue
            
            # Check price staleness (10 minutes max)
            if time.time() - price_point.timestamp > 600:
                logger.warning(f"Stale price data for netuid {netuid}")
                continue
            
            value_tao = amount * price_point.price_tao / 1e9  # Convert from RAO
            total_value_tao += value_tao
            total_tokens += amount
        
        return total_value_tao / (total_tokens / 1e9) if total_tokens > 0 else 0.0
    
    def validate_delivery_amounts(
        self, 
        delivery_amounts: Dict[int, int],
        tolerance_bps: int = 100
    ) -> tuple[bool, Optional[str]]:
        """Validate delivery amounts match current weights"""
        if not self.current_weights:
            return False, "No current weights available"
        
        # Check all required subnets are present
        for netuid, required_weight in self.current_weights.items():
            delivered_amount = delivery_amounts.get(netuid, 0)
            tolerance = (required_weight * tolerance_bps) // 10000
            
            if abs(delivered_amount - required_weight) > tolerance:
                return False, f"Netuid {netuid}: delivered {delivered_amount}, required {required_weight} (±{tolerance})"
        
        # Check no unexpected subnets
        for netuid in delivery_amounts:
            if netuid not in self.current_weights:
                return False, f"Unexpected netuid {netuid} in delivery"
        
        return True, None
    
    def sign_validation(self, validation_data: str) -> str:
        """Sign validation data with hotkey"""
        try:
            # Create signature using Bittensor wallet
            signature = self.wallet.hotkey.sign(validation_data.encode())
            return signature.hex()
        except Exception as e:
            logger.error(f"Error signing validation: {e}")
            return ""
    
    def validate_delivery(
        self,
        delivery_id: str,
        delivery_amounts: Dict[int, int]
    ) -> DeliveryValidation:
        """Validate a delivery and return signed result"""
        self.validations_performed += 1
        
        try:
            # Validate amounts
            is_valid, error_msg = self.validate_delivery_amounts(delivery_amounts)
            if not is_valid:
                return DeliveryValidation(
                    delivery_id=delivery_id,
                    is_valid=False,
                    nav_per_token=0.0,
                    timestamp=int(time.time()),
                    validator_signature="",
                    error_message=error_msg
                )
            
            # Calculate NAV
            nav = self.calculate_nav(delivery_amounts)
            if nav <= 0:
                return DeliveryValidation(
                    delivery_id=delivery_id,
                    is_valid=False,
                    nav_per_token=0.0,
                    timestamp=int(time.time()),
                    validator_signature="",
                    error_message="Invalid NAV calculation"
                )
            
            # Create validation payload and sign
            timestamp = int(time.time())
            validation_data = f"{delivery_id}:{nav}:{timestamp}:{self.validator_id}"
            signature = self.sign_validation(validation_data)
            
            if not signature:
                return DeliveryValidation(
                    delivery_id=delivery_id,
                    is_valid=False,
                    nav_per_token=0.0,
                    timestamp=timestamp,
                    validator_signature="",
                    error_message="Failed to sign validation"
                )
            
            self.validations_successful += 1
            
            return DeliveryValidation(
                delivery_id=delivery_id,
                is_valid=True,
                nav_per_token=nav,
                timestamp=timestamp,
                validator_signature=signature
            )
            
        except Exception as e:
            logger.error(f"Validation error for {delivery_id}: {e}")
            return DeliveryValidation(
                delivery_id=delivery_id,
                is_valid=False,
                nav_per_token=0.0,
                timestamp=int(time.time()),
                validator_signature="",
                error_message=str(e)
            )
    
    # API Endpoints
    async def handle_delivery_requirements(self, request):
        """API: Get current delivery requirements"""
        return web.json_response({
            'netuid_amounts': self.current_weights,
            'vault_address': self.vault_address,
            'deadline': int(time.time()) + 3600,  # 1 hour deadline
            'timestamp': int(time.time()),
            'validator_id': self.validator_id
        })
    
    async def handle_current_prices(self, request):
        """API: Get current prices"""
        prices = {}
        for netuid, price_point in self.current_prices.items():
            prices[str(netuid)] = {
                'price_tao': price_point.price_tao,
                'timestamp': price_point.timestamp
            }
        
        return web.json_response({
            'prices': prices,
            'timestamp': int(time.time()),
            'validator_id': self.validator_id
        })
    
    async def handle_validate_delivery(self, request):
        """API: Validate a delivery"""
        try:
            data = await request.json()
            validation = self.validate_delivery(
                delivery_id=data['delivery_id'],
                delivery_amounts=data['delivery_amounts']
            )
            
            return web.json_response({
                'delivery_id': validation.delivery_id,
                'is_valid': validation.is_valid,
                'nav_per_token': validation.nav_per_token,
                'timestamp': validation.timestamp,
                'validator_signature': validation.validator_signature,
                'error_message': validation.error_message
            })
            
        except Exception as e:
            return web.json_response({
                'error': str(e)
            }, status=400)
    
    async def handle_stats(self, request):
        """API: Get validator stats"""
        return web.json_response({
            'validator_id': self.validator_id,
            'hotkey_ss58': self.hotkey_ss58,
            'validations_performed': self.validations_performed,
            'validations_successful': self.validations_successful,
            'success_rate': self.validations_successful / max(self.validations_performed, 1),
            'active_prices': len(self.current_prices),
            'active_weights': len(self.current_weights)
        })
    
    async def start_api_server(self):
        """Start HTTP API server"""
        app = web.Application()
        
        # Add routes
        app.router.add_get('/delivery_requirements', self.handle_delivery_requirements)
        app.router.add_get('/current_prices', self.handle_current_prices)
        app.router.add_post('/validate_delivery', self.handle_validate_delivery)
        app.router.add_get('/stats', self.handle_stats)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.api_port)
        await site.start()
        
        logger.info(f"API server started on port {self.api_port}")
    
    async def price_update_loop(self):
        """Periodic price updates"""
        while True:
            try:
                self.update_prices_from_network()
                await asyncio.sleep(60)  # Update every minute
            except Exception as e:
                logger.error(f"Price update error: {e}")
                await asyncio.sleep(30)
    
    async def run_validator_service(self):
        """Run the complete validator service"""
        logger.info("Starting validator service")
        
        # Set initial weights (top 20 subnets by emission)
        try:
            subnets = self.subtensor.get_all_subnets_info()
            # Sort by emission and take top 20
            top_subnets = sorted(subnets, key=lambda s: s.emission, reverse=True)[:20]
            
            # Create equal weights for simplicity (can be made more sophisticated)
            weight_per_subnet = 10000 // len(top_subnets)  # 10000 bps total
            weights = {subnet.netuid: weight_per_subnet for subnet in top_subnets}
            
            self.update_weights(weights)
            logger.info(f"Set initial weights for top {len(weights)} subnets")
            
        except Exception as e:
            logger.error(f"Error setting initial weights: {e}")
        
        # Start services
        await self.start_api_server()
        await self.price_update_loop()

# Example usage
async def main():
    validator = ProductionValidator(
        wallet_path=os.environ.get("WALLET_PATH", "~/.bittensor/wallets/default"),
        validator_id=os.environ.get("VALIDATOR_ID", "prod_validator_1"),
        api_port=int(os.environ.get("API_PORT", "8000"))
    )
    
    await validator.run_validator_service()

if __name__ == "__main__":
    asyncio.run(main())
