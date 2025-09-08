"""
Basket Validator for TAO20 Creation Unit System

Enforces all-or-nothing basket delivery with tight tolerances.
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BasketValidationResult:
    """Result of basket validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    tolerance_violations: List[Tuple[int, int, int]]  # (netuid, required, delivered)
    missing_assets: List[int]
    extra_assets: List[int]

class BasketValidator:
    """
    Validates basket delivery for creation requests.
    
    Enforces all-or-nothing delivery with tight tolerances.
    """
    
    def __init__(self, tolerance_bps: int = 5):
        """
        Initialize basket validator
        
        Args:
            tolerance_bps: Tolerance in basis points (default 5 bps = 0.05%)
        """
        self.tolerance_bps = tolerance_bps
        self.tolerance_multiplier = tolerance_bps / 10000.0
        
        logger.info(f"BasketValidator initialized with tolerance {tolerance_bps} bps ({self.tolerance_multiplier:.4f})")
    
    def validate_all_or_nothing(
        self, 
        required: Dict[int, int], 
        delivered: Dict[int, int]
    ) -> BasketValidationResult:
        """
        Validate all-or-nothing basket delivery
        
        Args:
            required: Required basket quantities (netuid -> quantity)
            delivered: Delivered basket quantities (netuid -> quantity)
            
        Returns:
            BasketValidationResult with validation details
        """
        errors = []
        warnings = []
        tolerance_violations = []
        missing_assets = []
        extra_assets = []
        
        # Check all required assets are present
        for netuid in required:
            if netuid not in delivered:
                missing_assets.append(netuid)
                errors.append(f"Missing required asset: subnet {netuid}")
        
        # Check no extra assets
        for netuid in delivered:
            if netuid not in required:
                extra_assets.append(netuid)
                errors.append(f"Extra asset not in required basket: subnet {netuid}")
        
        # Check quantities within tolerance
        for netuid, required_qty in required.items():
            if netuid in delivered:
                delivered_qty = delivered[netuid]
                tolerance = max(1, int(required_qty * self.tolerance_multiplier))
                
                if abs(delivered_qty - required_qty) > tolerance:
                    tolerance_violations.append((netuid, required_qty, delivered_qty))
                    errors.append(
                        f"Quantity for subnet {netuid} outside tolerance: "
                        f"required {required_qty}, delivered {delivered_qty}, "
                        f"tolerance ±{tolerance}"
                    )
                elif abs(delivered_qty - required_qty) > tolerance * 0.5:
                    # Warning for quantities close to tolerance limit
                    warnings.append(
                        f"Quantity for subnet {netuid} close to tolerance limit: "
                        f"required {required_qty}, delivered {delivered_qty}, "
                        f"tolerance ±{tolerance}"
                    )
        
        # Determine overall validity
        is_valid = len(errors) == 0
        
        result = BasketValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            tolerance_violations=tolerance_violations,
            missing_assets=missing_assets,
            extra_assets=extra_assets
        )
        
        if is_valid:
            logger.info(f"Basket validation passed for {len(required)} assets")
        else:
            logger.warning(f"Basket validation failed: {len(errors)} errors")
        
        return result
    
    def validate_basket_completeness(self, required: Dict[int, int], delivered: Dict[int, int]) -> bool:
        """
        Quick check if basket is complete (all required assets present)
        
        Args:
            required: Required basket quantities
            delivered: Delivered basket quantities
            
        Returns:
            True if all required assets are present
        """
        return all(netuid in delivered for netuid in required)
    
    def validate_basket_accuracy(self, required: Dict[int, int], delivered: Dict[int, int]) -> bool:
        """
        Quick check if basket quantities are within tolerance
        
        Args:
            required: Required basket quantities
            delivered: Delivered basket quantities
            
        Returns:
            True if all quantities are within tolerance
        """
        for netuid, required_qty in required.items():
            if netuid not in delivered:
                return False
            
            delivered_qty = delivered[netuid]
            tolerance = max(1, int(required_qty * self.tolerance_multiplier))
            
            if abs(delivered_qty - required_qty) > tolerance:
                return False
        
        return True
    
    def calculate_basket_deviation(self, required: Dict[int, int], delivered: Dict[int, int]) -> Dict[int, float]:
        """
        Calculate deviation percentage for each asset
        
        Args:
            required: Required basket quantities
            delivered: Delivered basket quantities
            
        Returns:
            Dictionary mapping netuid to deviation percentage
        """
        deviations = {}
        
        for netuid, required_qty in required.items():
            if netuid in delivered:
                delivered_qty = delivered[netuid]
                if required_qty > 0:
                    deviation = abs(delivered_qty - required_qty) / required_qty
                    deviations[netuid] = deviation
                else:
                    deviations[netuid] = 0.0 if delivered_qty == 0 else float('inf')
            else:
                deviations[netuid] = float('inf')
        
        return deviations
    
    def get_tolerance_for_asset(self, required_qty: int) -> int:
        """
        Get tolerance for a specific asset quantity
        
        Args:
            required_qty: Required quantity
            
        Returns:
            Tolerance amount
        """
        return max(1, int(required_qty * self.tolerance_multiplier))
    
    def validate_minimum_quantities(self, delivered: Dict[int, int], min_quantities: Dict[int, int]) -> List[str]:
        """
        Validate minimum quantities for delivered assets
        
        Args:
            delivered: Delivered basket quantities
            min_quantities: Minimum required quantities
            
        Returns:
            List of validation errors
        """
        errors = []
        
        for netuid, min_qty in min_quantities.items():
            if netuid in delivered:
                delivered_qty = delivered[netuid]
                if delivered_qty < min_qty:
                    errors.append(
                        f"Delivered quantity for subnet {netuid} below minimum: "
                        f"delivered {delivered_qty}, minimum {min_qty}"
                    )
            else:
                errors.append(f"Missing asset for subnet {netuid} with minimum requirement {min_qty}")
        
        return errors
    
    def suggest_basket_corrections(
        self, 
        required: Dict[int, int], 
        delivered: Dict[int, int]
    ) -> Dict[int, int]:
        """
        Suggest corrections for basket quantities
        
        Args:
            required: Required basket quantities
            delivered: Delivered basket quantities
            
        Returns:
            Dictionary with suggested corrections (netuid -> adjustment)
        """
        corrections = {}
        
        for netuid, required_qty in required.items():
            if netuid in delivered:
                delivered_qty = delivered[netuid]
                adjustment = required_qty - delivered_qty
                
                if abs(adjustment) > 0:
                    corrections[netuid] = adjustment
            else:
                # Missing asset - suggest full required quantity
                corrections[netuid] = required_qty
        
        return corrections
    
    def get_validation_summary(self, result: BasketValidationResult) -> Dict:
        """
        Get a summary of validation results
        
        Args:
            result: BasketValidationResult object
            
        Returns:
            Dictionary with validation summary
        """
        summary = {
            'is_valid': result.is_valid,
            'total_errors': len(result.errors),
            'total_warnings': len(result.warnings),
            'missing_assets_count': len(result.missing_assets),
            'extra_assets_count': len(result.extra_assets),
            'tolerance_violations_count': len(result.tolerance_violations),
            'missing_assets': result.missing_assets,
            'extra_assets': result.extra_assets,
            'tolerance_violations': [
                {
                    'netuid': netuid,
                    'required': required,
                    'delivered': delivered,
                    'deviation': abs(delivered - required) / required if required > 0 else 0
                }
                for netuid, required, delivered in result.tolerance_violations
            ]
        }
        
        return summary
    
    def log_validation_result(self, result: BasketValidationResult, request_id: str):
        """
        Log validation results
        
        Args:
            result: BasketValidationResult object
            request_id: Request ID for logging context
        """
        if result.is_valid:
            logger.info(f"Basket validation PASSED for request {request_id}")
            if result.warnings:
                logger.warning(f"Basket validation warnings for request {request_id}: {result.warnings}")
        else:
            logger.error(f"Basket validation FAILED for request {request_id}: {result.errors}")
            
            if result.missing_assets:
                logger.error(f"Missing assets for request {request_id}: {result.missing_assets}")
            
            if result.extra_assets:
                logger.error(f"Extra assets for request {request_id}: {result.extra_assets}")
            
            if result.tolerance_violations:
                logger.error(f"Tolerance violations for request {request_id}: {result.tolerance_violations}")

class BasketValidatorFactory:
    """Factory for creating basket validators with different configurations"""
    
    @staticmethod
    def create_strict_validator() -> BasketValidator:
        """Create a strict validator with 1 bps tolerance"""
        return BasketValidator(tolerance_bps=1)
    
    @staticmethod
    def create_standard_validator() -> BasketValidator:
        """Create a standard validator with 5 bps tolerance"""
        return BasketValidator(tolerance_bps=5)
    
    @staticmethod
    def create_relaxed_validator() -> BasketValidator:
        """Create a relaxed validator with 10 bps tolerance"""
        return BasketValidator(tolerance_bps=10)
    
    @staticmethod
    def create_custom_validator(tolerance_bps: int) -> BasketValidator:
        """Create a custom validator with specified tolerance"""
        return BasketValidator(tolerance_bps=tolerance_bps)
