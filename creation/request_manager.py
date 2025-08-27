"""
Creation Request Manager for TAO20 Creation Unit System

Handles creation request lifecycle, validation, and basket specifications.
"""

import time
import hashlib
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from .epoch_manager import EpochManager, CreationFile

logger = logging.getLogger(__name__)

class RequestStatus(Enum):
    """Status of a creation request"""
    PENDING = "pending"
    DELIVERED = "delivered"
    ATTESTED = "attested"
    MINTED = "minted"
    EXPIRED = "expired"
    FAILED = "failed"

@dataclass
class CreationRequest:
    """Represents a creation request"""
    request_id: str
    epoch_id: int
    creation_size: int  # Number of creation units
    miner_hotkey: str
    submitted_at: int
    expires_at: int
    status: RequestStatus
    basket_totals: Optional[Dict[int, int]] = None  # netuid -> actual delivered amount
    receipt_block: Optional[int] = None
    nav_per_share: Optional[float] = None
    shares_out: Optional[int] = None
    fees: Optional[int] = None
    cash_component: Optional[int] = None
    error_message: Optional[str] = None

class CreationRequestManager:
    """
    Manages creation requests for the TAO20 creation unit system.
    
    Handles request submission, validation, lifecycle management, and basket specifications.
    """
    
    def __init__(self, epoch_manager: Optional[EpochManager] = None):
        self.creation_requests: Dict[str, CreationRequest] = {}
        self.epoch_manager = epoch_manager or EpochManager()
        self.request_expiry_window = 3600  # 1 hour default
        self.min_creation_size = 1000
        self.max_creation_size = 10000
    
    def generate_request_id(self, miner_hotkey: str, creation_size: int) -> str:
        """
        Generate a unique request ID
        
        Args:
            miner_hotkey: Miner's hotkey
            creation_size: Creation size
            
        Returns:
            Unique request ID
        """
        # Create a unique identifier
        unique_data = f"{miner_hotkey}:{creation_size}:{int(time.time())}"
        request_hash = hashlib.sha256(unique_data.encode()).hexdigest()
        return f"req_{request_hash[:16]}"
    
    def validate_creation_size(self, creation_size: int) -> List[str]:
        """
        Validate creation size
        
        Args:
            creation_size: Creation size to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not isinstance(creation_size, int):
            errors.append("Creation size must be an integer")
            return errors
        
        if creation_size < self.min_creation_size:
            errors.append(f"Creation size {creation_size} below minimum {self.min_creation_size}")
        
        if creation_size > self.max_creation_size:
            errors.append(f"Creation size {creation_size} above maximum {self.max_creation_size}")
        
        return errors
    
    def validate_miner_hotkey(self, miner_hotkey: str) -> List[str]:
        """
        Validate miner hotkey
        
        Args:
            miner_hotkey: Miner hotkey to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not isinstance(miner_hotkey, str):
            errors.append("Miner hotkey must be a string")
            return errors
        
        if len(miner_hotkey) == 0:
            errors.append("Miner hotkey cannot be empty")
        
        # Add more validation as needed (e.g., format validation)
        
        return errors
    
    def validate_epoch_consistency(self, epoch_id: int) -> List[str]:
        """
        Validate epoch consistency
        
        Args:
            epoch_id: Epoch ID to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        current_epoch = self.epoch_manager.get_current_epoch_id()
        
        if epoch_id != current_epoch:
            errors.append(f"Request epoch {epoch_id} does not match current epoch {current_epoch}")
        
        # Check if epoch is active
        if not self.epoch_manager.is_epoch_active(epoch_id):
            errors.append(f"Epoch {epoch_id} is not active")
        
        return errors
    
    async def submit_creation_request(
        self, 
        miner_hotkey: str, 
        creation_size: int,
        expiry_window: Optional[int] = None
    ) -> str:
        """
        Submit a creation request
        
        Args:
            miner_hotkey: Miner's hotkey
            creation_size: Number of creation units
            expiry_window: Custom expiry window in seconds (optional)
            
        Returns:
            Request ID
            
        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Submitting creation request: miner={miner_hotkey}, size={creation_size}")
        
        # Validate inputs
        errors = []
        errors.extend(self.validate_miner_hotkey(miner_hotkey))
        errors.extend(self.validate_creation_size(creation_size))
        
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")
        
        # Get current epoch
        current_epoch = self.epoch_manager.get_current_epoch_id()
        errors.extend(self.validate_epoch_consistency(current_epoch))
        
        if errors:
            raise ValueError(f"Epoch validation failed: {'; '.join(errors)}")
        
        # Check if creation file exists for current epoch
        creation_file = self.epoch_manager.get_current_creation_file()
        if not creation_file:
            raise ValueError(f"No creation file found for current epoch {current_epoch}")
        
        # Generate request ID
        request_id = self.generate_request_id(miner_hotkey, creation_size)
        
        # Calculate expiry time
        expiry_window = expiry_window or self.request_expiry_window
        expires_at = int(time.time()) + expiry_window
        
        # Create request
        request = CreationRequest(
            request_id=request_id,
            epoch_id=current_epoch,
            creation_size=creation_size,
            miner_hotkey=miner_hotkey,
            submitted_at=int(time.time()),
            expires_at=expires_at,
            status=RequestStatus.PENDING
        )
        
        # Store request
        self.creation_requests[request_id] = request
        
        logger.info(f"Created creation request {request_id} for {creation_size} units")
        return request_id
    
    def get_creation_request(self, request_id: str) -> Optional[CreationRequest]:
        """
        Get a creation request by ID
        
        Args:
            request_id: Request ID
            
        Returns:
            CreationRequest object or None if not found
        """
        return self.creation_requests.get(request_id)
    
    def get_required_basket(self, creation_size: int) -> Dict[int, int]:
        """
        Get required basket quantities for creation size
        
        Args:
            creation_size: Number of creation units
            
        Returns:
            Dictionary mapping netuid to required quantity
            
        Raises:
            ValueError: If no creation file exists for current epoch
        """
        creation_file = self.epoch_manager.get_current_creation_file()
        if not creation_file:
            raise ValueError("No creation file found for current epoch")
        
        basket = {}
        for asset in creation_file.assets:
            required_qty = asset.qty_per_creation_unit * creation_size
            basket[asset.netuid] = required_qty
        
        return basket
    
    def get_required_basket_for_request(self, request_id: str) -> Dict[int, int]:
        """
        Get required basket for a specific request
        
        Args:
            request_id: Request ID
            
        Returns:
            Dictionary mapping netuid to required quantity
            
        Raises:
            ValueError: If request not found
        """
        request = self.get_creation_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        return self.get_required_basket(request.creation_size)
    
    def update_request_status(self, request_id: str, status: RequestStatus, **kwargs) -> bool:
        """
        Update request status and optional fields
        
        Args:
            request_id: Request ID
            status: New status
            **kwargs: Additional fields to update
            
        Returns:
            True if updated successfully, False if request not found
        """
        request = self.get_creation_request(request_id)
        if not request:
            logger.warning(f"Attempted to update non-existent request {request_id}")
            return False
        
        # Update status
        request.status = status
        
        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(request, key):
                setattr(request, key, value)
            else:
                logger.warning(f"Unknown field {key} for request {request_id}")
        
        logger.info(f"Updated request {request_id} status to {status.value}")
        return True
    
    def mark_request_delivered(self, request_id: str, basket_totals: Dict[int, int], receipt_block: int) -> bool:
        """
        Mark request as delivered
        
        Args:
            request_id: Request ID
            basket_totals: Actual delivered basket totals
            receipt_block: Block number where delivery was finalized
            
        Returns:
            True if updated successfully
        """
        return self.update_request_status(
            request_id,
            RequestStatus.DELIVERED,
            basket_totals=basket_totals,
            receipt_block=receipt_block
        )
    
    def mark_request_attested(self, request_id: str, nav_per_share: float, shares_out: int, fees: int, cash_component: int) -> bool:
        """
        Mark request as attested
        
        Args:
            request_id: Request ID
            nav_per_share: NAV per share at receipt block
            shares_out: Number of shares to mint
            fees: Fees charged
            cash_component: Cash component for rounding
            
        Returns:
            True if updated successfully
        """
        return self.update_request_status(
            request_id,
            RequestStatus.ATTESTED,
            nav_per_share=nav_per_share,
            shares_out=shares_out,
            fees=fees,
            cash_component=cash_component
        )
    
    def mark_request_minted(self, request_id: str) -> bool:
        """
        Mark request as minted
        
        Args:
            request_id: Request ID
            
        Returns:
            True if updated successfully
        """
        return self.update_request_status(request_id, RequestStatus.MINTED)
    
    def mark_request_expired(self, request_id: str, error_message: Optional[str] = None) -> bool:
        """
        Mark request as expired
        
        Args:
            request_id: Request ID
            error_message: Optional error message
            
        Returns:
            True if updated successfully
        """
        return self.update_request_status(
            request_id,
            RequestStatus.EXPIRED,
            error_message=error_message
        )
    
    def mark_request_failed(self, request_id: str, error_message: str) -> bool:
        """
        Mark request as failed
        
        Args:
            request_id: Request ID
            error_message: Error message
            
        Returns:
            True if updated successfully
        """
        return self.update_request_status(
            request_id,
            RequestStatus.FAILED,
            error_message=error_message
        )
    
    def get_pending_requests(self) -> List[CreationRequest]:
        """
        Get all pending requests
        
        Returns:
            List of pending creation requests
        """
        return [
            request for request in self.creation_requests.values()
            if request.status == RequestStatus.PENDING
        ]
    
    def get_delivered_requests(self) -> List[CreationRequest]:
        """
        Get all delivered requests
        
        Returns:
            List of delivered creation requests
        """
        return [
            request for request in self.creation_requests.values()
            if request.status == RequestStatus.DELIVERED
        ]
    
    def get_expired_requests(self) -> List[CreationRequest]:
        """
        Get all expired requests
        
        Returns:
            List of expired creation requests
        """
        current_time = int(time.time())
        return [
            request for request in self.creation_requests.values()
            if request.status == RequestStatus.PENDING and request.expires_at < current_time
        ]
    
    def cleanup_expired_requests(self) -> int:
        """
        Clean up expired requests
        
        Returns:
            Number of requests cleaned up
        """
        expired_requests = self.get_expired_requests()
        
        for request in expired_requests:
            self.mark_request_expired(request.request_id, "Request expired")
        
        logger.info(f"Cleaned up {len(expired_requests)} expired requests")
        return len(expired_requests)
    
    def get_miner_requests(self, miner_hotkey: str) -> List[CreationRequest]:
        """
        Get all requests for a specific miner
        
        Args:
            miner_hotkey: Miner's hotkey
            
        Returns:
            List of requests for the miner
        """
        return [
            request for request in self.creation_requests.values()
            if request.miner_hotkey == miner_hotkey
        ]
    
    def get_requests_by_status(self, status: RequestStatus) -> List[CreationRequest]:
        """
        Get requests by status
        
        Args:
            status: Request status to filter by
            
        Returns:
            List of requests with the specified status
        """
        return [
            request for request in self.creation_requests.values()
            if request.status == status
        ]
    
    def get_request_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about creation requests
        
        Returns:
            Dictionary with request statistics
        """
        total_requests = len(self.creation_requests)
        
        stats = {
            'total_requests': total_requests,
            'pending_requests': len(self.get_pending_requests()),
            'delivered_requests': len(self.get_delivered_requests()),
            'attested_requests': len(self.get_requests_by_status(RequestStatus.ATTESTED)),
            'minted_requests': len(self.get_requests_by_status(RequestStatus.MINTED)),
            'expired_requests': len(self.get_requests_by_status(RequestStatus.EXPIRED)),
            'failed_requests': len(self.get_requests_by_status(RequestStatus.FAILED)),
        }
        
        if total_requests > 0:
            stats['success_rate'] = stats['minted_requests'] / total_requests
            stats['expiry_rate'] = stats['expired_requests'] / total_requests
        else:
            stats['success_rate'] = 0.0
            stats['expiry_rate'] = 0.0
        
        return stats
    
    def to_dict(self, request: CreationRequest) -> Dict:
        """Convert request to dictionary for serialization"""
        data = asdict(request)
        data['status'] = request.status.value
        return data
    
    def from_dict(self, data: Dict) -> CreationRequest:
        """Create request from dictionary"""
        status_value = data.pop('status')
        data['status'] = RequestStatus(status_value)
        return CreationRequest(**data)
