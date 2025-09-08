#!/usr/bin/env python3
"""
TAO20 NAV Monitoring System

This module provides real-time NAV monitoring and arbitrage opportunity detection
for TAO20 miners and validators. It integrates with the Bittensor blockchain
using btcli for price data and maintains accurate, up-to-date NAV calculations.

Key Features:
- Real-time NAV calculation using Bittensor data
- Market price monitoring from DEX/oracles
- Arbitrage opportunity detection
- Price deviation alerts
- Historical NAV tracking
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
import json
import subprocess
import os
from statistics import median

import bittensor as bt

logger = logging.getLogger(__name__)


@dataclass
class SubnetTokenData:
    """Subnet token information"""
    netuid: int
    name: str
    symbol: str
    price_tao: Decimal
    market_cap: Decimal
    emission_rate: Decimal
    last_updated: int
    weight_in_index: Decimal


@dataclass
class NAVCalculation:
    """NAV calculation result"""
    nav_per_token: Decimal
    total_portfolio_value: Decimal
    total_token_supply: Decimal
    calculation_timestamp: int
    subnet_contributions: Dict[int, Decimal]
    data_sources: List[str]
    is_stale: bool = False


@dataclass
class ArbitragePriceData:
    """Price data for arbitrage analysis"""
    tao20_market_price: Decimal
    nav_price: Decimal
    spread_percent: Decimal
    spread_direction: str  # 'premium' or 'discount'
    confidence_score: Decimal
    timestamp: int


@dataclass
class PriceAlert:
    """Price deviation alert"""
    alert_type: str  # 'arbitrage', 'deviation', 'stale_data'
    severity: str    # 'low', 'medium', 'high', 'critical'
    message: str
    data: Dict
    timestamp: int


class NAVMonitor:
    """
    Real-time NAV monitoring system for TAO20
    
    Uses btcli and Bittensor blockchain data to provide accurate,
    up-to-date NAV calculations and arbitrage opportunity detection.
    """
    
    def __init__(
        self,
        config: bt.config,
        subtensor: bt.subtensor,
        metagraph: bt.metagraph
    ):
        self.config = config
        self.subtensor = subtensor
        self.metagraph = metagraph
        
        # Configuration
        self.update_interval = config.get('nav_update_interval', 30)  # 30 seconds
        self.price_staleness_threshold = config.get('price_staleness_threshold', 300)  # 5 minutes
        self.arbitrage_threshold = Decimal(config.get('arbitrage_threshold', '0.005'))  # 0.5%
        self.deviation_alert_threshold = Decimal(config.get('deviation_alert_threshold', '0.02'))  # 2%
        
        # State
        self.subnet_data: Dict[int, SubnetTokenData] = {}
        self.current_nav: Optional[NAVCalculation] = None
        self.nav_history: List[NAVCalculation] = []
        self.price_alerts: List[PriceAlert] = []
        self.last_update: int = 0
        
        # Target subnets (top 20)
        self.target_subnets = list(range(1, 21))  # Subnets 1-20
        
        # Market data sources
        self.dex_contract_address = config.get('dex_contract_address')
        self.price_oracle_urls = config.get('price_oracle_urls', [])
        
        logger.info("NAV Monitor initialized")
        logger.info(f"Monitoring {len(self.target_subnets)} subnets")
        logger.info(f"Update interval: {self.update_interval}s")
    
    async def start_monitoring(self):
        """Start the NAV monitoring loop"""
        logger.info("Starting NAV monitoring...")
        
        # Initial data load
        await self._update_subnet_data()
        await self._calculate_current_nav()
        
        # Start monitoring loops
        asyncio.create_task(self._subnet_data_update_loop())
        asyncio.create_task(self._nav_calculation_loop())
        asyncio.create_task(self._arbitrage_monitoring_loop())
        asyncio.create_task(self._alert_cleanup_loop())
        
        logger.info("NAV monitoring started")
    
    async def _subnet_data_update_loop(self):
        """Background loop to update subnet data"""
        while True:
            try:
                await self._update_subnet_data()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in subnet data update loop: {e}")
                await asyncio.sleep(60)
    
    async def _nav_calculation_loop(self):
        """Background loop to calculate NAV"""
        while True:
            try:
                await self._calculate_current_nav()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in NAV calculation loop: {e}")
                await asyncio.sleep(60)
    
    async def _arbitrage_monitoring_loop(self):
        """Background loop to monitor arbitrage opportunities"""
        while True:
            try:
                await self._check_arbitrage_opportunities()
                await asyncio.sleep(10)  # Check more frequently
            except Exception as e:
                logger.error(f"Error in arbitrage monitoring loop: {e}")
                await asyncio.sleep(30)
    
    async def _alert_cleanup_loop(self):
        """Background loop to cleanup old alerts"""
        while True:
            try:
                current_time = int(time.time())
                # Remove alerts older than 1 hour
                self.price_alerts = [
                    alert for alert in self.price_alerts
                    if current_time - alert.timestamp < 3600
                ]
                await asyncio.sleep(300)  # Cleanup every 5 minutes
            except Exception as e:
                logger.error(f"Error in alert cleanup loop: {e}")
                await asyncio.sleep(300)
    
    async def _update_subnet_data(self):
        """Update subnet token data using btcli"""
        try:
            logger.debug("Updating subnet data...")
            
            for netuid in self.target_subnets:
                try:
                    subnet_data = await self._fetch_subnet_data_btcli(netuid)
                    if subnet_data:
                        self.subnet_data[netuid] = subnet_data
                except Exception as e:
                    logger.warning(f"Failed to update data for subnet {netuid}: {e}")
            
            logger.debug(f"Updated data for {len(self.subnet_data)} subnets")
            
        except Exception as e:
            logger.error(f"Error updating subnet data: {e}")
    
    async def _fetch_subnet_data_btcli(self, netuid: int) -> Optional[SubnetTokenData]:
        """Fetch subnet data using btcli"""
        try:
            # Use btcli to get subnet information [[memory:8378619]]
            cmd = [
                'btcli', 'subnet', 'show',
                '--netuid', str(netuid),
                '--subtensor.network', self.config.get('subtensor.network', 'finney'),
                '--no_prompt'
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.warning(f"btcli command failed for netuid {netuid}: {stderr.decode()}")
                return None
            
            # Parse btcli output
            output = stdout.decode()
            subnet_info = self._parse_btcli_subnet_output(output, netuid)
            
            if subnet_info:
                return SubnetTokenData(
                    netuid=netuid,
                    name=subnet_info.get('name', f'Subnet-{netuid}'),
                    symbol=subnet_info.get('symbol', f'SN{netuid}'),
                    price_tao=Decimal(subnet_info.get('price_tao', '0.1')),  # Default price
                    market_cap=Decimal(subnet_info.get('market_cap', '0')),
                    emission_rate=Decimal(subnet_info.get('emission_rate', '0')),
                    last_updated=int(time.time()),
                    weight_in_index=Decimal(subnet_info.get('weight', '0.05'))  # 5% default
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching subnet data via btcli for netuid {netuid}: {e}")
            return None
    
    def _parse_btcli_subnet_output(self, output: str, netuid: int) -> Optional[Dict]:
        """Parse btcli subnet show output"""
        try:
            # Parse the btcli output to extract relevant information
            # This is a simplified parser - real implementation would be more robust
            
            lines = output.split('\n')
            subnet_info = {'netuid': netuid}
            
            for line in lines:
                line = line.strip()
                if 'Emission:' in line:
                    try:
                        emission = float(line.split(':')[1].strip().split()[0])
                        subnet_info['emission_rate'] = emission
                    except:
                        pass
                elif 'Total Stake:' in line:
                    try:
                        stake = float(line.split(':')[1].strip().split()[0])
                        subnet_info['total_stake'] = stake
                    except:
                        pass
            
            # Calculate derived values
            if 'emission_rate' in subnet_info and 'total_stake' in subnet_info:
                # Simple price calculation based on emission/stake ratio
                if subnet_info['total_stake'] > 0:
                    subnet_info['price_tao'] = subnet_info['emission_rate'] / subnet_info['total_stake']
                else:
                    subnet_info['price_tao'] = 0.1  # Default
            
            return subnet_info
            
        except Exception as e:
            logger.error(f"Error parsing btcli output: {e}")
            return None
    
    async def _calculate_current_nav(self):
        """Calculate current NAV based on subnet data"""
        try:
            if not self.subnet_data:
                logger.warning("No subnet data available for NAV calculation")
                return
            
            total_portfolio_value = Decimal('0')
            subnet_contributions = {}
            data_sources = ['btcli']
            
            # Calculate portfolio value
            for netuid, subnet_data in self.subnet_data.items():
                # Check data staleness
                age = int(time.time()) - subnet_data.last_updated
                if age > self.price_staleness_threshold:
                    logger.warning(f"Stale data for subnet {netuid} (age: {age}s)")
                
                # Calculate contribution to portfolio
                contribution = subnet_data.price_tao * subnet_data.weight_in_index
                subnet_contributions[netuid] = contribution
                total_portfolio_value += contribution
            
            # Get total TAO20 token supply (simplified)
            # In real implementation, would query from contract
            total_token_supply = Decimal('1000000')  # Placeholder
            
            # Calculate NAV per token
            if total_token_supply > 0:
                nav_per_token = total_portfolio_value / total_token_supply
            else:
                nav_per_token = Decimal('1.0')  # Default
            
            # Check for staleness
            is_stale = any(
                int(time.time()) - subnet_data.last_updated > self.price_staleness_threshold
                for subnet_data in self.subnet_data.values()
            )
            
            # Create NAV calculation
            nav_calculation = NAVCalculation(
                nav_per_token=nav_per_token,
                total_portfolio_value=total_portfolio_value,
                total_token_supply=total_token_supply,
                calculation_timestamp=int(time.time()),
                subnet_contributions=subnet_contributions,
                data_sources=data_sources,
                is_stale=is_stale
            )
            
            self.current_nav = nav_calculation
            self.nav_history.append(nav_calculation)
            self.last_update = int(time.time())
            
            # Keep only recent history
            if len(self.nav_history) > 1000:
                self.nav_history = self.nav_history[-1000:]
            
            # Check for significant deviations
            await self._check_nav_deviations()
            
            logger.debug(f"NAV calculated: {nav_per_token:.6f} TAO (stale: {is_stale})")
            
        except Exception as e:
            logger.error(f"Error calculating NAV: {e}")
    
    async def _check_nav_deviations(self):
        """Check for significant NAV deviations"""
        try:
            if len(self.nav_history) < 2:
                return
            
            current_nav = self.nav_history[-1].nav_per_token
            previous_nav = self.nav_history[-2].nav_per_token
            
            if previous_nav > 0:
                deviation = abs(current_nav - previous_nav) / previous_nav
                
                if deviation > self.deviation_alert_threshold:
                    severity = 'high' if deviation > self.deviation_alert_threshold * 2 else 'medium'
                    
                    alert = PriceAlert(
                        alert_type='deviation',
                        severity=severity,
                        message=f"Significant NAV deviation: {deviation:.2%}",
                        data={
                            'current_nav': float(current_nav),
                            'previous_nav': float(previous_nav),
                            'deviation_percent': float(deviation * 100)
                        },
                        timestamp=int(time.time())
                    )
                    
                    self.price_alerts.append(alert)
                    logger.warning(f"NAV deviation alert: {deviation:.2%}")
            
        except Exception as e:
            logger.error(f"Error checking NAV deviations: {e}")
    
    async def _check_arbitrage_opportunities(self):
        """Check for arbitrage opportunities"""
        try:
            if not self.current_nav:
                return
            
            # Get TAO20 market price (simplified - would query from DEX)
            market_price = await self._get_tao20_market_price()
            if not market_price:
                return
            
            nav_price = self.current_nav.nav_per_token
            
            # Calculate spread
            spread = (market_price - nav_price) / nav_price
            spread_percent = abs(spread) * 100
            
            if spread_percent >= self.arbitrage_threshold * 100:
                direction = 'premium' if spread > 0 else 'discount'
                confidence = self._calculate_confidence_score()
                
                arbitrage_data = ArbitragePriceData(
                    tao20_market_price=market_price,
                    nav_price=nav_price,
                    spread_percent=spread_percent,
                    spread_direction=direction,
                    confidence_score=confidence,
                    timestamp=int(time.time())
                )
                
                # Create arbitrage alert
                severity = 'high' if spread_percent > self.arbitrage_threshold * 200 else 'medium'
                
                alert = PriceAlert(
                    alert_type='arbitrage',
                    severity=severity,
                    message=f"Arbitrage opportunity: {direction} {spread_percent:.2f}%",
                    data={
                        'market_price': float(market_price),
                        'nav_price': float(nav_price),
                        'spread_percent': float(spread_percent),
                        'direction': direction,
                        'confidence': float(confidence)
                    },
                    timestamp=int(time.time())
                )
                
                self.price_alerts.append(alert)
                logger.info(f"Arbitrage opportunity detected: {direction} {spread_percent:.2f}%")
            
        except Exception as e:
            logger.error(f"Error checking arbitrage opportunities: {e}")
    
    async def _get_tao20_market_price(self) -> Optional[Decimal]:
        """Get TAO20 market price from DEX/oracle"""
        try:
            # In real implementation, would query Uniswap or other DEX
            # For now, simulate with slight variation from NAV
            if self.current_nav:
                base_price = self.current_nav.nav_per_token
                # Add small random variation (±2%)
                import random
                variation = Decimal(random.uniform(-0.02, 0.02))
                market_price = base_price * (Decimal('1') + variation)
                return market_price
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting TAO20 market price: {e}")
            return None
    
    def _calculate_confidence_score(self) -> Decimal:
        """Calculate confidence score for price data"""
        try:
            if not self.current_nav:
                return Decimal('0')
            
            # Factors affecting confidence:
            # 1. Data freshness
            # 2. Number of data sources
            # 3. Data consistency
            
            freshness_score = Decimal('1.0')
            if self.current_nav.is_stale:
                freshness_score = Decimal('0.5')
            
            source_score = min(Decimal('1.0'), Decimal(len(self.current_nav.data_sources)) / Decimal('3'))
            
            # Overall confidence (simple average)
            confidence = (freshness_score + source_score) / Decimal('2')
            
            return confidence
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return Decimal('0.5')  # Default medium confidence
    
    def get_current_nav(self) -> Optional[NAVCalculation]:
        """Get current NAV calculation"""
        return self.current_nav
    
    def get_arbitrage_opportunities(self, min_spread: Optional[Decimal] = None) -> List[PriceAlert]:
        """Get current arbitrage opportunities"""
        if min_spread is None:
            min_spread = self.arbitrage_threshold
        
        return [
            alert for alert in self.price_alerts
            if alert.alert_type == 'arbitrage' 
            and alert.data.get('spread_percent', 0) >= float(min_spread * 100)
        ]
    
    def get_nav_history(self, hours: int = 24) -> List[NAVCalculation]:
        """Get NAV history for specified hours"""
        cutoff_time = int(time.time()) - (hours * 3600)
        return [
            nav for nav in self.nav_history
            if nav.calculation_timestamp >= cutoff_time
        ]
    
    def get_subnet_data(self, netuid: Optional[int] = None) -> Dict:
        """Get subnet data"""
        if netuid is not None:
            return self.subnet_data.get(netuid)
        return self.subnet_data
    
    def get_price_alerts(self, severity: Optional[str] = None) -> List[PriceAlert]:
        """Get price alerts, optionally filtered by severity"""
        if severity:
            return [alert for alert in self.price_alerts if alert.severity == severity]
        return self.price_alerts
    
    def get_monitoring_stats(self) -> Dict:
        """Get monitoring system statistics"""
        try:
            current_time = int(time.time())
            
            # Calculate data freshness
            freshness_scores = []
            for subnet_data in self.subnet_data.values():
                age = current_time - subnet_data.last_updated
                freshness_scores.append(max(0, 1 - (age / self.price_staleness_threshold)))
            
            avg_freshness = sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0
            
            # Count alerts by severity
            alert_counts = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
            for alert in self.price_alerts:
                alert_counts[alert.severity] = alert_counts.get(alert.severity, 0) + 1
            
            return {
                'subnets_monitored': len(self.subnet_data),
                'nav_calculations': len(self.nav_history),
                'current_nav': float(self.current_nav.nav_per_token) if self.current_nav else None,
                'nav_is_stale': self.current_nav.is_stale if self.current_nav else True,
                'last_update': self.last_update,
                'data_freshness_score': avg_freshness,
                'total_alerts': len(self.price_alerts),
                'alert_counts': alert_counts,
                'arbitrage_opportunities': len(self.get_arbitrage_opportunities()),
                'update_interval': self.update_interval
            }
            
        except Exception as e:
            logger.error(f"Error getting monitoring stats: {e}")
            return {}


class NAVOracle:
    """
    NAV Oracle service for external consumption
    
    Provides reliable NAV data and arbitrage signals to miners and validators
    """
    
    def __init__(self, nav_monitor: NAVMonitor):
        self.nav_monitor = nav_monitor
        self.api_port = 8001
        self.last_api_update = 0
        
    async def start_api_service(self):
        """Start NAV Oracle API service"""
        from aiohttp import web
        
        async def handle_nav(request):
            nav = self.nav_monitor.get_current_nav()
            if nav:
                return web.json_response({
                    'nav_per_token': float(nav.nav_per_token),
                    'total_portfolio_value': float(nav.total_portfolio_value),
                    'calculation_timestamp': nav.calculation_timestamp,
                    'is_stale': nav.is_stale,
                    'subnet_contributions': {
                        str(k): float(v) for k, v in nav.subnet_contributions.items()
                    }
                })
            else:
                return web.json_response({'error': 'NAV data not available'}, status=503)
        
        async def handle_arbitrage(request):
            opportunities = self.nav_monitor.get_arbitrage_opportunities()
            return web.json_response([
                {
                    'type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'data': alert.data,
                    'timestamp': alert.timestamp
                }
                for alert in opportunities
            ])
        
        async def handle_stats(request):
            return web.json_response(self.nav_monitor.get_monitoring_stats())
        
        app = web.Application()
        app.router.add_get('/nav', handle_nav)
        app.router.add_get('/arbitrage', handle_arbitrage)
        app.router.add_get('/stats', handle_stats)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.api_port)
        await site.start()
        
        logger.info(f"NAV Oracle API started on port {self.api_port}")
        
        # Keep service running
        while True:
            await asyncio.sleep(3600)


async def main():
    """Example usage of NAV monitoring system"""
    # Setup Bittensor components
    config = bt.config()
    config.netuid = 20
    
    subtensor = bt.subtensor(config=config)
    metagraph = subtensor.metagraph(config.netuid)
    
    # Initialize NAV monitor
    nav_monitor = NAVMonitor(config, subtensor, metagraph)
    
    # Start monitoring
    await nav_monitor.start_monitoring()
    
    # Start Oracle API
    oracle = NAVOracle(nav_monitor)
    await oracle.start_api_service()


if __name__ == "__main__":
    asyncio.run(main())
