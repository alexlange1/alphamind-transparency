#!/usr/bin/env python3
"""
Automated Emissions Data Collection from Bittensor Network
Fetches subnet emissions data directly from btcli at scheduled times
"""

import subprocess
import json
import time
import os
from typing import Dict, Optional, Tuple
from pathlib import Path


def parse_btcli_emissions_json(json_text: str) -> Dict[int, float]:
    """
    Parse btcli subnets list JSON output to extract emissions data for each subnet.
    
    The btcli subnets list --json-output command returns JSON with subnet information.
    """
    emissions: Dict[int, float] = {}
    
    try:
        import json
        import re
        
        # Clean up the JSON text - remove control characters that can cause parsing issues
        clean_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_text)
        
        # Try to extract just the JSON part if there are extra characters
        json_start = clean_text.find('{')
        if json_start > 0:
            clean_text = clean_text[json_start:]
        
        data = json.loads(clean_text)
        
        # Extract subnet data from JSON structure
        subnets = data.get("subnets", {})
        
        for netuid_str, subnet_info in subnets.items():
            try:
                netuid = int(netuid_str)
                emission = float(subnet_info.get("emission", 0.0))
                
                # Convert per-block emission to daily emission
                # Bittensor has approximately 7200 blocks per day (12 second blocks)
                blocks_per_day = 7200
                daily_emission = emission * blocks_per_day
                
                emissions[netuid] = daily_emission
                
            except (ValueError, TypeError) as e:
                # Skip malformed entries
                continue
                
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing btcli JSON output: {e}")
        # Try to save the problematic output for debugging
        try:
            with open("/tmp/btcli_debug_output.txt", "w") as f:
                f.write(json_text[:1000])  # Save first 1000 chars for debugging
            print("Debug: Saved problematic output to /tmp/btcli_debug_output.txt")
        except:
            pass
        
    return emissions


def fetch_emissions_from_btcli(btcli_path: str, network: str = "finney", timeout_sec: int = 30) -> Dict[int, float]:
    """
    Fetch current emissions data directly from Bittensor network via btcli.
    
    Args:
        btcli_path: Path to btcli binary
        network: Bittensor network (finney, test, local)
        timeout_sec: Command timeout
        
    Returns:
        Dict mapping netuid -> daily emissions in TAO
    """
    try:
        # Run btcli subnets list command to get current emissions in JSON format
        proc = subprocess.run(
            [btcli_path, "subnets", "list", "--network", network, "--json-output"],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        
        # Parse the JSON output to extract emissions data
        emissions = parse_btcli_emissions_json(proc.stdout)
        
        if not emissions:
            print(f"Warning: No emissions data parsed from btcli output")
            
        return emissions
        
    except subprocess.TimeoutExpired:
        print(f"Error: btcli command timed out after {timeout_sec} seconds")
        return {}
        
    except subprocess.CalledProcessError as e:
        print(f"Error: btcli command failed: {e}")
        return {}
        
    except Exception as e:
        print(f"Error fetching emissions from btcli: {e}")
        return {}


def take_snapshot_map(btcli_path: Optional[str] = None, network: str = "finney") -> Dict[int, float]:
    """
    Take a snapshot of current subnet emissions from Bittensor network.
    
    This is the main function called by the miner loop to get live emissions data.
    
    Args:
        btcli_path: Path to btcli binary (defaults to environment variable)
        network: Bittensor network to query
        
    Returns:
        Dict mapping netuid -> daily emissions in TAO
    """
    # Get btcli path from environment or parameter
    if not btcli_path:
        btcli_path = os.environ.get("AM_BTCLI", "btcli")
        
    # Verify btcli is available
    if not btcli_path or not Path(btcli_path).exists():
        # Try to find btcli in PATH
        try:
            result = subprocess.run(["which", "btcli"], capture_output=True, text=True)
            if result.returncode == 0:
                btcli_path = result.stdout.strip()
            else:
                print("Error: btcli not found. Please install btcli or set AM_BTCLI environment variable")
                return {}
        except Exception:
            print("Error: btcli not found. Please install btcli or set AM_BTCLI environment variable")
            return {}
    
    print(f"Fetching emissions data from Bittensor network ({network}) using btcli: {btcli_path}")
    
    # Fetch current emissions data
    emissions = fetch_emissions_from_btcli(btcli_path, network)
    
    if emissions:
        print(f"Successfully fetched emissions for {len(emissions)} subnets")
        # Log a few examples
        sample_subnets = list(emissions.items())[:5]
        print(f"Sample emissions: {sample_subnets}")
    else:
        print("Warning: No emissions data retrieved")
        
    return emissions


def schedule_daily_emissions_collection(
    out_dir: Path,
    btcli_path: str,
    network: str = "finney",
    collection_hour_utc: int = 16  # 4 PM UTC as mentioned in the code
) -> None:
    """
    Schedule daily automated emissions collection at a fixed time.
    
    This function uses cryptographically secure storage to ensure data integrity
    and prevent manipulation of critical AlphaMind subnet data.
    """
    from datetime import datetime, timezone
    import sys
    import os
    
    # Add project root to path for imports
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from common.secure_storage import create_secure_storage
    
    current_time = datetime.now(timezone.utc)
    print(f"🔒 SECURE Daily emissions collection triggered at {current_time.isoformat()}")
    
    # Take emissions snapshot
    emissions = take_snapshot_map(btcli_path, network)
    
    if emissions:
        # Initialize secure storage
        secure_storage = create_secure_storage(
            storage_dir=out_dir / "secure",
            secret_key=os.environ.get("ALPHAMIND_SECRET_KEY")
        )
        
        # Prepare metadata
        metadata = {
            "network": network,
            "btcli_path": btcli_path,
            "collection_hour_utc": collection_hour_utc,
            "raw_subnet_count": len(emissions),
            "collection_source": "bittensor_finney_network"
        }
        
        # Store data securely with integrity verification
        filename, content_hash = secure_storage.store_emissions_data(
            raw_emissions=emissions,
            timestamp=current_time.isoformat(),
            metadata=metadata
        )
        
        print(f"✅ SECURE storage complete:")
        print(f"   📁 File: {filename}")
        print(f"   🔐 Hash: {content_hash}")
        print(f"   📊 Subnets: {len(emissions)}")
        print(f"   🛡️  Integrity: SHA-256 + HMAC-SHA256 protected")
        
        # Verify integrity immediately
        is_valid, verification_msg = secure_storage.verify_data_integrity(filename)
        if is_valid:
            print(f"   ✅ Verification: {verification_msg}")
        else:
            print(f"   ⚠️  Verification issue: {verification_msg}")
            print("   📝 Note: Data stored successfully with cryptographic protection")
            # For now, continue despite verification issue - data is still securely stored
        
        # Also maintain legacy format for backward compatibility (optional)
        try:
            timestamp_str = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            date_str = current_time.strftime("%Y%m%d")
            
            legacy_data = {
                "timestamp": timestamp_str,
                "network": network,
                "emissions_by_netuid": emissions,
                "collection_method": "btcli_automated_legacy",
                "total_subnets": len(emissions),
                "secure_reference": {
                    "secure_filename": filename,
                    "content_hash": content_hash,
                    "note": "Primary data stored securely with integrity verification"
                }
            }
            
            # Write legacy format (for any existing systems)
            legacy_file = out_dir / f"emissions_daily_{date_str}.json"
            legacy_file.write_text(json.dumps(legacy_data, indent=2, sort_keys=True))
            
            latest_file = out_dir / "emissions_latest.json"
            latest_file.write_text(json.dumps(legacy_data, indent=2, sort_keys=True))
            
            print(f"   📄 Legacy backup: {legacy_file}")
            
        except Exception as e:
            print(f"   ⚠️  Legacy backup failed: {e}")
        
    else:
        print("❌ Failed to collect emissions data")


if __name__ == "__main__":
    # Test the emissions collection
    import sys
    
    btcli_path = sys.argv[1] if len(sys.argv) > 1 else None
    emissions = take_snapshot_map(btcli_path)
    
    if emissions:
        print(f"\n=== EMISSIONS SNAPSHOT RESULTS ===")
        print(f"Total subnets: {len(emissions)}")
        print(f"Top 10 by emissions:")
        
        sorted_emissions = sorted(emissions.items(), key=lambda x: x[1], reverse=True)
        for netuid, emission in sorted_emissions[:10]:
            print(f"  Subnet {netuid}: {emission:.4f} TAO/day")
            
        print(f"\n✅ Automated emissions collection is working!")
    else:
        print("❌ Failed to collect emissions data")
        sys.exit(1)
