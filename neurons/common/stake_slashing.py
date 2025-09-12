#!/usr/bin/env python3
"""
TAO20 Validator Staking and Slashing Mechanism

This module implements the stake-based honesty enforcement system for TAO20
validators. It provides economic incentives for honest behavior and penalties
for dishonest or erroneous reporting through a transparent slashing mechanism.

Key Features:
- Stake requirement enforcement
- Deviation detection and consensus monitoring
- Graduated slashing penalties
- Validator reputation tracking
- Economic incentive alignment
- Transparent dispute resolution
"""

import asyncio
import logging
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import json
import statistics

import torch
import bittensor as bt

logger = logging.getLogger(__name__)


class SlashReason(Enum):
    """Reasons for validator slashing"""
    WEIGHT_DEVIATION = "weight_deviation"
    CONSENSUS_VIOLATION = "consensus_violation"
    DATA_FALSIFICATION = "data_falsification"
    INACTIVITY = "inactivity"
    REPEATED_ERRORS = "repeated_errors"
    MALICIOUS_BEHAVIOR = "malicious_behavior"


class ValidatorStatus(Enum):
    """Validator status states"""
    ACTIVE = "active"
    WARNING = "warning"
    PROBATION = "probation"
    SUSPENDED = "suspended"
    SLASHED = "slashed"


@dataclass
class StakeInfo:
    """Validator stake information"""
    validator_hotkey: str
    validator_uid: int
    
    # Stake amounts (in RAO)
    total_stake: int = 0
    locked_stake: int = 0
    slashed_stake: int = 0
    available_stake: int = 0
    
    # Requirements
    minimum_required: int = 0
    meets_requirement: bool = False
    
    # History
    stake_history: List[Dict] = field(default_factory=list)
    last_stake_update: int = 0


@dataclass
class DeviationRecord:
    """Record of validator deviation"""
    validator_hotkey: str
    timestamp: int
    deviation_type: str
    deviation_magnitude: Decimal
    reference_data: Dict
    validator_data: Dict
    consensus_data: Dict
    severity_score: Decimal


@dataclass
class SlashEvent:
    """Slashing event record"""
    slash_id: str
    validator_hotkey: str
    timestamp: int
    reason: SlashReason
    severity: str  # 'minor', 'moderate', 'severe', 'critical'
    
    # Financial impact
    slash_amount: int  # RAO
    slash_percentage: Decimal
    remaining_stake: int
    
    # Context
    evidence: Dict
    deviation_records: List[DeviationRecord]
    consensus_validators: List[str]
    
    # Status
    is_executed: bool = False
    is_appealed: bool = False
    appeal_result: Optional[str] = None


@dataclass
class ValidatorReputation:
    """Validator reputation tracking"""
    validator_hotkey: str
    
    # Reputation scores (0.0 - 1.0)
    accuracy_score: Decimal = Decimal('1.0')
    consistency_score: Decimal = Decimal('1.0')
    reliability_score: Decimal = Decimal('1.0')
    overall_score: Decimal = Decimal('1.0')
    
    # Performance metrics
    total_submissions: int = 0
    accurate_submissions: int = 0
    consensus_agreements: int = 0
    deviation_count: int = 0
    slash_count: int = 0
    
    # Time tracking
    first_activity: int = 0
    last_activity: int = 0
    active_days: int = 0
    
    # Status
    current_status: ValidatorStatus = ValidatorStatus.ACTIVE
    status_history: List[Dict] = field(default_factory=list)


class StakeSlashingManager:
    """
    Comprehensive stake-based slashing system for TAO20 validators
    
    Monitors validator behavior, detects deviations, and enforces
    economic penalties to maintain system integrity.
    """
    
    def __init__(
        self,
        subtensor: bt.subtensor,
        metagraph: bt.metagraph,
        config: dict
    ):
        self.subtensor = subtensor
        self.metagraph = metagraph
        self.config = config
        
        # Configuration parameters
        self.min_stake_requirement = int(config.get('min_stake_requirement', 1000 * 1e9))  # 1000 TAO in RAO
        self.deviation_threshold = Decimal(config.get('deviation_threshold', '0.05'))  # 5%
        self.severe_deviation_threshold = Decimal(config.get('severe_deviation_threshold', '0.15'))  # 15%
        
        # Slashing parameters
        self.minor_slash_rate = Decimal(config.get('minor_slash_rate', '0.01'))    # 1%
        self.moderate_slash_rate = Decimal(config.get('moderate_slash_rate', '0.05'))  # 5%
        self.severe_slash_rate = Decimal(config.get('severe_slash_rate', '0.15'))     # 15%
        self.critical_slash_rate = Decimal(config.get('critical_slash_rate', '0.5'))   # 50%
        
        # Consensus parameters
        self.min_validators_for_consensus = config.get('min_validators_for_consensus', 3)
        self.consensus_agreement_threshold = Decimal(config.get('consensus_agreement_threshold', '0.67'))  # 67%
        
        # State tracking
        self.validator_stakes: Dict[str, StakeInfo] = {}
        self.validator_reputations: Dict[str, ValidatorReputation] = {}
        self.deviation_records: List[DeviationRecord] = []
        self.slash_events: List[SlashEvent] = []
        self.weight_submissions: Dict[str, torch.Tensor] = {}
        
        # Consensus tracking
        self.consensus_weights: Optional[torch.Tensor] = None
        self.consensus_timestamp: int = 0
        
        logger.info("Stake Slashing Manager initialized")
        logger.info(f"Minimum stake: {self.min_stake_requirement/1e9:.0f} TAO")
        logger.info(f"Deviation threshold: {self.deviation_threshold:.1%}")
    
    async def initialize_validator_stakes(self):
        """Initialize validator stake information from metagraph"""
        try:
            logger.info("Initializing validator stakes...")
            
            for uid in range(self.metagraph.n.item()):
                hotkey = self.metagraph.hotkeys[uid]
                stake_amount = int(self.metagraph.S[uid] * 1e9)  # Convert TAO to RAO
                
                stake_info = StakeInfo(
                    validator_hotkey=hotkey,
                    validator_uid=uid,
                    total_stake=stake_amount,
                    available_stake=stake_amount,
                    minimum_required=self.min_stake_requirement,
                    meets_requirement=stake_amount >= self.min_stake_requirement,
                    last_stake_update=int(time.time())
                )
                
                self.validator_stakes[hotkey] = stake_info
                
                # Initialize reputation
                self.validator_reputations[hotkey] = ValidatorReputation(
                    validator_hotkey=hotkey,
                    first_activity=int(time.time()),
                    last_activity=int(time.time())
                )
            
            active_validators = sum(1 for stake in self.validator_stakes.values() if stake.meets_requirement)
            logger.info(f"Initialized {len(self.validator_stakes)} validators ({active_validators} active)")
            
        except Exception as e:
            logger.error(f"Error initializing validator stakes: {e}")
            raise
    
    def record_weight_submission(self, validator_hotkey: str, weights: torch.Tensor):
        """Record validator weight submission"""
        try:
            self.weight_submissions[validator_hotkey] = weights.clone()
            
            # Update reputation
            if validator_hotkey in self.validator_reputations:
                reputation = self.validator_reputations[validator_hotkey]
                reputation.total_submissions += 1
                reputation.last_activity = int(time.time())
            
            logger.debug(f"Recorded weight submission from {validator_hotkey[:10]}...")
            
        except Exception as e:
            logger.error(f"Error recording weight submission: {e}")
    
    def calculate_consensus_weights(self) -> Optional[torch.Tensor]:
        """Calculate consensus weights from validator submissions"""
        try:
            if len(self.weight_submissions) < self.min_validators_for_consensus:
                logger.warning(f"Insufficient validators for consensus: {len(self.weight_submissions)}")
                return None
            
            # Filter submissions from validators with sufficient stake
            valid_submissions = {}
            for hotkey, weights in self.weight_submissions.items():
                stake_info = self.validator_stakes.get(hotkey)
                if stake_info and stake_info.meets_requirement:
                    valid_submissions[hotkey] = weights
            
            if len(valid_submissions) < self.min_validators_for_consensus:
                logger.warning("Insufficient valid validators for consensus")
                return None
            
            # Calculate consensus using median approach
            weight_tensors = list(valid_submissions.values())
            stacked_weights = torch.stack(weight_tensors)
            
            # Use median for robustness against outliers
            consensus_weights = torch.median(stacked_weights, dim=0)[0]
            
            self.consensus_weights = consensus_weights
            self.consensus_timestamp = int(time.time())
            
            logger.debug(f"Calculated consensus from {len(valid_submissions)} validators")
            return consensus_weights
            
        except Exception as e:
            logger.error(f"Error calculating consensus weights: {e}")
            return None
    
    def detect_validator_deviations(self) -> List[DeviationRecord]:
        """Detect deviations from consensus"""
        try:
            if not self.consensus_weights:
                return []
            
            deviations = []
            current_time = int(time.time())
            
            for validator_hotkey, submitted_weights in self.weight_submissions.items():
                try:
                    # Calculate deviation from consensus
                    deviation_magnitude = self._calculate_weight_deviation(
                        submitted_weights, self.consensus_weights
                    )
                    
                    if deviation_magnitude > self.deviation_threshold:
                        # Create deviation record
                        deviation = DeviationRecord(
                            validator_hotkey=validator_hotkey,
                            timestamp=current_time,
                            deviation_type="weight_submission",
                            deviation_magnitude=deviation_magnitude,
                            reference_data={"consensus_weights": self.consensus_weights.tolist()},
                            validator_data={"submitted_weights": submitted_weights.tolist()},
                            consensus_data={
                                "num_validators": len(self.weight_submissions),
                                "consensus_timestamp": self.consensus_timestamp
                            },
                            severity_score=self._calculate_severity_score(deviation_magnitude)
                        )
                        
                        deviations.append(deviation)
                        self.deviation_records.append(deviation)
                        
                        # Update reputation
                        if validator_hotkey in self.validator_reputations:
                            reputation = self.validator_reputations[validator_hotkey]
                            reputation.deviation_count += 1
                            self._update_reputation_scores(reputation)
                        
                        logger.warning(f"Deviation detected: {validator_hotkey[:10]}... "
                                     f"magnitude={deviation_magnitude:.4f}")
                
                except Exception as e:
                    logger.error(f"Error checking deviation for {validator_hotkey}: {e}")
            
            # Cleanup old deviation records
            cutoff_time = current_time - 86400  # Keep 24 hours
            self.deviation_records = [
                record for record in self.deviation_records
                if record.timestamp > cutoff_time
            ]
            
            return deviations
            
        except Exception as e:
            logger.error(f"Error detecting validator deviations: {e}")
            return []
    
    def _calculate_weight_deviation(self, weights1: torch.Tensor, weights2: torch.Tensor) -> Decimal:
        """Calculate deviation between two weight vectors"""
        try:
            # Use L1 distance (Manhattan distance) normalized by sum of weights
            diff = torch.abs(weights1 - weights2)
            total_deviation = diff.sum().item()
            
            # Normalize by total weight magnitude
            weight_sum = (weights1.sum() + weights2.sum()).item()
            if weight_sum > 0:
                normalized_deviation = total_deviation / weight_sum
            else:
                normalized_deviation = 0.0
            
            return Decimal(str(normalized_deviation))
            
        except Exception as e:
            logger.error(f"Error calculating weight deviation: {e}")
            return Decimal('0')
    
    def _calculate_severity_score(self, deviation_magnitude: Decimal) -> Decimal:
        """Calculate severity score based on deviation magnitude"""
        try:
            if deviation_magnitude <= self.deviation_threshold:
                return Decimal('0')  # No penalty
            elif deviation_magnitude <= self.deviation_threshold * 2:
                return Decimal('0.25')  # Minor
            elif deviation_magnitude <= self.severe_deviation_threshold:
                return Decimal('0.5')   # Moderate
            elif deviation_magnitude <= self.severe_deviation_threshold * 2:
                return Decimal('0.75')  # Severe
            else:
                return Decimal('1.0')   # Critical
                
        except Exception as e:
            logger.error(f"Error calculating severity score: {e}")
            return Decimal('0.5')
    
    def _update_reputation_scores(self, reputation: ValidatorReputation):
        """Update reputation scores based on recent activity"""
        try:
            # Calculate accuracy score
            if reputation.total_submissions > 0:
                reputation.accuracy_score = Decimal(reputation.accurate_submissions) / Decimal(reputation.total_submissions)
            
            # Calculate consistency score (inverse of deviation frequency)
            if reputation.total_submissions > 0:
                deviation_rate = Decimal(reputation.deviation_count) / Decimal(reputation.total_submissions)
                reputation.consistency_score = max(Decimal('0'), Decimal('1') - deviation_rate)
            
            # Calculate reliability score (based on activity and slash history)
            activity_factor = min(Decimal('1'), Decimal(reputation.total_submissions) / Decimal('100'))
            slash_penalty = Decimal(reputation.slash_count) * Decimal('0.1')
            reputation.reliability_score = max(Decimal('0'), activity_factor - slash_penalty)
            
            # Calculate overall score (weighted average)
            reputation.overall_score = (
                reputation.accuracy_score * Decimal('0.4') +
                reputation.consistency_score * Decimal('0.4') +
                reputation.reliability_score * Decimal('0.2')
            )
            
        except Exception as e:
            logger.error(f"Error updating reputation scores: {e}")
    
    async def evaluate_slashing_candidates(self) -> List[SlashEvent]:
        """Evaluate validators for potential slashing"""
        try:
            slash_events = []
            current_time = int(time.time())
            
            for validator_hotkey, reputation in self.validator_reputations.items():
                try:
                    # Get recent deviations
                    recent_deviations = [
                        record for record in self.deviation_records
                        if record.validator_hotkey == validator_hotkey
                        and current_time - record.timestamp < 3600  # Last hour
                    ]
                    
                    if not recent_deviations:
                        continue
                    
                    # Determine slash severity
                    max_severity = max(record.severity_score for record in recent_deviations)
                    deviation_count = len(recent_deviations)
                    
                    # Calculate slash parameters
                    slash_severity, slash_reason = self._determine_slash_parameters(
                        max_severity, deviation_count, reputation
                    )
                    
                    if slash_severity == "none":
                        continue
                    
                    # Calculate slash amount
                    stake_info = self.validator_stakes.get(validator_hotkey)
                    if not stake_info:
                        continue
                    
                    slash_rate = self._get_slash_rate(slash_severity)
                    slash_amount = int(stake_info.available_stake * slash_rate)
                    
                    # Create slash event
                    slash_event = SlashEvent(
                        slash_id=self._generate_slash_id(validator_hotkey, current_time),
                        validator_hotkey=validator_hotkey,
                        timestamp=current_time,
                        reason=slash_reason,
                        severity=slash_severity,
                        slash_amount=slash_amount,
                        slash_percentage=slash_rate,
                        remaining_stake=stake_info.available_stake - slash_amount,
                        evidence={
                            "deviation_count": deviation_count,
                            "max_severity": float(max_severity),
                            "reputation_score": float(reputation.overall_score),
                            "total_submissions": reputation.total_submissions
                        },
                        deviation_records=recent_deviations,
                        consensus_validators=list(self.weight_submissions.keys())
                    )
                    
                    slash_events.append(slash_event)
                    
                except Exception as e:
                    logger.error(f"Error evaluating slashing for {validator_hotkey}: {e}")
            
            return slash_events
            
        except Exception as e:
            logger.error(f"Error evaluating slashing candidates: {e}")
            return []
    
    def _determine_slash_parameters(
        self, 
        max_severity: Decimal, 
        deviation_count: int, 
        reputation: ValidatorReputation
    ) -> Tuple[str, SlashReason]:
        """Determine slash severity and reason"""
        try:
            # Consider multiple factors
            if max_severity >= Decimal('0.75'):  # Critical deviation
                return "severe", SlashReason.CONSENSUS_VIOLATION
            elif max_severity >= Decimal('0.5') or deviation_count >= 5:  # Moderate deviation or frequent errors
                return "moderate", SlashReason.WEIGHT_DEVIATION
            elif max_severity >= Decimal('0.25') or deviation_count >= 3:  # Minor deviation
                return "minor", SlashReason.WEIGHT_DEVIATION
            elif reputation.slash_count >= 3:  # Repeated offender
                return "severe", SlashReason.REPEATED_ERRORS
            else:
                return "none", SlashReason.WEIGHT_DEVIATION
                
        except Exception as e:
            logger.error(f"Error determining slash parameters: {e}")
            return "none", SlashReason.WEIGHT_DEVIATION
    
    def _get_slash_rate(self, severity: str) -> Decimal:
        """Get slash rate based on severity"""
        rates = {
            "minor": self.minor_slash_rate,
            "moderate": self.moderate_slash_rate,
            "severe": self.severe_slash_rate,
            "critical": self.critical_slash_rate
        }
        return rates.get(severity, Decimal('0'))
    
    def _generate_slash_id(self, validator_hotkey: str, timestamp: int) -> str:
        """Generate unique slash ID"""
        data = f"{validator_hotkey}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    async def execute_slash_event(self, slash_event: SlashEvent) -> bool:
        """Execute a slash event"""
        try:
            validator_hotkey = slash_event.validator_hotkey
            
            # Get stake info
            stake_info = self.validator_stakes.get(validator_hotkey)
            if not stake_info:
                logger.error(f"No stake info for validator {validator_hotkey}")
                return False
            
            # Check if slash amount is valid
            if slash_event.slash_amount > stake_info.available_stake:
                logger.error(f"Slash amount exceeds available stake")
                return False
            
            # Update stake info
            stake_info.slashed_stake += slash_event.slash_amount
            stake_info.available_stake -= slash_event.slash_amount
            stake_info.meets_requirement = stake_info.available_stake >= self.min_stake_requirement
            
            # Update reputation
            reputation = self.validator_reputations.get(validator_hotkey)
            if reputation:
                reputation.slash_count += 1
                self._update_reputation_scores(reputation)
                
                # Update status
                if slash_event.severity == "critical":
                    reputation.current_status = ValidatorStatus.SUSPENDED
                elif slash_event.severity == "severe":
                    reputation.current_status = ValidatorStatus.PROBATION
                else:
                    reputation.current_status = ValidatorStatus.WARNING
                
                # Record status change
                reputation.status_history.append({
                    'timestamp': int(time.time()),
                    'status': reputation.current_status.value,
                    'reason': slash_event.reason.value,
                    'slash_amount': slash_event.slash_amount
                })
            
            # Mark slash as executed
            slash_event.is_executed = True
            self.slash_events.append(slash_event)
            
            logger.warning(f"Executed slash: {validator_hotkey[:10]}... "
                         f"{slash_event.severity} - {slash_event.slash_amount/1e9:.2f} TAO")
            
            # In real implementation, would execute on-chain slash
            # For now, just track internally
            
            return True
            
        except Exception as e:
            logger.error(f"Error executing slash event: {e}")
            return False
    
    def get_validator_status(self, validator_hotkey: str) -> Dict:
        """Get comprehensive validator status"""
        try:
            stake_info = self.validator_stakes.get(validator_hotkey)
            reputation = self.validator_reputations.get(validator_hotkey)
            
            if not stake_info or not reputation:
                return {'error': 'Validator not found'}
            
            # Get recent deviations
            recent_deviations = [
                record for record in self.deviation_records
                if record.validator_hotkey == validator_hotkey
                and int(time.time()) - record.timestamp < 86400  # Last 24 hours
            ]
            
            # Get slash history
            slash_history = [
                event for event in self.slash_events
                if event.validator_hotkey == validator_hotkey
            ]
            
            return {
                'validator_hotkey': validator_hotkey,
                'stake_info': {
                    'total_stake_tao': stake_info.total_stake / 1e9,
                    'available_stake_tao': stake_info.available_stake / 1e9,
                    'slashed_stake_tao': stake_info.slashed_stake / 1e9,
                    'meets_requirement': stake_info.meets_requirement,
                    'required_tao': stake_info.minimum_required / 1e9
                },
                'reputation': {
                    'overall_score': float(reputation.overall_score),
                    'accuracy_score': float(reputation.accuracy_score),
                    'consistency_score': float(reputation.consistency_score),
                    'reliability_score': float(reputation.reliability_score),
                    'current_status': reputation.current_status.value,
                    'total_submissions': reputation.total_submissions,
                    'deviation_count': reputation.deviation_count,
                    'slash_count': reputation.slash_count
                },
                'recent_activity': {
                    'deviations_24h': len(recent_deviations),
                    'last_activity': reputation.last_activity,
                    'active_days': reputation.active_days
                },
                'slash_history': [
                    {
                        'timestamp': event.timestamp,
                        'severity': event.severity,
                        'reason': event.reason.value,
                        'amount_tao': event.slash_amount / 1e9
                    }
                    for event in slash_history
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting validator status: {e}")
            return {'error': str(e)}
    
    def get_system_stats(self) -> Dict:
        """Get slashing system statistics"""
        try:
            current_time = int(time.time())
            
            # Count validators by status
            status_counts = {status.value: 0 for status in ValidatorStatus}
            for reputation in self.validator_reputations.values():
                status_counts[reputation.current_status.value] += 1
            
            # Calculate total slashed amount
            total_slashed = sum(stake.slashed_stake for stake in self.validator_stakes.values())
            
            # Count recent activity
            recent_deviations = len([
                record for record in self.deviation_records
                if current_time - record.timestamp < 3600  # Last hour
            ])
            
            recent_slashes = len([
                event for event in self.slash_events
                if current_time - event.timestamp < 86400  # Last 24 hours
            ])
            
            return {
                'total_validators': len(self.validator_stakes),
                'active_validators': sum(1 for stake in self.validator_stakes.values() if stake.meets_requirement),
                'validator_status_counts': status_counts,
                'total_slashed_tao': total_slashed / 1e9,
                'total_deviation_records': len(self.deviation_records),
                'total_slash_events': len(self.slash_events),
                'recent_deviations_1h': recent_deviations,
                'recent_slashes_24h': recent_slashes,
                'consensus_validators': len(self.weight_submissions),
                'last_consensus_timestamp': self.consensus_timestamp,
                'config': {
                    'min_stake_tao': self.min_stake_requirement / 1e9,
                    'deviation_threshold': float(self.deviation_threshold),
                    'slash_rates': {
                        'minor': float(self.minor_slash_rate),
                        'moderate': float(self.moderate_slash_rate),
                        'severe': float(self.severe_slash_rate),
                        'critical': float(self.critical_slash_rate)
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def export_slash_report(self) -> str:
        """Export comprehensive slashing report"""
        try:
            report_data = {
                'timestamp': int(time.time()),
                'system_stats': self.get_system_stats(),
                'validator_details': [
                    self.get_validator_status(hotkey)
                    for hotkey in self.validator_stakes.keys()
                ],
                'recent_slash_events': [
                    {
                        'slash_id': event.slash_id,
                        'validator': event.validator_hotkey,
                        'timestamp': event.timestamp,
                        'reason': event.reason.value,
                        'severity': event.severity,
                        'amount_tao': event.slash_amount / 1e9,
                        'is_executed': event.is_executed
                    }
                    for event in self.slash_events[-50:]  # Last 50 events
                ]
            }
            
            return json.dumps(report_data, indent=2)
            
        except Exception as e:
            logger.error(f"Error exporting slash report: {e}")
            return "{}"


async def main():
    """Example usage of stake slashing system"""
    import bittensor as bt
    
    # Setup Bittensor components
    config = bt.config()
    config.netuid = 20
    
    subtensor = bt.subtensor(config=config)
    metagraph = subtensor.metagraph(config.netuid)
    
    # Initialize slashing manager
    slashing_config = {
        'min_stake_requirement': 1000 * 1e9,  # 1000 TAO
        'deviation_threshold': 0.05,           # 5%
        'minor_slash_rate': 0.01,             # 1%
        'moderate_slash_rate': 0.05,          # 5%
        'severe_slash_rate': 0.15,            # 15%
        'critical_slash_rate': 0.5            # 50%
    }
    
    manager = StakeSlashingManager(subtensor, metagraph, slashing_config)
    
    # Initialize stakes
    await manager.initialize_validator_stakes()
    
    # Simulate weight submissions and consensus
    import torch
    
    # Normal validator
    weights1 = torch.tensor([0.1, 0.2, 0.3, 0.4])
    manager.record_weight_submission("validator1", weights1)
    
    # Similar validator
    weights2 = torch.tensor([0.12, 0.18, 0.32, 0.38])
    manager.record_weight_submission("validator2", weights2)
    
    # Deviating validator
    weights3 = torch.tensor([0.5, 0.1, 0.1, 0.3])  # Significant deviation
    manager.record_weight_submission("validator3", weights3)
    
    # Calculate consensus
    consensus = manager.calculate_consensus_weights()
    print(f"Consensus weights: {consensus}")
    
    # Detect deviations
    deviations = manager.detect_validator_deviations()
    print(f"Detected {len(deviations)} deviations")
    
    # Evaluate slashing
    slash_events = await manager.evaluate_slashing_candidates()
    print(f"Slash candidates: {len(slash_events)}")
    
    # Execute slashes
    for event in slash_events:
        success = await manager.execute_slash_event(event)
        print(f"Slash executed: {success}")
    
    # Get system stats
    stats = manager.get_system_stats()
    print(f"System stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
