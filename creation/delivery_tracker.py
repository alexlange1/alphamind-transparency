"""
Delivery Tracker for TAO20 Creation Unit System

Monitors and tracks basket delivery status and progress.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from .request_manager import CreationRequestManager, RequestStatus
from .basket_validator import BasketValidator
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'vault'))
from substrate_vault import SubstrateVaultManager, DeliveryStatus, DeliveryTransaction

logger = logging.getLogger(__name__)

class TrackingStatus(Enum):
    """Status of delivery tracking"""
    TRACKING = "tracking"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class DeliveryTrackingInfo:
    """Information about delivery tracking"""
    request_id: str
    tracking_status: TrackingStatus
    start_time: int
    end_time: Optional[int]
    delivery_tx: Optional[DeliveryTransaction]
    validation_result: Optional[Dict]
    error_message: Optional[str]

class DeliveryTracker:
    """
    Tracks basket delivery progress and status.
    
    Monitors delivery transactions and validates basket delivery.
    """
    
    def __init__(
        self,
        request_manager: CreationRequestManager,
        vault_manager: SubstrateVaultManager,
        basket_validator: Optional[BasketValidator] = None
    ):
        """
        Initialize delivery tracker
        
        Args:
            request_manager: Creation request manager
            vault_manager: Substrate vault manager
            basket_validator: Basket validator (optional)
        """
        self.request_manager = request_manager
        self.vault_manager = vault_manager
        self.basket_validator = basket_validator or BasketValidator()
        
        self.tracking_info: Dict[str, DeliveryTrackingInfo] = {}
        self.tracking_callbacks: Dict[str, List[Callable]] = {}
        self.tracking_timeout = 3600  # 1 hour default timeout
        
        logger.info("DeliveryTracker initialized")
    
    async def start_tracking(
        self, 
        request_id: str,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Start tracking delivery for a request
        
        Args:
            request_id: Request ID to track
            callback: Optional callback function for status updates
            
        Returns:
            True if tracking started successfully
        """
        # Check if request exists
        request = self.request_manager.get_creation_request(request_id)
        if not request:
            logger.error(f"Request {request_id} not found for tracking")
            return False
        
        # Check if already tracking
        if request_id in self.tracking_info:
            logger.warning(f"Already tracking request {request_id}")
            return True
        
        # Initialize tracking info
        tracking_info = DeliveryTrackingInfo(
            request_id=request_id,
            tracking_status=TrackingStatus.TRACKING,
            start_time=int(time.time()),
            end_time=None,
            delivery_tx=None,
            validation_result=None,
            error_message=None
        )
        
        self.tracking_info[request_id] = tracking_info
        
        # Register callback
        if callback:
            if request_id not in self.tracking_callbacks:
                self.tracking_callbacks[request_id] = []
            self.tracking_callbacks[request_id].append(callback)
        
        logger.info(f"Started tracking delivery for request {request_id}")
        return True
    
    async def stop_tracking(self, request_id: str) -> bool:
        """
        Stop tracking delivery for a request
        
        Args:
            request_id: Request ID to stop tracking
            
        Returns:
            True if tracking stopped successfully
        """
        if request_id not in self.tracking_info:
            logger.warning(f"Not tracking request {request_id}")
            return False
        
        # Update tracking info
        tracking_info = self.tracking_info[request_id]
        tracking_info.end_time = int(time.time())
        
        # Remove from tracking
        del self.tracking_info[request_id]
        
        # Remove callbacks
        if request_id in self.tracking_callbacks:
            del self.tracking_callbacks[request_id]
        
        logger.info(f"Stopped tracking delivery for request {request_id}")
        return True
    
    async def track_delivery_progress(self, request_id: str) -> Optional[Dict]:
        """
        Track delivery progress for a request
        
        Args:
            request_id: Request ID to track
            
        Returns:
            Progress information or None if not tracking
        """
        if request_id not in self.tracking_info:
            return None
        
        tracking_info = self.tracking_info[request_id]
        request = self.request_manager.get_creation_request(request_id)
        
        if not request:
            return None
        
        # Check if delivery has been recorded
        if request.status == RequestStatus.DELIVERED and request.receipt_block:
            # Delivery completed, validate basket
            await self._validate_delivered_basket(request_id, request)
            return self._get_progress_info(tracking_info, request)
        
        # Check for timeout
        elapsed_time = int(time.time()) - tracking_info.start_time
        if elapsed_time > self.tracking_timeout:
            await self._handle_tracking_timeout(request_id)
            return self._get_progress_info(tracking_info, request)
        
        # Still tracking
        return self._get_progress_info(tracking_info, request)
    
    async def _validate_delivered_basket(self, request_id: str, request):
        """
        Validate delivered basket
        
        Args:
            request_id: Request ID
            request: Creation request
        """
        tracking_info = self.tracking_info[request_id]
        
        try:
            # Get required basket
            required_basket = self.request_manager.get_required_basket_for_request(request_id)
            
            # Validate delivered basket
            validation_result = self.basket_validator.validate_all_or_nothing(
                required_basket, request.basket_totals
            )
            
            tracking_info.validation_result = self.basket_validator.get_validation_summary(validation_result)
            
            if validation_result.is_valid:
                tracking_info.tracking_status = TrackingStatus.COMPLETED
                logger.info(f"Basket validation passed for request {request_id}")
            else:
                tracking_info.tracking_status = TrackingStatus.FAILED
                tracking_info.error_message = f"Basket validation failed: {validation_result.errors}"
                logger.error(f"Basket validation failed for request {request_id}: {validation_result.errors}")
            
            # Notify callbacks
            await self._notify_callbacks(request_id, tracking_info)
            
        except Exception as e:
            tracking_info.tracking_status = TrackingStatus.FAILED
            tracking_info.error_message = f"Validation error: {str(e)}"
            logger.error(f"Basket validation error for request {request_id}: {e}")
    
    async def _handle_tracking_timeout(self, request_id: str):
        """
        Handle tracking timeout
        
        Args:
            request_id: Request ID
        """
        tracking_info = self.tracking_info[request_id]
        tracking_info.tracking_status = TrackingStatus.TIMEOUT
        tracking_info.error_message = "Tracking timeout"
        
        logger.warning(f"Tracking timeout for request {request_id}")
        
        # Notify callbacks
        await self._notify_callbacks(request_id, tracking_info)
    
    def _get_progress_info(self, tracking_info: DeliveryTrackingInfo, request) -> Dict:
        """
        Get progress information
        
        Args:
            tracking_info: Tracking information
            request: Creation request
            
        Returns:
            Progress information dictionary
        """
        elapsed_time = int(time.time()) - tracking_info.start_time
        
        progress_info = {
            'request_id': tracking_info.request_id,
            'tracking_status': tracking_info.tracking_status.value,
            'elapsed_time': elapsed_time,
            'request_status': request.status.value,
            'has_basket_totals': request.basket_totals is not None,
            'has_receipt_block': request.receipt_block is not None,
            'validation_result': tracking_info.validation_result,
            'error_message': tracking_info.error_message
        }
        
        if request.basket_totals:
            progress_info['basket_assets_count'] = len(request.basket_totals)
        
        return progress_info
    
    async def _notify_callbacks(self, request_id: str, tracking_info: DeliveryTrackingInfo):
        """
        Notify registered callbacks
        
        Args:
            request_id: Request ID
            tracking_info: Tracking information
        """
        if request_id not in self.tracking_callbacks:
            return
        
        callbacks = self.tracking_callbacks[request_id]
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(request_id, tracking_info)
                else:
                    callback(request_id, tracking_info)
            except Exception as e:
                logger.error(f"Callback error for request {request_id}: {e}")
    
    async def get_tracking_status(self, request_id: str) -> Optional[TrackingStatus]:
        """
        Get tracking status for a request
        
        Args:
            request_id: Request ID
            
        Returns:
            Tracking status or None if not tracking
        """
        if request_id not in self.tracking_info:
            return None
        
        return self.tracking_info[request_id].tracking_status
    
    def get_all_tracking_info(self) -> List[DeliveryTrackingInfo]:
        """
        Get all tracking information
        
        Returns:
            List of all tracking information
        """
        return list(self.tracking_info.values())
    
    def get_tracking_statistics(self) -> Dict:
        """
        Get tracking statistics
        
        Returns:
            Dictionary with tracking statistics
        """
        total_tracking = len(self.tracking_info)
        
        stats = {
            'total_tracking': total_tracking,
            'tracking': len([t for t in self.tracking_info.values() if t.tracking_status == TrackingStatus.TRACKING]),
            'completed': len([t for t in self.tracking_info.values() if t.tracking_status == TrackingStatus.COMPLETED]),
            'failed': len([t for t in self.tracking_info.values() if t.tracking_status == TrackingStatus.FAILED]),
            'timeout': len([t for t in self.tracking_info.values() if t.tracking_status == TrackingStatus.TIMEOUT]),
        }
        
        if total_tracking > 0:
            stats['completion_rate'] = stats['completed'] / total_tracking
            stats['failure_rate'] = (stats['failed'] + stats['timeout']) / total_tracking
        else:
            stats['completion_rate'] = 0.0
            stats['failure_rate'] = 0.0
        
        return stats
    
    async def cleanup_completed_tracking(self) -> int:
        """
        Clean up completed tracking entries
        
        Returns:
            Number of entries cleaned up
        """
        completed_requests = []
        
        for request_id, tracking_info in self.tracking_info.items():
            if tracking_info.tracking_status in [TrackingStatus.COMPLETED, TrackingStatus.FAILED, TrackingStatus.TIMEOUT]:
                completed_requests.append(request_id)
        
        for request_id in completed_requests:
            await self.stop_tracking(request_id)
        
        logger.info(f"Cleaned up {len(completed_requests)} completed tracking entries")
        return len(completed_requests)
    
    async def monitor_deliveries(self, interval_seconds: int = 30):
        """
        Monitor all tracked deliveries
        
        Args:
            interval_seconds: Monitoring interval in seconds
        """
        logger.info(f"Starting delivery monitoring with {interval_seconds}s interval")
        
        while True:
            try:
                # Track progress for all active tracking
                for request_id in list(self.tracking_info.keys()):
                    await self.track_delivery_progress(request_id)
                
                # Clean up completed tracking
                await self.cleanup_completed_tracking()
                
                # Wait for next interval
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in delivery monitoring: {e}")
                await asyncio.sleep(interval_seconds)

class DeliveryTrackerFactory:
    """Factory for creating delivery trackers with different configurations"""
    
    @staticmethod
    def create_standard_tracker(
        request_manager: CreationRequestManager,
        vault_manager: SubstrateVaultManager
    ) -> DeliveryTracker:
        """Create a standard delivery tracker"""
        return DeliveryTracker(request_manager, vault_manager)
    
    @staticmethod
    def create_strict_tracker(
        request_manager: CreationRequestManager,
        vault_manager: SubstrateVaultManager
    ) -> DeliveryTracker:
        """Create a strict delivery tracker with tight validation"""
        basket_validator = BasketValidator(tolerance_bps=1)
        return DeliveryTracker(request_manager, vault_manager, basket_validator)
    
    @staticmethod
    def create_relaxed_tracker(
        request_manager: CreationRequestManager,
        vault_manager: SubstrateVaultManager
    ) -> DeliveryTracker:
        """Create a relaxed delivery tracker with loose validation"""
        basket_validator = BasketValidator(tolerance_bps=10)
        return DeliveryTracker(request_manager, vault_manager, basket_validator)
