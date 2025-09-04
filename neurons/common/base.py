#!/usr/bin/env python3
"""
Common base functionality for TAO20 miners and validators
Eliminates code duplication and provides clean abstractions
"""

import os
import logging
from typing import Optional
import bittensor as bt

logger = logging.getLogger(__name__)

class TAO20Base:
    """Base class for TAO20 miners and validators with common functionality"""
    
    def __init__(
        self,
        wallet_path: str,
        participant_id: str,
        bittensor_network: str = "finney"
    ):
        self.participant_id = participant_id
        
        # Initialize Bittensor wallet - single point of failure
        self.bt_wallet = bt.wallet(path=wallet_path)
        self.hotkey_ss58 = self.bt_wallet.hotkey.ss58_address
        
        # Initialize Bittensor connection
        self.subtensor = bt.subtensor(network=bittensor_network)
        
        # Simple metrics - no external dependencies
        self.metrics = {
            'operations_completed': 0,
            'operations_failed': 0,
            'last_operation_time': 0
        }
        
        logger.info(f"TAO20 {self.__class__.__name__} initialized: {participant_id}")
    
    def increment_metric(self, metric_name: str, value: int = 1):
        """Simple metric tracking"""
        if metric_name in self.metrics:
            self.metrics[metric_name] += value
    
    def get_metrics(self) -> dict:
        """Return current metrics"""
        return self.metrics.copy()
