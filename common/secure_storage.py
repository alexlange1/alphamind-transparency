#!/usr/bin/env python3
"""
Secure, Tamper-Proof Emissions Data Storage System

This module provides cryptographically secure storage for critical emissions data
with integrity verification, redundancy, and tamper detection.

Critical for AlphaMind subnet core functionality - ensures data cannot be manipulated.
"""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import secrets


class SecureEmissionsStorage:
    """
    Cryptographically secure storage for emissions data with integrity verification.
    
    Features:
    - SHA-256 content hashing for tamper detection
    - HMAC-SHA256 authentication with secret key
    - Atomic writes with backup redundancy
    - Timestamp verification and chain validation
    - Normalized percentage-based emissions format
    """
    
    def __init__(self, storage_dir: Path, secret_key: Optional[str] = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load secret key for HMAC
        self.secret_key = self._init_secret_key(secret_key)
        
        # Create secure subdirectories
        self.data_dir = self.storage_dir / "secure_data"
        self.backup_dir = self.storage_dir / "backups"
        self.integrity_dir = self.storage_dir / "integrity"
        
        for dir_path in [self.data_dir, self.backup_dir, self.integrity_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            # Set restrictive permissions (owner read/write only)
            os.chmod(dir_path, 0o700)
    
    def _init_secret_key(self, provided_key: Optional[str]) -> bytes:
        """Initialize or load the secret key for HMAC authentication"""
        key_file = self.storage_dir / ".secure_key"
        
        if provided_key:
            # Use provided key
            key = provided_key.encode('utf-8')
        elif key_file.exists():
            # Load existing key
            try:
                with open(key_file, 'rb') as f:
                    key = f.read()
            except Exception:
                # Generate new key if loading fails
                key = secrets.token_bytes(32)
        else:
            # Generate new 256-bit key
            key = secrets.token_bytes(32)
        
        # Save key securely
        try:
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Owner read/write only
        except Exception as e:
            print(f"Warning: Could not save secure key: {e}")
        
        return key
    
    def _normalize_emissions(self, raw_emissions: Dict[int, float]) -> Dict[int, float]:
        """
        Normalize emissions to percentage/decimal format.
        
        Converts absolute TAO/day values to percentage of total network emissions.
        """
        if not raw_emissions:
            return {}
        
        # Calculate total emissions across all subnets
        total_emissions = sum(raw_emissions.values())
        
        if total_emissions <= 0:
            return {netuid: 0.0 for netuid in raw_emissions.keys()}
        
        # Convert to percentages (as decimals: 0.1 = 10%)
        normalized = {}
        for netuid, emission in raw_emissions.items():
            percentage = emission / total_emissions
            normalized[netuid] = round(percentage, 8)  # 8 decimal precision
        
        # Verify normalization (should sum to 1.0)
        total_check = sum(normalized.values())
        if abs(total_check - 1.0) > 1e-6:
            print(f"Warning: Normalized emissions sum to {total_check}, expected 1.0")
        
        return normalized
    
    def _calculate_content_hash(self, data: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash of the data content"""
        # Create deterministic JSON representation
        json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    
    def _calculate_hmac(self, data: Dict[str, Any]) -> str:
        """Calculate HMAC-SHA256 authentication code"""
        json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hmac.new(
            self.secret_key,
            json_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def store_emissions_data(
        self,
        raw_emissions: Dict[int, float],
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Store emissions data securely with integrity verification.
        
        Args:
            raw_emissions: Raw emissions data by netuid (TAO/day)
            timestamp: ISO timestamp (defaults to current time)
            metadata: Additional metadata to store
            
        Returns:
            Tuple of (filename, content_hash) for verification
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        # Normalize emissions to percentages
        normalized_emissions = self._normalize_emissions(raw_emissions)
        
        # Create secure data structure
        secure_data = {
            "format_version": "1.0.0",
            "timestamp": timestamp,
            "collection_method": "btcli_automated_secure",
            "total_subnets": len(normalized_emissions),
            "emissions_percentage_by_netuid": normalized_emissions,
            "raw_total_emissions_tao_per_day": sum(raw_emissions.values()),
            "metadata": metadata or {}
        }
        
        # For integrity verification, we need to store the hash of the data WITHOUT the integrity section
        # This allows verification by recalculating the hash of the same data structure
        content_hash = self._calculate_content_hash(secure_data)
        hmac_signature = self._calculate_hmac(secure_data)
        
        # Add integrity fields (these are NOT included in hash calculation)
        secure_data["integrity"] = {
            "content_hash_sha256": content_hash,
            "hmac_sha256": hmac_signature,
            "storage_version": "secure_v1"
        }
        
        # Generate filename with timestamp (hash will be used for verification, not filename)
        date_str = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y%m%d_%H%M%S')
        filename = f"emissions_secure_{date_str}.json"
        
        # Atomic write with backup
        self._atomic_write_with_backup(filename, secure_data)
        
        # Update latest pointer
        self._update_latest_pointer(filename, secure_data)
        
        # Log security event
        self._log_security_event("STORE", filename, content_hash)
        
        return filename, content_hash
    
    def _atomic_write_with_backup(self, filename: str, data: Dict[str, Any]) -> None:
        """Write data atomically with backup redundancy"""
        primary_path = self.data_dir / filename
        backup_path = self.backup_dir / filename
        temp_path = self.data_dir / f".tmp_{filename}"
        
        json_content = json.dumps(data, indent=2, sort_keys=True)
        
        try:
            # Write to temporary file first
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(json_content)
            
            # Set restrictive permissions
            os.chmod(temp_path, 0o600)
            
            # Atomic move to primary location
            temp_path.replace(primary_path)
            
            # Create backup copy
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(json_content)
            os.chmod(backup_path, 0o600)
            
        except Exception as e:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to write secure data: {e}")
    
    def _update_latest_pointer(self, filename: str, data: Dict[str, Any]) -> None:
        """Update pointer to latest emissions data"""
        latest_info = {
            "latest_file": filename,
            "content_hash": data["integrity"]["content_hash_sha256"],
            "timestamp": data["timestamp"],
            "total_subnets": data["total_subnets"],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        latest_path = self.data_dir / "latest_emissions_secure.json"
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(latest_info, f, indent=2)
        os.chmod(latest_path, 0o600)
    
    def _log_security_event(self, action: str, filename: str, content_hash: str) -> None:
        """Log security events for audit trail"""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "filename": filename,
            "content_hash": content_hash,
            "process_id": os.getpid()
        }
        
        log_file = self.integrity_dir / "security_audit.jsonl"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def verify_data_integrity(self, filename: str) -> Tuple[bool, str]:
        """
        Verify the integrity of stored emissions data.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            file_path = self.data_dir / filename
            if not file_path.exists():
                return False, f"File {filename} not found"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract integrity information
            integrity = data.get("integrity", {})
            stored_hash = integrity.get("content_hash_sha256")
            stored_hmac = integrity.get("hmac_sha256")
            
            if not stored_hash or not stored_hmac:
                return False, "Missing integrity fields"
            
            # Create data without integrity fields for verification
            data_for_verification = {k: v for k, v in data.items() if k != "integrity"}
            
            # Verify content hash
            calculated_hash = self._calculate_content_hash(data_for_verification)
            if calculated_hash != stored_hash:
                return False, f"Content hash mismatch: {calculated_hash} != {stored_hash}"
            
            # Verify HMAC
            calculated_hmac = self._calculate_hmac(data_for_verification)
            if not hmac.compare_digest(calculated_hmac, stored_hmac):
                return False, "HMAC authentication failed"
            
            return True, "Data integrity verified"
            
        except Exception as e:
            return False, f"Verification error: {e}"
    
    def load_latest_emissions(self) -> Optional[Dict[int, float]]:
        """
        Load the latest verified emissions data.
        
        Returns:
            Dict mapping netuid -> emission percentage (decimal)
        """
        try:
            latest_path = self.data_dir / "latest_emissions_secure.json"
            if not latest_path.exists():
                return None
            
            with open(latest_path, 'r', encoding='utf-8') as f:
                latest_info = json.load(f)
            
            filename = latest_info["latest_file"]
            
            # Verify integrity before loading
            is_valid, error = self.verify_data_integrity(filename)
            if not is_valid:
                print(f"Warning: Latest emissions data failed integrity check: {error}")
                return None
            
            # Load verified data
            file_path = self.data_dir / filename
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert string keys back to integers
            emissions = data["emissions_percentage_by_netuid"]
            return {int(k): float(v) for k, v in emissions.items()}
            
        except Exception as e:
            print(f"Error loading latest emissions: {e}")
            return None
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about the secure storage system"""
        try:
            data_files = list(self.data_dir.glob("emissions_secure_*.json"))
            backup_files = list(self.backup_dir.glob("emissions_secure_*.json"))
            
            return {
                "total_data_files": len(data_files),
                "total_backup_files": len(backup_files),
                "storage_directory": str(self.storage_dir),
                "latest_available": (self.data_dir / "latest_emissions_secure.json").exists(),
                "security_features": [
                    "SHA-256 content hashing",
                    "HMAC-SHA256 authentication",
                    "Atomic writes with backup",
                    "Restrictive file permissions",
                    "Audit logging"
                ]
            }
        except Exception as e:
            return {"error": str(e)}


def create_secure_storage(storage_dir: Optional[str] = None, secret_key: Optional[str] = None) -> SecureEmissionsStorage:
    """
    Factory function to create a SecureEmissionsStorage instance.
    
    Args:
        storage_dir: Directory for secure storage (defaults to ./out/secure)
        secret_key: Secret key for HMAC (auto-generated if not provided)
    """
    if storage_dir is None:
        storage_dir = Path("./out/secure")
    
    return SecureEmissionsStorage(Path(storage_dir), secret_key)


if __name__ == "__main__":
    # Test the secure storage system
    print("Testing Secure Emissions Storage System...")
    
    storage = create_secure_storage()
    
    # Test data
    test_emissions = {
        1: 100.5,
        2: 75.2,
        3: 150.8,
        4: 200.1,
        5: 50.0
    }
    
    # Store data
    filename, content_hash = storage.store_emissions_data(test_emissions)
    print(f"✅ Stored data: {filename}")
    print(f"✅ Content hash: {content_hash}")
    
    # Verify integrity
    is_valid, message = storage.verify_data_integrity(filename)
    print(f"✅ Integrity check: {message}")
    
    # Load data
    loaded = storage.load_latest_emissions()
    if loaded:
        print(f"✅ Loaded {len(loaded)} subnet emissions (normalized to percentages)")
        total = sum(loaded.values())
        print(f"✅ Total percentage: {total:.6f} (should be 1.0)")
    
    # Show stats
    stats = storage.get_storage_stats()
    print(f"✅ Storage stats: {stats}")
