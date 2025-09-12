#!/usr/bin/env python3
"""
Phase 1: Simplified Price Validator for TAO20
Validators only submit raw price and emissions data - NAV calculated on-chain
"""

import json
import time
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal, getcontext

import aiohttp
import bittensor as bt
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_structured_data

# Set high precision
getcontext().prec = 50

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SubnetPriceData:
    """Simple price and emissions data for a subnet"""
    netuid: int
    price: Decimal  # Current token price
    emission: Decimal  # Current emission rate
    price_source: str
    confidence: float
    timestamp: int

class Phase1PriceValidator:
    """
    Simplified validator for Phase 1 - only submits raw data
    Contract handles all NAV calculation logic
    """
    
    def __init__(
        self,
        oracle_address: str,
        web3_rpc_url: str,
        validator_private_key: str,
        bittensor_network: str = "finney"
    ):
        self.oracle_address = oracle_address
        self.web3_rpc_url = web3_rpc_url
        self.validator_private_key = validator_private_key
        self.bittensor_network = bittensor_network
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(web3_rpc_url))
        self.validator_account = Account.from_key(validator_private_key)
        
        # Initialize Bittensor
        self.subtensor = bt.subtensor(network=bittensor_network)
        
        # Oracle contract
        self.oracle_abi = self._load_oracle_abi()
        self.oracle = self.w3.eth.contract(
            address=oracle_address,
            abi=self.oracle_abi
        )
        
        logger.info(f"Phase 1 Validator initialized: {self.validator_account.address}")
    
    def _load_oracle_abi(self) -> List[Dict]:
        """Load simplified oracle ABI"""
        return [
            {
                "inputs": [
                    {"name": "netuids", "type": "uint16[]"},
                    {"name": "prices", "type": "uint256[]"},
                    {"name": "emissions", "type": "uint256[]"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "signature", "type": "bytes"}
                ],
                "name": "submitPrices",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "getCurrentNAV",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    async def get_current_composition(self) -> List[int]:
        """Get current subnet composition (simplified - hardcoded for Phase 1)"""
        # In Phase 1, we'll use a fixed composition for simplicity
        # This would come from the staking manager in production
        return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    
    async def get_subnet_price(self, netuid: int) -> Tuple[Decimal, str, float]:
        """
        Get price for subnet token - simplified for Phase 1
        Returns: (price, source, confidence)
        """
        try:
            # Method 1: Try to get from DEX/market data
            market_price = await self._get_market_price(netuid)
            if market_price:
                return market_price, "market", 0.9
            
            # Method 2: Calculate from emissions (internal valuation)
            emission_price = await self._calculate_emission_price(netuid)
            if emission_price:
                return emission_price, "emission", 0.7
            
            # Method 3: Fallback to fixed price
            fallback_price = Decimal('0.001')  # $0.001 fallback
            return fallback_price, "fallback", 0.3
            
        except Exception as e:
            logger.warning(f"Error getting price for subnet {netuid}: {e}")
            return Decimal('0.001'), "error", 0.1
    
    async def _get_market_price(self, netuid: int) -> Optional[Decimal]:
        """Try to get market price from external sources"""
        try:
            # This would integrate with actual price APIs
            # For now, return None to simulate no market data
            return None
        except:
            return None
    
    async def _calculate_emission_price(self, netuid: int) -> Optional[Decimal]:
        """Calculate price based on emission data"""
        try:
            # Get emission data from Bittensor
            emission = self.subtensor.get_emission_value_by_subnet(netuid)
            if emission is None or emission <= 0:
                return None
            
            # Simple valuation: emission * multiplier
            # This is a placeholder - real model would be more sophisticated
            base_multiplier = Decimal('0.0001')  # $0.0001 per emission unit
            calculated_price = Decimal(str(emission)) * base_multiplier
            
            # Apply bounds
            min_price = Decimal('0.0001')
            max_price = Decimal('1.0')
            
            return max(min_price, min(max_price, calculated_price))
            
        except Exception as e:
            logger.debug(f"Emission price calculation failed for {netuid}: {e}")
            return None
    
    async def get_subnet_emission(self, netuid: int) -> Decimal:
        """Get current emission for subnet"""
        try:
            emission = self.subtensor.get_emission_value_by_subnet(netuid)
            return Decimal(str(emission)) if emission else Decimal('0')
        except Exception as e:
            logger.warning(f"Error getting emission for subnet {netuid}: {e}")
            return Decimal('0')
    
    async def collect_price_data(self) -> List[SubnetPriceData]:
        """Collect price and emission data for all subnets"""
        logger.info("Collecting price and emission data...")
        
        netuids = await self.get_current_composition()
        price_data = []
        
        for netuid in netuids:
            try:
                # Get price and emission
                price, source, confidence = await self.get_subnet_price(netuid)
                emission = await self.get_subnet_emission(netuid)
                
                price_data.append(SubnetPriceData(
                    netuid=netuid,
                    price=price,
                    emission=emission,
                    price_source=source,
                    confidence=confidence,
                    timestamp=int(time.time())
                ))
                
                logger.debug(f"Subnet {netuid}: ${price:.6f} ({source}), emission: {emission}")
                
            except Exception as e:
                logger.error(f"Error collecting data for subnet {netuid}: {e}")
                continue
        
        logger.info(f"Collected data for {len(price_data)} subnets")
        return price_data
    
    async def create_price_submission(self, price_data: List[SubnetPriceData]) -> Dict:
        """Create EIP-712 signed price submission"""
        try:
            # Extract arrays for submission
            netuids = [data.netuid for data in price_data]
            prices = [int(data.price * Decimal('1e18')) for data in price_data]  # Convert to wei
            emissions = [int(data.emission * Decimal('1e18')) for data in price_data]  # Convert to wei
            timestamp = int(time.time())
            
            # Get validator nonce from contract
            nonce = 0  # This should be fetched from contract in production
            
            # Create EIP-712 structured data
            domain = {
                'name': 'TAO20 Hybrid NAV Oracle',
                'version': '1',
                'chainId': self.w3.eth.chain_id,
                'verifyingContract': self.oracle_address
            }
            
            message = {
                'netuids': netuids,
                'prices': prices,
                'emissions': emissions,
                'timestamp': timestamp,
                'nonce': nonce,
                'validator': self.validator_account.address
            }
            
            types = {
                'EIP712Domain': [
                    {'name': 'name', 'type': 'string'},
                    {'name': 'version', 'type': 'string'},
                    {'name': 'chainId', 'type': 'uint256'},
                    {'name': 'verifyingContract', 'type': 'address'}
                ],
                'PriceSubmission': [
                    {'name': 'netuids', 'type': 'uint16[]'},
                    {'name': 'prices', 'type': 'uint256[]'},
                    {'name': 'emissions', 'type': 'uint256[]'},
                    {'name': 'timestamp', 'type': 'uint256'},
                    {'name': 'nonce', 'type': 'uint256'},
                    {'name': 'validator', 'type': 'address'}
                ]
            }
            
            # Create and sign structured data
            structured_data = {
                'types': types,
                'primaryType': 'PriceSubmission',
                'domain': domain,
                'message': message
            }
            
            encoded = encode_structured_data(structured_data)
            signature = self.validator_account.sign_message(encoded)
            
            return {
                'netuids': netuids,
                'prices': prices,
                'emissions': emissions,
                'timestamp': timestamp,
                'signature': signature.signature.hex(),
                'validator': self.validator_account.address,
                'price_data': [
                    {
                        'netuid': data.netuid,
                        'price_usd': float(data.price),
                        'emission': float(data.emission),
                        'source': data.price_source,
                        'confidence': data.confidence
                    }
                    for data in price_data
                ]
            }
            
        except Exception as e:
            logger.error(f"Error creating price submission: {e}")
            raise
    
    async def submit_to_oracle(self, submission: Dict) -> bool:
        """Submit price data to oracle contract"""
        try:
            logger.info("Submitting price data to oracle...")
            
            # Build transaction
            transaction = self.oracle.functions.submitPrices(
                submission['netuids'],
                submission['prices'],
                submission['emissions'],
                submission['timestamp'],
                bytes.fromhex(submission['signature'][2:])  # Remove 0x prefix
            ).build_transaction({
                'from': self.validator_account.address,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.validator_account.address)
            })
            
            # Sign and send transaction
            signed_txn = self.validator_account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info(f"✅ Price submission successful: {tx_hash.hex()}")
                return True
            else:
                logger.error(f"❌ Price submission failed: {tx_hash.hex()}")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting to oracle: {e}")
            return False
    
    async def get_current_nav(self) -> Optional[Decimal]:
        """Get current NAV from oracle contract"""
        try:
            nav_wei = self.oracle.functions.getCurrentNAV().call()
            return Decimal(nav_wei) / Decimal('1e18')
        except Exception as e:
            logger.warning(f"Could not get current NAV: {e}")
            return None
    
    async def run_validation_cycle(self) -> bool:
        """Run a complete validation cycle"""
        try:
            logger.info("🔄 Starting Phase 1 validation cycle...")
            
            # Step 1: Collect price and emission data
            price_data = await self.collect_price_data()
            if not price_data:
                logger.error("No price data collected")
                return False
            
            # Step 2: Create signed submission
            submission = await self.create_price_submission(price_data)
            
            # Step 3: Submit to oracle
            success = await self.submit_to_oracle(submission)
            
            if success:
                # Step 4: Check updated NAV
                await asyncio.sleep(5)  # Wait for processing
                nav = await self.get_current_nav()
                if nav:
                    logger.info(f"📊 Updated NAV: {nav:.6f}")
                
                # Step 5: Save report
                await self.save_validation_report(submission, nav)
                
                logger.info("✅ Validation cycle completed successfully")
                return True
            else:
                logger.error("❌ Validation cycle failed")
                return False
                
        except Exception as e:
            logger.error(f"Error in validation cycle: {e}")
            return False
    
    async def save_validation_report(self, submission: Dict, nav: Optional[Decimal]):
        """Save validation report for auditing"""
        timestamp = submission['timestamp']
        report = {
            'timestamp': timestamp,
            'validator': self.validator_account.address,
            'submission': submission,
            'resulting_nav': float(nav) if nav else None,
            'phase': 1,
            'oracle_address': self.oracle_address,
            'chain_id': self.w3.eth.chain_id
        }
        
        filename = f"phase1_validation_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Validation report saved: {filename}")

async def main():
    """Main function"""
    import os
    
    # Configuration
    config = {
        'oracle_address': os.getenv('ORACLE_ADDRESS'),
        'web3_rpc_url': os.getenv('WEB3_RPC_URL'),
        'validator_private_key': os.getenv('VALIDATOR_PRIVATE_KEY'),
        'bittensor_network': os.getenv('BITTENSOR_NETWORK', 'finney')
    }
    
    # Validate configuration
    missing = [k for k, v in config.items() if not v and k != 'bittensor_network']
    if missing:
        logger.error(f"Missing configuration: {missing}")
        return
    
    try:
        # Initialize validator
        validator = Phase1PriceValidator(**config)
        
        # Run validation cycle
        success = await validator.run_validation_cycle()
        
        if success:
            print("\n" + "="*50)
            print("🎉 PHASE 1 VALIDATION COMPLETED")
            print("="*50)
            print("✅ Price data submitted successfully")
            print("✅ NAV calculated on-chain by oracle")
            print("✅ Transparent and auditable")
            print("="*50)
        else:
            print("\n❌ Validation failed - check logs")
            
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
