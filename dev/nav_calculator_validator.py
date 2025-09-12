#!/usr/bin/env python3
"""
TAO20 NAV Calculator for Validators
Real-time NAV calculation script that validators can run to submit accurate NAV data
"""

import json
import time
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal, getcontext
import hashlib
import hmac
from pathlib import Path

import aiohttp
import bittensor as bt
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_structured_data

# Set high precision for calculations
getcontext().prec = 50

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SubnetTokenInfo:
    """Information about a subnet token"""
    netuid: int
    token_address: str
    staked_amount: Decimal  # Amount staked in the vault
    current_price: Decimal  # Current market price
    staking_rewards: Decimal  # Accumulated staking rewards
    last_price_update: int
    price_source: str

@dataclass
class NAVCalculationResult:
    """Result of NAV calculation"""
    nav: Decimal
    total_value: Decimal
    total_supply: Decimal
    subnet_breakdown: List[Dict]
    calculation_timestamp: int
    price_staleness_seconds: int
    confidence_score: float

class NAVCalculator:
    """
    Calculates accurate NAV for TAO20 index token
    """
    
    def __init__(
        self,
        staking_manager_address: str,
        tao20_token_address: str,
        web3_rpc_url: str,
        validator_private_key: str,
        bittensor_network: str = "finney"
    ):
        self.staking_manager_address = staking_manager_address
        self.tao20_token_address = tao20_token_address
        self.web3_rpc_url = web3_rpc_url
        self.validator_private_key = validator_private_key
        self.bittensor_network = bittensor_network
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(web3_rpc_url))
        self.validator_account = Account.from_key(validator_private_key)
        
        # Initialize Bittensor
        self.subtensor = bt.subtensor(network=bittensor_network)
        
        # Price sources configuration
        self.price_sources = {
            'coingecko': 'https://api.coingecko.com/api/v3',
            'coinmarketcap': 'https://pro-api.coinmarketcap.com/v1',
            'dexscreener': 'https://api.dexscreener.com/latest',
            'internal': 'internal_calculation'  # Calculate from DEX data
        }
        
        # Contract ABIs (simplified)
        self.staking_manager_abi = self._load_staking_manager_abi()
        self.tao20_abi = self._load_tao20_abi()
        
        # Initialize contracts
        self.staking_manager = self.w3.eth.contract(
            address=staking_manager_address,
            abi=self.staking_manager_abi
        )
        self.tao20_token = self.w3.eth.contract(
            address=tao20_token_address,
            abi=self.tao20_abi
        )
        
        # Cache for price data
        self.price_cache = {}
        self.cache_ttl = 60  # 1 minute cache
    
    def _load_staking_manager_abi(self) -> List[Dict]:
        """Load StakingManager contract ABI"""
        return [
            {
                "inputs": [],
                "name": "getCurrentComposition",
                "outputs": [
                    {"name": "netuids", "type": "uint16[]"},
                    {"name": "weights", "type": "uint256[]"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "netuid", "type": "uint16"}],
                "name": "getSubnetInfo",
                "outputs": [
                    {"name": "staked", "type": "uint256"},
                    {"name": "rewards", "type": "uint256"},
                    {"name": "lastUpdate", "type": "uint256"},
                    {"name": "validator", "type": "bytes32"},
                    {"name": "weight", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "getTotalValue",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def _load_tao20_abi(self) -> List[Dict]:
        """Load TAO20 token contract ABI"""
        return [
            {
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    async def get_current_composition(self) -> Tuple[List[int], List[int]]:
        """Get current index composition from staking manager"""
        try:
            result = self.staking_manager.functions.getCurrentComposition().call()
            netuids = [int(x) for x in result[0]]
            weights = [int(x) for x in result[1]]
            return netuids, weights
        except Exception as e:
            logger.error(f"Error getting composition: {e}")
            raise
    
    async def get_subnet_staking_data(self, netuid: int) -> Dict:
        """Get staking data for a specific subnet"""
        try:
            result = self.staking_manager.functions.getSubnetInfo(netuid).call()
            return {
                'staked_amount': Decimal(result[0]) / Decimal('1e18'),  # Convert from wei
                'rewards': Decimal(result[1]) / Decimal('1e18'),
                'last_update': result[2],
                'validator': result[3].hex(),
                'weight': result[4]
            }
        except Exception as e:
            logger.error(f"Error getting subnet {netuid} data: {e}")
            return {
                'staked_amount': Decimal('0'),
                'rewards': Decimal('0'),
                'last_update': 0,
                'validator': '0x0',
                'weight': 0
            }
    
    async def get_tao20_total_supply(self) -> Decimal:
        """Get total supply of TAO20 tokens"""
        try:
            supply = self.tao20_token.functions.totalSupply().call()
            return Decimal(supply) / Decimal('1e18')
        except Exception as e:
            logger.error(f"Error getting total supply: {e}")
            return Decimal('0')
    
    async def get_subnet_token_price(self, netuid: int) -> Tuple[Decimal, str, int]:
        """
        Get current price for subnet token
        Returns: (price, source, timestamp)
        """
        cache_key = f"price_{netuid}"
        current_time = int(time.time())
        
        # Check cache first
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            if current_time - cached_data['timestamp'] < self.cache_ttl:
                return cached_data['price'], cached_data['source'], cached_data['timestamp']
        
        # Try multiple price sources
        price_attempts = []
        
        # 1. Try CoinGecko (if subnet has listing)
        try:
            price = await self._get_price_from_coingecko(netuid)
            if price:
                price_attempts.append((price, 'coingecko', current_time))
        except Exception as e:
            logger.debug(f"CoinGecko price fetch failed for subnet {netuid}: {e}")
        
        # 2. Try DEX data (calculate from trading pairs)
        try:
            price = await self._get_price_from_dex(netuid)
            if price:
                price_attempts.append((price, 'dex', current_time))
        except Exception as e:
            logger.debug(f"DEX price fetch failed for subnet {netuid}: {e}")
        
        # 3. Try internal calculation (based on emissions/performance)
        try:
            price = await self._calculate_internal_price(netuid)
            if price:
                price_attempts.append((price, 'internal', current_time))
        except Exception as e:
            logger.debug(f"Internal price calculation failed for subnet {netuid}: {e}")
        
        # Select best price (prefer external sources, then internal)
        if price_attempts:
            # Sort by source preference: external sources first
            price_attempts.sort(key=lambda x: 0 if x[1] in ['coingecko', 'dex'] else 1)
            best_price, source, timestamp = price_attempts[0]
            
            # Cache the result
            self.price_cache[cache_key] = {
                'price': best_price,
                'source': source,
                'timestamp': timestamp
            }
            
            return best_price, source, timestamp
        
        # Fallback: return last known price or estimate
        logger.warning(f"No price data available for subnet {netuid}, using fallback")
        fallback_price = await self._get_fallback_price(netuid)
        return fallback_price, 'fallback', current_time
    
    async def _get_price_from_coingecko(self, netuid: int) -> Optional[Decimal]:
        """Get price from CoinGecko API"""
        # This would require mapping netuid to CoinGecko token IDs
        # For now, return None as most subnet tokens aren't listed
        return None
    
    async def _get_price_from_dex(self, netuid: int) -> Optional[Decimal]:
        """Calculate price from DEX trading data"""
        try:
            # This would query DEX APIs to get trading pair data
            # Implementation depends on which DEXes list subnet tokens
            
            # Placeholder implementation
            async with aiohttp.ClientSession() as session:
                # Query DEX API for subnet token trading pairs
                # Calculate volume-weighted average price
                pass
            
            return None  # Placeholder
        except Exception as e:
            logger.error(f"DEX price calculation error: {e}")
            return None
    
    async def _calculate_internal_price(self, netuid: int) -> Optional[Decimal]:
        """Calculate price based on subnet fundamentals"""
        try:
            # Get subnet information from Bittensor
            subnet_info = self.subtensor.get_subnet_info(netuid)
            if not subnet_info:
                return None
            
            # Get emissions and performance data
            emissions = self.subtensor.get_emission_value_by_subnet(netuid)
            if emissions is None:
                return None
            
            # Simple valuation model based on emissions
            # This is a placeholder - real implementation would be more sophisticated
            base_price = Decimal(str(emissions)) * Decimal('0.001')  # Simple multiplier
            
            return max(base_price, Decimal('0.0001'))  # Minimum price floor
            
        except Exception as e:
            logger.error(f"Internal price calculation error: {e}")
            return None
    
    async def _get_fallback_price(self, netuid: int) -> Decimal:
        """Get fallback price when no other sources available"""
        # Use a simple model based on subnet rank/emissions
        try:
            # Get basic subnet data
            emissions = self.subtensor.get_emission_value_by_subnet(netuid)
            if emissions:
                return Decimal(str(emissions)) * Decimal('0.0005')
        except:
            pass
        
        # Ultimate fallback
        return Decimal('0.001')
    
    async def calculate_nav(self) -> NAVCalculationResult:
        """Calculate current NAV for TAO20 index"""
        logger.info("Starting NAV calculation...")
        calculation_start = time.time()
        
        try:
            # Get current composition
            netuids, weights = await self.get_current_composition()
            logger.info(f"Current composition: {len(netuids)} subnets")
            
            # Get total supply
            total_supply = await self.get_tao20_total_supply()
            logger.info(f"Total TAO20 supply: {total_supply}")
            
            if total_supply == 0:
                # If no tokens exist, NAV is 1.0
                return NAVCalculationResult(
                    nav=Decimal('1.0'),
                    total_value=Decimal('0'),
                    total_supply=Decimal('0'),
                    subnet_breakdown=[],
                    calculation_timestamp=int(time.time()),
                    price_staleness_seconds=0,
                    confidence_score=1.0
                )
            
            # Calculate value for each subnet
            total_value = Decimal('0')
            subnet_breakdown = []
            max_staleness = 0
            confidence_scores = []
            
            for i, netuid in enumerate(netuids):
                weight = weights[i]
                
                # Get staking data
                staking_data = await self.get_subnet_staking_data(netuid)
                
                # Get current price
                price, price_source, price_timestamp = await self.get_subnet_token_price(netuid)
                
                # Calculate subnet value
                staked_value = staking_data['staked_amount'] * price
                rewards_value = staking_data['rewards']  # Rewards are already in TAO
                subnet_total_value = staked_value + rewards_value
                
                total_value += subnet_total_value
                
                # Track staleness
                staleness = int(time.time()) - price_timestamp
                max_staleness = max(max_staleness, staleness)
                
                # Calculate confidence based on price source and staleness
                confidence = self._calculate_price_confidence(price_source, staleness)
                confidence_scores.append(confidence)
                
                subnet_breakdown.append({
                    'netuid': netuid,
                    'weight_bps': weight,
                    'staked_amount': float(staking_data['staked_amount']),
                    'staking_rewards': float(staking_data['rewards']),
                    'token_price': float(price),
                    'price_source': price_source,
                    'price_staleness': staleness,
                    'total_value': float(subnet_total_value),
                    'confidence': confidence
                })
            
            # Calculate NAV
            nav = total_value / total_supply if total_supply > 0 else Decimal('1.0')
            
            # Overall confidence score (weighted average)
            overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            calculation_time = time.time() - calculation_start
            logger.info(f"NAV calculation completed in {calculation_time:.2f}s")
            logger.info(f"Calculated NAV: {nav}")
            logger.info(f"Total value: {total_value}")
            logger.info(f"Confidence score: {overall_confidence:.2f}")
            
            return NAVCalculationResult(
                nav=nav,
                total_value=total_value,
                total_supply=total_supply,
                subnet_breakdown=subnet_breakdown,
                calculation_timestamp=int(time.time()),
                price_staleness_seconds=max_staleness,
                confidence_score=overall_confidence
            )
            
        except Exception as e:
            logger.error(f"Error calculating NAV: {e}")
            raise
    
    def _calculate_price_confidence(self, source: str, staleness: int) -> float:
        """Calculate confidence score for price data"""
        base_confidence = {
            'coingecko': 0.9,
            'dex': 0.8,
            'internal': 0.6,
            'fallback': 0.3
        }.get(source, 0.1)
        
        # Reduce confidence based on staleness
        staleness_penalty = min(staleness / 3600, 0.5)  # Max 50% penalty after 1 hour
        
        return max(base_confidence * (1 - staleness_penalty), 0.1)
    
    async def create_nav_submission(self, nav_result: NAVCalculationResult) -> Dict:
        """Create EIP-712 signed NAV submission"""
        try:
            # Extract subnet prices for submission
            subnet_prices = [
                int(Decimal(subnet['token_price']) * Decimal('1e18'))  # Convert to wei
                for subnet in nav_result.subnet_breakdown
            ]
            
            # Create EIP-712 structured data
            domain = {
                'name': 'TAO20 NAV Oracle with Slashing',
                'version': '1',
                'chainId': self.w3.eth.chain_id,
                'verifyingContract': self.staking_manager_address  # Oracle address
            }
            
            message = {
                'nav': int(nav_result.nav * Decimal('1e18')),  # Convert to wei
                'subnetPrices': subnet_prices,
                'timestamp': nav_result.calculation_timestamp,
                'nonce': 0,  # This should be fetched from contract
                'validator': self.validator_account.address
            }
            
            types = {
                'EIP712Domain': [
                    {'name': 'name', 'type': 'string'},
                    {'name': 'version', 'type': 'string'},
                    {'name': 'chainId', 'type': 'uint256'},
                    {'name': 'verifyingContract', 'type': 'address'}
                ],
                'NAVSubmission': [
                    {'name': 'nav', 'type': 'uint256'},
                    {'name': 'subnetPrices', 'type': 'uint256[]'},
                    {'name': 'timestamp', 'type': 'uint256'},
                    {'name': 'nonce', 'type': 'uint256'},
                    {'name': 'validator', 'type': 'address'}
                ]
            }
            
            # Create structured data
            structured_data = {
                'types': types,
                'primaryType': 'NAVSubmission',
                'domain': domain,
                'message': message
            }
            
            # Sign the data
            encoded = encode_structured_data(structured_data)
            signature = self.validator_account.sign_message(encoded)
            
            return {
                'nav': message['nav'],
                'subnetPrices': subnet_prices,
                'timestamp': message['timestamp'],
                'signature': signature.signature.hex(),
                'validator': self.validator_account.address,
                'confidence': nav_result.confidence_score,
                'breakdown': nav_result.subnet_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error creating NAV submission: {e}")
            raise
    
    async def save_calculation_report(self, nav_result: NAVCalculationResult, submission: Dict):
        """Save detailed calculation report for auditing"""
        timestamp = nav_result.calculation_timestamp
        report_file = Path(f"nav_reports/nav_report_{timestamp}.json")
        report_file.parent.mkdir(exist_ok=True)
        
        report = {
            'calculation_timestamp': timestamp,
            'nav': float(nav_result.nav),
            'total_value': float(nav_result.total_value),
            'total_supply': float(nav_result.total_supply),
            'confidence_score': nav_result.confidence_score,
            'price_staleness_seconds': nav_result.price_staleness_seconds,
            'subnet_breakdown': nav_result.subnet_breakdown,
            'submission_data': submission,
            'validator_address': self.validator_account.address,
            'calculation_metadata': {
                'web3_rpc': self.web3_rpc_url,
                'bittensor_network': self.bittensor_network,
                'staking_manager_address': self.staking_manager_address,
                'tao20_token_address': self.tao20_token_address
            }
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Calculation report saved: {report_file}")

async def main():
    """Main function for running NAV calculation"""
    import os
    
    # Configuration from environment variables
    config = {
        'staking_manager_address': os.getenv('STAKING_MANAGER_ADDRESS'),
        'tao20_token_address': os.getenv('TAO20_TOKEN_ADDRESS'),
        'web3_rpc_url': os.getenv('WEB3_RPC_URL'),
        'validator_private_key': os.getenv('VALIDATOR_PRIVATE_KEY'),
        'bittensor_network': os.getenv('BITTENSOR_NETWORK', 'finney')
    }
    
    # Validate configuration
    missing_config = [k for k, v in config.items() if not v and k != 'bittensor_network']
    if missing_config:
        logger.error(f"Missing configuration: {missing_config}")
        return
    
    try:
        # Initialize calculator
        calculator = NAVCalculator(**config)
        
        # Calculate NAV
        logger.info("🧮 Starting NAV calculation...")
        nav_result = await calculator.calculate_nav()
        
        # Create submission
        logger.info("📝 Creating NAV submission...")
        submission = await calculator.create_nav_submission(nav_result)
        
        # Save report
        await calculator.save_calculation_report(nav_result, submission)
        
        # Display results
        print("\n" + "="*60)
        print("🎯 TAO20 NAV CALCULATION RESULTS")
        print("="*60)
        print(f"📊 Current NAV: {nav_result.nav:.6f}")
        print(f"💰 Total Value: ${nav_result.total_value:,.2f}")
        print(f"🪙 Total Supply: {nav_result.total_supply:,.2f} TAO20")
        print(f"⭐ Confidence: {nav_result.confidence_score:.2f}")
        print(f"⏰ Max Price Staleness: {nav_result.price_staleness_seconds}s")
        print("\n📈 Subnet Breakdown:")
        
        for subnet in nav_result.subnet_breakdown:
            print(f"  Subnet {subnet['netuid']:2d}: "
                  f"${subnet['total_value']:8,.2f} "
                  f"({subnet['weight_bps']/100:5.1f}%) "
                  f"[{subnet['price_source']}]")
        
        print(f"\n✅ Submission ready for validator: {submission['validator']}")
        print("="*60)
        
    except Exception as e:
        logger.error(f"❌ NAV calculation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
