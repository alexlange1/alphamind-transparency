#!/usr/bin/env python3
"""
Simplified TAO20 Validator
ONLY handles delivery validation and NAV calculation - clear role separation
"""

import asyncio
import logging
import os
import time
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass
from statistics import median

from .common.base import TAO20Base

logger = logging.getLogger(__name__)

@dataclass
class DeliveryValidation:
    """Result of delivery validation"""
    delivery_id: str
    is_valid: bool
    nav_per_token: float
    validation_timestamp: int
    validator_signature: str
    error_message: Optional[str] = None

@dataclass
class PriceData:
    """Price data for NAV calculation"""
    netuid: int
    price_tao: float
    timestamp: int
    source: str

class SimplifiedValidator(TAO20Base):
    """
    Simplified Validator - Only handles delivery validation and NAV calculation
    
    Clear responsibilities:
    1. Validate miner deliveries match index requirements
    2. Calculate NAV at delivery time
    3. Provide cryptographic attestations
    4. Maintain price consensus
    """
    
    def __init__(
        self,
        wallet_path: str,
        validator_id: str,
        api_port: int = 8000,
        bittensor_network: str = "finney"
    ):
        super().__init__(wallet_path, validator_id, bittensor_network)
        self.api_port = api_port
        
        # Validator-specific metrics
        self.metrics.update({
            'deliveries_validated': 0,
            'deliveries_rejected': 0,
            'nav_calculations': 0,
            'price_updates': 0
        })
        
        # Simple in-memory storage - no complex dependencies
        self.current_prices: Dict[int, PriceData] = {}
        self.current_weights: Dict[int, int] = {}
        self.validated_deliveries: List[DeliveryValidation] = []
    
    def update_price(self, netuid: int, price_tao: float, source: str = "btcli"):
        """Update price for a specific netuid"""
        self.current_prices[netuid] = PriceData(
            netuid=netuid,
            price_tao=price_tao,
            timestamp=int(time.time()),
            source=source
        )
        self.increment_metric('price_updates')
        logger.debug(f"Updated price for netuid {netuid}: {price_tao} TAO")
    
    def update_weights(self, weights: Dict[int, int]):
        """Update index weights"""
        self.current_weights = weights.copy()
        logger.info(f"Updated weights for {len(weights)} netuids")
    
    def calculate_nav(self, delivery_amounts: Dict[int, int]) -> float:
        """
        Calculate NAV based on current prices and delivery amounts
        Simple, focused calculation with no external dependencies
        """
        if not self.current_prices:
            logger.error("No price data available for NAV calculation")
            return 0.0
        
        total_value_tao = 0.0
        total_tokens = 0
        
        for netuid, amount in delivery_amounts.items():
            price_data = self.current_prices.get(netuid)
            if not price_data:
                logger.warning(f"No price data for netuid {netuid}")
                continue
            
            # Check price staleness (5 minutes max)
            if time.time() - price_data.timestamp > 300:
                logger.warning(f"Stale price data for netuid {netuid}")
                continue
            
            value_tao = amount * price_data.price_tao
            total_value_tao += value_tao
            total_tokens += amount
        
        nav_per_token = total_value_tao / total_tokens if total_tokens > 0 else 0.0
        self.increment_metric('nav_calculations')
        
        return nav_per_token
    
    def validate_delivery(
        self, 
        delivery_id: str,
        netuid_amounts: Dict[int, int],
        tolerance_bps: int = 100
    ) -> DeliveryValidation:
        """
        Validate delivery against current index requirements
        Returns signed validation result
        """
        self.increment_metric('deliveries_validated')
        
        try:
            # Check against current weights
            if not self.current_weights:
                return DeliveryValidation(
                    delivery_id=delivery_id,
                    is_valid=False,
                    nav_per_token=0.0,
                    validation_timestamp=int(time.time()),
                    validator_signature="",
                    error_message="No current weights available"
                )
            
            # Validate proportions match index weights within tolerance
            for netuid, required_weight in self.current_weights.items():
                delivered_amount = netuid_amounts.get(netuid, 0)
                tolerance = (required_weight * tolerance_bps) // 10000
                
                if abs(delivered_amount - required_weight) > tolerance:
                    self.increment_metric('deliveries_rejected')
                    return DeliveryValidation(
                        delivery_id=delivery_id,
                        is_valid=False,
                        nav_per_token=0.0,
                        validation_timestamp=int(time.time()),
                        validator_signature="",
                        error_message=f"Netuid {netuid} amount {delivered_amount} outside tolerance"
                    )
            
            # Calculate NAV
            nav = self.calculate_nav(netuid_amounts)
            if nav <= 0:
                self.increment_metric('deliveries_rejected')
                return DeliveryValidation(
                    delivery_id=delivery_id,
                    is_valid=False,
                    nav_per_token=0.0,
                    validation_timestamp=int(time.time()),
                    validator_signature="",
                    error_message="Invalid NAV calculation"
                )
            
            # Create validation payload for signing
            validation_data = f"{delivery_id}:{nav}:{int(time.time())}"
            signature = self.sign_message(validation_data)
            
            validation = DeliveryValidation(
                delivery_id=delivery_id,
                is_valid=True,
                nav_per_token=nav,
                validation_timestamp=int(time.time()),
                validator_signature=signature
            )
            
            # Store validation
            self.validated_deliveries.append(validation)
            
            logger.info(f"Validated delivery {delivery_id}: NAV={nav:.6f}")
            return validation
            
        except Exception as e:
            logger.error(f"Validation error for {delivery_id}: {e}")
            self.increment_metric('deliveries_rejected')
            return DeliveryValidation(
                delivery_id=delivery_id,
                is_valid=False,
                nav_per_token=0.0,
                validation_timestamp=int(time.time()),
                validator_signature="",
                error_message=str(e)
            )
    
    def sign_message(self, message: str) -> str:
        """Simple message signing using hotkey"""
        # Real implementation would use Bittensor signing
        # For now, return a simple hash
        return hashlib.sha256(f"{self.hotkey_ss58}:{message}".encode()).hexdigest()
    
    def get_current_weights_api(self) -> Dict[str, any]:
        """API endpoint for current weights"""
        return {
            'netuid_weights': self.current_weights,
            'timestamp': int(time.time()),
            'validator_id': self.participant_id
        }
    
    def get_current_prices_api(self) -> Dict[str, any]:
        """API endpoint for current prices"""
        prices = {}
        for netuid, price_data in self.current_prices.items():
            prices[str(netuid)] = {
                'price_tao': price_data.price_tao,
                'timestamp': price_data.timestamp,
                'source': price_data.source
            }
        
        return {
            'prices': prices,
            'timestamp': int(time.time()),
            'validator_id': self.participant_id
        }
    
    async def update_prices_from_network(self):
        """Update prices from Bittensor network"""
        try:
            # Simple price fetching - no complex dependencies
            # Real implementation would query Bittensor network
            logger.info("Updating prices from network")
            
            # Mock some prices for demonstration
            mock_prices = {
                1: 0.1,   # Mock price for netuid 1
                2: 0.15,  # Mock price for netuid 2
                3: 0.08   # Mock price for netuid 3
            }
            
            for netuid, price in mock_prices.items():
                self.update_price(netuid, price, "network")
                
        except Exception as e:
            logger.error(f"Error updating prices: {e}")
    
    async def run_validation_service(self):
        """
        Main validator loop
        1. Update prices periodically
        2. Serve API endpoints
        3. Process validation requests
        """
        logger.info(f"Starting validation service on port {self.api_port}")
        
        # Start price update loop
        asyncio.create_task(self.price_update_loop())
        
        # Start simple HTTP API server
        await self.start_api_server()
    
    async def price_update_loop(self):
        """Periodic price updates"""
        while True:
            try:
                await self.update_prices_from_network()
                await asyncio.sleep(60)  # Update every minute
            except Exception as e:
                logger.error(f"Price update loop error: {e}")
                await asyncio.sleep(10)
    
    async def start_api_server(self):
        """Simple HTTP API server - no FastAPI dependency"""
        from aiohttp import web
        
        async def handle_weights(request):
            return web.json_response(self.get_current_weights_api())
        
        async def handle_prices(request):
            return web.json_response(self.get_current_prices_api())
        
        async def handle_validate(request):
            data = await request.json()
            validation = self.validate_delivery(
                delivery_id=data['delivery_id'],
                netuid_amounts=data['netuid_amounts']
            )
            return web.json_response({
                'delivery_id': validation.delivery_id,
                'is_valid': validation.is_valid,
                'nav_per_token': validation.nav_per_token,
                'validator_signature': validation.validator_signature,
                'error_message': validation.error_message
            })
        
        app = web.Application()
        app.router.add_get('/current_weights', handle_weights)
        app.router.add_get('/current_prices', handle_prices)
        app.router.add_post('/validate_delivery', handle_validate)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.api_port)
        await site.start()
        
        logger.info(f"API server started on port {self.api_port}")
        
        # Keep running
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour

# Example usage
async def main():
    validator = SimplifiedValidator(
        wallet_path=os.environ.get("WALLET_PATH", "~/.bittensor/wallets/default"),
        validator_id=os.environ.get("VALIDATOR_ID", "simple_validator_1"),
        api_port=int(os.environ.get("API_PORT", "8000"))
    )
    
    # Set some initial weights for testing
    validator.update_weights({1: 1000, 2: 1500, 3: 800})
    
    await validator.run_validation_service()

if __name__ == "__main__":
    asyncio.run(main())
