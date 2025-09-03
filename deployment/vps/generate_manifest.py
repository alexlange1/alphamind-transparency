#!/usr/bin/env python3
"""
Generate cryptographic manifest for AlphaMind emissions data
Creates Merkle tree and Ed25519 signature for integrity verification
"""

import json
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple
import base64

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Installing cryptography package...")
    os.system("pip install cryptography")
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.backends import default_backend


class MerkleTree:
    """Simple Merkle tree implementation for file integrity verification"""
    
    def __init__(self, data_items: List[bytes]):
        self.data_items = data_items
        self.tree = self._build_tree()
    
    def _hash(self, data: bytes) -> bytes:
        return hashlib.sha256(data).digest()
    
    def _build_tree(self) -> List[List[bytes]]:
        if not self.data_items:
            return []
        
        # Start with leaf nodes (hash of each data item)
        current_level = [self._hash(item) for item in self.data_items]
        tree = [current_level[:]]  # Store each level
        
        # Build tree bottom-up
        while len(current_level) > 1:
            next_level = []
            
            # Process pairs
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                
                # Hash the concatenation
                combined = left + right
                next_level.append(self._hash(combined))
            
            current_level = next_level
            tree.append(current_level[:])
        
        return tree
    
    def get_root(self) -> bytes:
        """Get the Merkle root hash"""
        if not self.tree:
            return b''
        return self.tree[-1][0] if self.tree[-1] else b''
    
    def get_root_hex(self) -> str:
        """Get the Merkle root as hex string"""
        return self.get_root().hex()


def load_signing_key() -> ed25519.Ed25519PrivateKey:
    """Load or generate Ed25519 signing key"""
    key_file = Path("secrets/signing_key.pem")
    
    if key_file.exists():
        with open(key_file, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        return private_key
    else:
        # Generate new key
        private_key = ed25519.Ed25519PrivateKey.generate()
        
        # Save private key
        key_file.parent.mkdir(parents=True, exist_ok=True)
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        with open(key_file, "wb") as f:
            f.write(pem)
        os.chmod(key_file, 0o600)
        
        # Save public key for verification
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        with open("secrets/public_key.pem", "wb") as f:
            f.write(public_pem)
        os.chmod("secrets/public_key.pem", 0o644)
        
        print(f"✅ Generated new Ed25519 key pair")
        
        return private_key


def collect_file_hashes(data_dir: Path) -> List[Dict[str, Any]]:
    """Collect hashes of all files in the secure data directory"""
    files_info = []
    
    for file_path in data_dir.rglob("*.json"):
        if file_path.is_file():
            # Calculate SHA-256 hash
            with open(file_path, "rb") as f:
                content = f.read()
                file_hash = hashlib.sha256(content).hexdigest()
            
            # Get file info
            stat = file_path.stat()
            relative_path = file_path.relative_to(data_dir.parent)
            
            files_info.append({
                "path": str(relative_path),
                "sha256": file_hash,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            })
    
    return sorted(files_info, key=lambda x: x["path"])


def generate_manifest() -> Dict[str, Any]:
    """Generate complete cryptographic manifest"""
    print("🔐 Generating cryptographic manifest...")
    
    # Collect all file information
    data_dir = Path("out/secure")
    files_info = collect_file_hashes(data_dir)
    
    if not files_info:
        raise ValueError("No files found in secure data directory")
    
    print(f"📁 Found {len(files_info)} files to include in manifest")
    
    # Create Merkle tree from file hashes
    file_hashes = [bytes.fromhex(f["sha256"]) for f in files_info]
    merkle_tree = MerkleTree(file_hashes)
    merkle_root = merkle_tree.get_root_hex()
    
    print(f"🌳 Merkle root: {merkle_root}")
    
    # Load signing key
    private_key = load_signing_key()
    public_key = private_key.public_key()
    
    # Create manifest data
    manifest_data = {
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "collection_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_files": len(files_info),
        "merkle_root": merkle_root,
        "files": files_info,
        "metadata": {
            "network": os.environ.get("BITTENSOR_NETWORK", "finney"),
            "collection_method": "btcli_automated_vps",
            "storage_backend": "s3_versioned",
            "security_features": [
                "sha256_file_hashing",
                "merkle_tree_verification", 
                "ed25519_signature",
                "s3_versioning",
                "atomic_writes"
            ]
        }
    }
    
    # Create canonical JSON for signing
    canonical_json = json.dumps(manifest_data, sort_keys=True, separators=(',', ':'))
    
    # Sign the manifest
    signature = private_key.sign(canonical_json.encode('utf-8'))
    signature_b64 = base64.b64encode(signature).decode('ascii')
    
    # Get public key for verification
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('ascii')
    
    # Add signature to manifest
    manifest_data["signature"] = {
        "algorithm": "Ed25519",
        "signature": signature_b64,
        "public_key": public_key_pem,
        "signed_data_hash": hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    }
    
    return manifest_data


def main():
    """Main manifest generation function"""
    try:
        # Generate manifest
        manifest = generate_manifest()
        
        # Save manifest
        manifest_dir = Path("manifests")
        manifest_dir.mkdir(parents=True, exist_ok=True)
        
        # Daily manifest
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        manifest_file = manifest_dir / f"manifest_{date_str}.json"
        
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        
        os.chmod(manifest_file, 0o644)
        
        # Latest manifest
        latest_file = manifest_dir / "manifest_latest.json"
        with open(latest_file, "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        
        os.chmod(latest_file, 0o644)
        
        print(f"✅ Manifest generated: {manifest_file}")
        print(f"📊 Files: {manifest['total_files']}")
        print(f"🌳 Merkle root: {manifest['merkle_root']}")
        print(f"🔐 Signature: {manifest['signature']['signature'][:16]}...")
        
        return manifest_file
        
    except Exception as e:
        print(f"❌ Error generating manifest: {e}")
        raise


if __name__ == "__main__":
    main()
