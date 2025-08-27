"""
Epoch Boundary Enforcement for TAO20 Creation Unit System

Handles epoch transitions, request expiration, and automated cleanup.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from .epoch_manager import EpochManager
from .request_manager import CreationRequestManager, RequestStatus
from .delivery_tracker import DeliveryTracker, TrackingStatus

logger = logging.getLogger(__name__)

class EpochTransitionStatus(Enum):
    """Status of epoch transition"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class EpochTransitionInfo:
    """Information about epoch transition"""
    from_epoch: int
    to_epoch: int
    status: EpochTransitionStatus
    start_time: int
    end_time: Optional[int]
    expired_requests: List[str]
    error_message: Optional[str]

class EpochEnforcer:
    """
    Enforces epoch boundaries and handles epoch transitions.
    
    Manages request expiration, automated cleanup, and epoch transitions.
    """
    
    def __init__(
        self,
        epoch_manager: EpochManager,
        request_manager: CreationRequestManager,
        delivery_tracker: Optional[DeliveryTracker] = None
    ):
        """
        Initialize epoch enforcer
        
        Args:
            epoch_manager: Epoch manager
            request_manager: Request manager
            delivery_tracker: Delivery tracker (optional)
        """
        self.epoch_manager = epoch_manager
        self.request_manager = request_manager
        self.delivery_tracker = delivery_tracker
        
        self.transition_callbacks: List[Callable] = []
        self.expiration_callbacks: List[Callable] = []
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        
        logger.info("EpochEnforcer initialized")
    
    async def check_epoch_transition(self) -> Optional[EpochTransitionInfo]:
        """
        Check if epoch transition is needed
        
        Returns:
            EpochTransitionInfo if transition is needed, None otherwise
        """
        current_epoch = self.epoch_manager.get_current_epoch_id()
        current_time = int(time.time())
        
        # Check if we need to transition to a new epoch
        epoch_end = self.epoch_manager.get_epoch_end(current_epoch)
        
        if current_time >= epoch_end:
            # Epoch transition needed
            new_epoch = current_epoch + 1
            
            transition_info = EpochTransitionInfo(
                from_epoch=current_epoch,
                to_epoch=new_epoch,
                status=EpochTransitionStatus.PENDING,
                start_time=current_time,
                end_time=None,
                expired_requests=[],
                error_message=None
            )
            
            logger.info(f"Epoch transition needed: {current_epoch} -> {new_epoch}")
            return transition_info
        
        return None
    
    async def execute_epoch_transition(self, transition_info: EpochTransitionInfo) -> bool:
        """
        Execute epoch transition
        
        Args:
            transition_info: Epoch transition information
            
        Returns:
            True if transition successful
        """
        logger.info(f"Executing epoch transition: {transition_info.from_epoch} -> {transition_info.to_epoch}")
        
        transition_info.status = EpochTransitionStatus.IN_PROGRESS
        
        try:
            # 1. Expire all pending requests from old epoch
            expired_requests = await self._expire_epoch_requests(transition_info.from_epoch)
            transition_info.expired_requests = expired_requests
            
            # 2. Stop tracking expired requests
            if self.delivery_tracker:
                for request_id in expired_requests:
                    await self.delivery_tracker.stop_tracking(request_id)
            
            # 3. Clean up expired epochs
            cleaned_count = self.epoch_manager.cleanup_expired_epochs()
            
            # 4. Notify callbacks
            await self._notify_transition_callbacks(transition_info)
            
            # 5. Mark transition as completed
            transition_info.status = EpochTransitionStatus.COMPLETED
            transition_info.end_time = int(time.time())
            
            logger.info(f"Epoch transition completed: {len(expired_requests)} requests expired, {cleaned_count} epochs cleaned")
            return True
            
        except Exception as e:
            transition_info.status = EpochTransitionStatus.FAILED
            transition_info.error_message = str(e)
            transition_info.end_time = int(time.time())
            
            logger.error(f"Epoch transition failed: {e}")
            return False
    
    async def _expire_epoch_requests(self, epoch_id: int) -> List[str]:
        """
        Expire all pending requests for an epoch
        
        Args:
            epoch_id: Epoch ID to expire requests for
            
        Returns:
            List of expired request IDs
        """
        expired_requests = []
        
        # Get all pending requests for the epoch
        pending_requests = self.request_manager.get_requests_by_status(RequestStatus.PENDING)
        
        for request in pending_requests:
            if request.epoch_id == epoch_id:
                # Mark request as expired
                self.request_manager.mark_request_expired(
                    request.request_id, 
                    f"Request expired due to epoch {epoch_id} transition"
                )
                expired_requests.append(request.request_id)
                
                # Notify expiration callbacks
                await self._notify_expiration_callbacks(request.request_id, request)
        
        logger.info(f"Expired {len(expired_requests)} requests for epoch {epoch_id}")
        return expired_requests
    
    async def _notify_transition_callbacks(self, transition_info: EpochTransitionInfo):
        """
        Notify transition callbacks
        
        Args:
            transition_info: Epoch transition information
        """
        for callback in self.transition_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(transition_info)
                else:
                    callback(transition_info)
            except Exception as e:
                logger.error(f"Transition callback error: {e}")
    
    async def _notify_expiration_callbacks(self, request_id: str, request):
        """
        Notify expiration callbacks
        
        Args:
            request_id: Request ID
            request: Request object
        """
        for callback in self.expiration_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(request_id, request)
                else:
                    callback(request_id, request)
            except Exception as e:
                logger.error(f"Expiration callback error: {e}")
    
    def add_transition_callback(self, callback: Callable):
        """
        Add epoch transition callback
        
        Args:
            callback: Callback function to call on epoch transition
        """
        self.transition_callbacks.append(callback)
        logger.info("Added epoch transition callback")
    
    def add_expiration_callback(self, callback: Callable):
        """
        Add request expiration callback
        
        Args:
            callback: Callback function to call on request expiration
        """
        self.expiration_callbacks.append(callback)
        logger.info("Added request expiration callback")
    
    async def start_monitoring(self, interval_seconds: int = 60):
        """
        Start epoch monitoring
        
        Args:
            interval_seconds: Monitoring interval in seconds
        """
        if self.is_monitoring:
            logger.warning("Epoch monitoring already started")
            return
        
        self.is_monitoring = True
        logger.info(f"Starting epoch monitoring with {interval_seconds}s interval")
        
        self.monitoring_task = asyncio.create_task(
            self._monitor_epochs(interval_seconds)
        )
    
    async def stop_monitoring(self):
        """Stop epoch monitoring"""
        if not self.is_monitoring:
            logger.warning("Epoch monitoring not started")
            return
        
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped epoch monitoring")
    
    async def _monitor_epochs(self, interval_seconds: int):
        """
        Monitor epochs for transitions
        
        Args:
            interval_seconds: Monitoring interval in seconds
        """
        while self.is_monitoring:
            try:
                # Check for epoch transition
                transition_info = await self.check_epoch_transition()
                
                if transition_info:
                    # Execute transition
                    success = await self.execute_epoch_transition(transition_info)
                    
                    if not success:
                        logger.error("Epoch transition failed")
                
                # Wait for next check
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in epoch monitoring: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def force_epoch_transition(self, target_epoch: int) -> bool:
        """
        Force transition to a specific epoch (for testing)
        
        Args:
            target_epoch: Target epoch ID
            
        Returns:
            True if transition successful
        """
        current_epoch = self.epoch_manager.get_current_epoch_id()
        
        if target_epoch <= current_epoch:
            logger.warning(f"Cannot transition to epoch {target_epoch} (current: {current_epoch})")
            return False
        
        transition_info = EpochTransitionInfo(
            from_epoch=current_epoch,
            to_epoch=target_epoch,
            status=EpochTransitionStatus.PENDING,
            start_time=int(time.time()),
            end_time=None,
            expired_requests=[],
            error_message=None
        )
        
        logger.info(f"Forcing epoch transition to {target_epoch}")
        return await self.execute_epoch_transition(transition_info)
    
    def get_epoch_statistics(self) -> Dict:
        """
        Get epoch statistics
        
        Returns:
            Dictionary with epoch statistics
        """
        current_epoch = self.epoch_manager.get_current_epoch_id()
        current_time = int(time.time())
        
        # Calculate time until next epoch
        epoch_end = self.epoch_manager.get_epoch_end(current_epoch)
        time_until_next = max(0, epoch_end - current_time)
        
        # Get request statistics by epoch
        request_stats = {}
        for status in RequestStatus:
            requests = self.request_manager.get_requests_by_status(status)
            for request in requests:
                epoch = request.epoch_id
                if epoch not in request_stats:
                    request_stats[epoch] = {}
                if status.value not in request_stats[epoch]:
                    request_stats[epoch][status.value] = 0
                request_stats[epoch][status.value] += 1
        
        stats = {
            'current_epoch': current_epoch,
            'time_until_next_epoch': time_until_next,
            'epoch_progress_percent': ((current_time - self.epoch_manager.get_epoch_start(current_epoch)) / 1209600) * 100,
            'request_stats_by_epoch': request_stats,
            'is_monitoring': self.is_monitoring,
            'transition_callbacks_count': len(self.transition_callbacks),
            'expiration_callbacks_count': len(self.expiration_callbacks)
        }
        
        return stats
    
    async def cleanup_expired_requests(self) -> int:
        """
        Clean up expired requests
        
        Returns:
            Number of requests cleaned up
        """
        # Clean up expired requests in request manager
        cleaned_count = self.request_manager.cleanup_expired_requests()
        
        # Clean up completed tracking
        if self.delivery_tracker:
            tracking_cleaned = await self.delivery_tracker.cleanup_completed_tracking()
            cleaned_count += tracking_cleaned
        
        logger.info(f"Cleaned up {cleaned_count} expired/completed items")
        return cleaned_count

class EpochEnforcerFactory:
    """Factory for creating epoch enforcers with different configurations"""
    
    @staticmethod
    def create_standard_enforcer(
        epoch_manager: EpochManager,
        request_manager: CreationRequestManager,
        delivery_tracker: Optional[DeliveryTracker] = None
    ) -> EpochEnforcer:
        """Create a standard epoch enforcer"""
        return EpochEnforcer(epoch_manager, request_manager, delivery_tracker)
    
    @staticmethod
    def create_aggressive_enforcer(
        epoch_manager: EpochManager,
        request_manager: CreationRequestManager,
        delivery_tracker: Optional[DeliveryTracker] = None
    ) -> EpochEnforcer:
        """Create an aggressive enforcer with shorter monitoring intervals"""
        enforcer = EpochEnforcer(epoch_manager, request_manager, delivery_tracker)
        # Could add additional configuration here
        return enforcer
