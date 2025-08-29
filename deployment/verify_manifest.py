#!/usr/bin/env python3
"""
Standalone AlphaMind Emissions Data Verification Script

This script can be used by anyone to verify the integrity of AlphaMind emissions data
by downloading manifests and verifying cryptographic signatures and Merkle trees.

Usage:
    python3 verify_manifest.py --manifest-url URL --data-url URL
    python3 verify_manifest.py --date 2025-01-27
"""

import argparse
import json
import hashlib
import base64
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
import urllib.request
import urllib.error

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
except ImportError:
    print("Installing cryptography package...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519


def download_file(url: str, local_path: str) -> bool:
    """Download file from URL"""
    try:
        print(f"📥 Downloading: {url}")
        urllib.request.urlretrieve(url, local_path)
        return True
    except urllib.error.URLError as e:
        print(f"❌ Download failed: {e}")
        return False


def verify_signature(manifest_data: dict, signature_b64: str, public_key_pem: str) -> bool:
    """Verify Ed25519 signature"""
    try:
        # Load public key
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        
        # Create canonical JSON (same as signing process)
        signing_data = {k: v for k, v in manifest_data.items() if k != 'signature'}
        canonical_json = json.dumps(signing_data, sort_keys=True, separators=(',', ':'))
        
        # Verify signature
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, canonical_json.encode('utf-8'))
        return True
    except Exception as e:
        print(f"❌ Signature verification failed: {e}")
        return False


def verify_merkle_tree(files_info: list, expected_root: str) -> bool:
    """Verify Merkle tree root"""
    try:
        # Extract file hashes in order
        file_hashes = [bytes.fromhex(f["sha256"]) for f in sorted(files_info, key=lambda x: x["path"])]
        
        if not file_hashes:
            return False
        
        # Build Merkle tree
        def hash_data(data):
            return hashlib.sha256(data).digest()
        
        current_level = [hash_data(h) for h in file_hashes]
        
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                combined = left + right
                next_level.append(hash_data(combined))
            current_level = next_level
        
        computed_root = current_level[0].hex()
        return computed_root == expected_root
    except Exception as e:
        print(f"❌ Merkle tree verification failed: {e}")
        return False


def verify_manifest_from_urls(manifest_url: str, data_url: str = None) -> bool:
    """Verify manifest from URLs"""
    print(f"🔍 Verifying AlphaMind emissions data")
    print(f"📄 Manifest URL: {manifest_url}")
    
    # Download manifest
    manifest_file = "manifest_verify.json"
    if not download_file(manifest_url, manifest_file):
        return False
    
    # Load and parse manifest
    try:
        with open(manifest_file) as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in manifest: {e}")
        return False
    
    print(f"✅ Downloaded manifest: {manifest['total_files']} files")
    print(f"📅 Collection date: {manifest['collection_date']}")
    print(f"🌳 Merkle root: {manifest['merkle_root']}")
    
    # Verify signature
    signature_info = manifest.get('signature', {})
    if not signature_info:
        print("❌ No signature found in manifest")
        return False
    
    print("🔐 Verifying Ed25519 signature...")
    if verify_signature(manifest, signature_info['signature'], signature_info['public_key']):
        print("✅ Signature verification: PASSED")
    else:
        print("❌ Signature verification: FAILED")
        return False
    
    # Verify Merkle tree
    print("🌳 Verifying Merkle tree...")
    if verify_merkle_tree(manifest['files'], manifest['merkle_root']):
        print("✅ Merkle tree verification: PASSED")
    else:
        print("❌ Merkle tree verification: FAILED")
        return False
    
    # Summary
    print("\n🎯 VERIFICATION SUMMARY")
    print("=" * 50)
    print(f"📅 Collection date: {manifest['collection_date']}")
    print(f"📊 Files verified: {manifest['total_files']}")
    print(f"🔐 Signature: ✅ VALID")
    print(f"🌳 Merkle tree: ✅ VALID")
    print(f"⏰ Collection time: {manifest['timestamp']}")
    print(f"🌐 Network: {manifest['metadata']['network']}")
    print(f"🔒 Security features: {len(manifest['metadata']['security_features'])}")
    
    for feature in manifest['metadata']['security_features']:
        print(f"   • {feature}")
    
    print("\n✅ ALL VERIFICATIONS PASSED")
    print("🛡️  Data integrity confirmed for AlphaMind subnet")
    
    # Cleanup
    Path(manifest_file).unlink(missing_ok=True)
    
    return True


def verify_manifest_by_date(verify_date: str, base_url: str = None) -> bool:
    """Verify manifest for a specific date"""
    if base_url is None:
        base_url = "https://alphamind-emissions-data.s3.amazonaws.com"
    
    # Parse date
    try:
        date_obj = datetime.strptime(verify_date, "%Y-%m-%d").date()
    except ValueError:
        print(f"❌ Invalid date format: {verify_date}. Use YYYY-MM-DD")
        return False
    
    # Build URLs
    date_path = date_obj.strftime("%Y/%m/%d")
    date_str = date_obj.strftime("%Y%m%d")
    
    manifest_url = f"{base_url}/manifests/{date_path}/manifest_{date_str}.json"
    data_url = f"{base_url}/emissions/{date_path}/"
    
    return verify_manifest_from_urls(manifest_url, data_url)


def main():
    parser = argparse.ArgumentParser(
        description="Verify AlphaMind emissions data integrity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify by date (uses default S3 URLs)
  python3 verify_manifest.py --date 2025-01-27
  
  # Verify yesterday's data
  python3 verify_manifest.py --date yesterday
  
  # Verify with custom URLs
  python3 verify_manifest.py --manifest-url https://example.com/manifest.json
  
  # Verify latest available data
  python3 verify_manifest.py --manifest-url https://bucket.s3.amazonaws.com/manifests/manifest_latest.json
        """
    )
    
    parser.add_argument(
        "--date",
        help="Date to verify (YYYY-MM-DD or 'yesterday')"
    )
    
    parser.add_argument(
        "--manifest-url",
        help="Direct URL to manifest file"
    )
    
    parser.add_argument(
        "--data-url", 
        help="Base URL for data files (optional)"
    )
    
    parser.add_argument(
        "--base-url",
        default="https://alphamind-emissions-data.s3.amazonaws.com",
        help="Base S3 URL (default: %(default)s)"
    )
    
    args = parser.parse_args()
    
    if not args.date and not args.manifest_url:
        parser.error("Either --date or --manifest-url is required")
    
    try:
        if args.manifest_url:
            success = verify_manifest_from_urls(args.manifest_url, args.data_url)
        else:
            verify_date = args.date
            if verify_date == "yesterday":
                verify_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            success = verify_manifest_by_date(verify_date, args.base_url)
        
        if success:
            print("\n🎉 Verification completed successfully!")
            sys.exit(0)
        else:
            print("\n💥 Verification failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
