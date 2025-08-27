#!/usr/bin/env python3
"""
Verify Portfolio Holdings Match Target Weights
"""

import json
import subprocess
from pathlib import Path

def get_real_prices():
    """Get real prices from btcli"""
    try:
        btcli_path = "/Users/alexanderlange/.venvs/alphamind/bin/btcli"
        result = subprocess.run(
            [btcli_path, "subnets", "list", "--network", "finney"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            prices = {}
            for line in result.stdout.splitlines():
                if "│" in line and line.strip() and not line.startswith("─"):
                    parts = [p.strip() for p in line.split("│")]
                    if len(parts) >= 3 and parts[0].strip().isdigit():
                        try:
                            netuid = int(parts[0].strip())
                            price_str = parts[2].strip().split()[0].replace("τ/", "").replace("τ", "")
                            price = float(price_str)
                            prices[netuid] = price
                        except (ValueError, IndexError):
                            continue
            return prices
    except Exception as e:
        print(f"Error getting real prices: {e}")
        return {}

def get_vault_data():
    """Get vault state and weights"""
    vault_file = Path("subnet/out/vault_state.json")
    weights_file = Path("subnet/out/weights.json")
    
    vault_data = {}
    weights_data = {}
    
    if vault_file.exists():
        with open(vault_file) as f:
            vault_data = json.load(f)
    
    if weights_file.exists():
        with open(weights_file) as f:
            weights_data = json.load(f)
    
    return vault_data, weights_data

def main():
    print("🔍 Verifying Portfolio Holdings vs Target Weights")
    print("=" * 80)
    
    # Get data
    vault_data, weights_data = get_vault_data()
    real_prices = get_real_prices()
    
    holdings = vault_data.get('holdings', {})
    target_weights = weights_data.get('weights', {})
    total_supply = vault_data.get('tao20_supply', 0)
    current_nav = vault_data.get('last_nav_tao', 0)
    
    print(f"📊 Portfolio Summary:")
    print(f"  Total Supply: {total_supply:.2f} TAO20")
    print(f"  Current NAV: {current_nav:.8f} TAO")
    print(f"  Holdings: {len(holdings)} subnets")
    print(f"  Target Weights: {len(target_weights)} subnets")
    
    # Calculate total portfolio value
    total_value = current_nav * total_supply
    print(f"  Total Portfolio Value: {total_value:.2f} TAO")
    
    print(f"\n📋 Detailed Analysis:")
    print("-" * 100)
    print(f"{'Rank':<4} {'Netuid':<6} {'Target Wt':<10} {'Holdings':<12} {'Price':<10} {'Value':<12} {'Actual Wt':<10} {'Match':<6}")
    print("-" * 100)
    
    # Sort by target weight
    sorted_weights = sorted(target_weights.items(), key=lambda x: float(x[1]), reverse=True)
    
    total_actual_value = 0
    weight_matches = 0
    
    for rank, (netuid, target_weight) in enumerate(sorted_weights, 1):
        netuid = int(netuid)
        target_weight = float(target_weight)
        
        # Get holdings and price
        holding_units = holdings.get(str(netuid), 0.0)
        price = real_prices.get(netuid, 0.0)
        
        # Calculate actual value and weight
        actual_value = holding_units * price
        total_actual_value += actual_value
        
        actual_weight = actual_value / total_value if total_value > 0 else 0
        
        # Check if weights match (within 1% tolerance)
        weight_diff = abs(target_weight - actual_weight)
        weight_match = "✅" if weight_diff < 0.01 else "❌"
        if weight_diff < 0.01:
            weight_matches += 1
        
        print(f"{rank:<4} {netuid:<6} {target_weight:<10.4f} {holding_units:<12.2f} {price:<10.6f} {actual_value:<12.2f} {actual_weight:<10.4f} {weight_match:<6}")
    
    print("-" * 100)
    print(f"Total Actual Value: {total_actual_value:.2f} TAO")
    print(f"Expected Total Value: {total_value:.2f} TAO")
    print(f"Value Difference: {total_actual_value - total_value:.2f} TAO")
    
    print(f"\n📊 Weight Matching Summary:")
    print(f"  Total subnets: {len(sorted_weights)}")
    print(f"  Weight matches: {weight_matches}")
    print(f"  Weight mismatches: {len(sorted_weights) - weight_matches}")
    
    if weight_matches == len(sorted_weights):
        print(f"\n✅ PERFECT MATCH! Portfolio holdings exactly match target weights.")
    elif weight_matches >= len(sorted_weights) * 0.9:
        print(f"\n✅ GOOD MATCH! {weight_matches}/{len(sorted_weights)} weights match.")
    else:
        print(f"\n⚠️  POOR MATCH! Only {weight_matches}/{len(sorted_weights)} weights match.")
        print("Portfolio needs rebalancing to match target weights.")
    
    # Show specific mismatches
    if weight_matches < len(sorted_weights):
        print(f"\n📋 Weight Mismatches (Top 5):")
        print("-" * 50)
        mismatch_count = 0
        for netuid, target_weight in sorted_weights:
            netuid = int(netuid)
            target_weight = float(target_weight)
            holding_units = holdings.get(str(netuid), 0.0)
            price = real_prices.get(netuid, 0.0)
            actual_value = holding_units * price
            actual_weight = actual_value / total_value if total_value > 0 else 0
            weight_diff = abs(target_weight - actual_weight)
            
            if weight_diff >= 0.01 and mismatch_count < 5:
                print(f"Netuid {netuid}: Target={target_weight:.4f}, Actual={actual_weight:.4f}, Diff={weight_diff:.4f}")
                mismatch_count += 1

if __name__ == "__main__":
    main()
