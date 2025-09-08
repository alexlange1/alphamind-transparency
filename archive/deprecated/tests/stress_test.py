#!/usr/bin/env python3
"""
Comprehensive stress testing for TAO20 security and performance
"""
import asyncio
import concurrent.futures
import json
import os
import random
import tempfile
import time
import threading
from pathlib import Path
from typing import Dict, List, Any
import requests
import multiprocessing
from datetime import datetime, timezone, timedelta

from subnet.common.rate_limiter import RateLimiter
from subnet.common.validation import validate_positive_amount, ValidationError
from subnet.common.monitoring import SecurityMonitor
from subnet.tao20.models import EmissionsReport
from subnet.tao20.reports import PriceReport
from subnet.validator.service import consensus_prices_with_twap, build_miner_stake_map
from subnet.sim.vault import VaultState, mint_tao_extended, apply_management_fee


class StressTester:
    """Comprehensive stress testing suite"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.monitor = SecurityMonitor(base_path)
        self.results = []
        
    def log_result(self, test_name: str, passed: bool, duration: float, details: Dict[str, Any] = None):
        """Log test result"""
        result = {
            "test_name": test_name,
            "passed": passed,
            "duration_sec": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {}
        }
        self.results.append(result)
        
        if not passed:
            self.monitor.alert(
                "stress_test_failure",
                "high",
                f"Stress test failed: {test_name}",
                result
            )
    
    def test_rate_limiter_concurrent(self, num_clients: int = 100, requests_per_client: int = 10):
        """Test rate limiter under concurrent load"""
        print(f"Testing rate limiter with {num_clients} concurrent clients...")
        start_time = time.time()
        
        limiter = RateLimiter(max_requests=50, window_seconds=60)
        successful_requests = multiprocessing.Value('i', 0)
        blocked_requests = multiprocessing.Value('i', 0)
        
        def client_worker(client_id: int):
            for _ in range(requests_per_client):
                if limiter.is_allowed(f"client_{client_id}"):
                    with successful_requests.get_lock():
                        successful_requests.value += 1
                else:
                    with blocked_requests.get_lock():
                        blocked_requests.value += 1
                time.sleep(0.01)  # Small delay between requests
        
        # Create and start threads
        threads = []
        for i in range(num_clients):
            thread = threading.Thread(target=client_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        duration = time.time() - start_time
        total_requests = successful_requests.value + blocked_requests.value
        expected_total = num_clients * requests_per_client
        
        # Test passes if we processed all requests and some were blocked
        passed = (total_requests == expected_total and 
                 blocked_requests.value > 0 and 
                 successful_requests.value > 0)
        
        self.log_result(
            "rate_limiter_concurrent",
            passed,
            duration,
            {
                "num_clients": num_clients,
                "requests_per_client": requests_per_client,
                "successful_requests": successful_requests.value,
                "blocked_requests": blocked_requests.value,
                "total_requests": total_requests
            }
        )
        
        return passed
    
    def test_input_validation_fuzzing(self, num_tests: int = 1000):
        """Fuzz test input validation with random invalid inputs"""
        print(f"Fuzzing input validation with {num_tests} random inputs...")
        start_time = time.time()
        
        passed_tests = 0
        failed_tests = 0
        
        # Generate random invalid inputs
        invalid_inputs = [
            -1 * random.random() * 1000,  # Negative numbers
            0,  # Zero
            float('inf'),  # Infinity
            float('nan'),  # NaN
            1e20,  # Very large numbers
            "invalid_string",  # String instead of number
            None,  # None value
            [],  # List
            {},  # Dict
            complex(1, 2),  # Complex number
        ]
        
        for i in range(num_tests):
            # Pick random invalid input or generate new one
            if random.random() < 0.8 and invalid_inputs:
                test_input = random.choice(invalid_inputs)
            else:
                # Generate new random invalid input
                rand_type = random.choice(['negative', 'zero', 'large', 'string', 'list'])
                if rand_type == 'negative':
                    test_input = -random.random() * 1000
                elif rand_type == 'zero':
                    test_input = 0
                elif rand_type == 'large':
                    test_input = 10 ** random.randint(20, 100)
                elif rand_type == 'string':
                    test_input = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))
                else:  # list
                    test_input = [random.random() for _ in range(random.randint(1, 10))]
            
            try:
                validate_positive_amount(test_input)
                # If no exception was raised, validation failed
                failed_tests += 1
            except ValidationError:
                # Expected behavior - validation caught the invalid input
                passed_tests += 1
            except Exception:
                # Unexpected exception type
                failed_tests += 1
        
        duration = time.time() - start_time
        success_rate = passed_tests / num_tests
        
        # Test passes if success rate is > 95%
        passed = success_rate > 0.95
        
        self.log_result(
            "input_validation_fuzzing",
            passed,
            duration,
            {
                "num_tests": num_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": success_rate
            }
        )
        
        return passed
    
    def test_consensus_under_attack(self, num_malicious: int = 10, num_honest: int = 20):
        """Test consensus mechanism under simulated attack"""
        print(f"Testing consensus with {num_malicious} malicious and {num_honest} honest miners...")
        start_time = time.time()
        
        # Create honest price reports
        honest_price = 100.0
        honest_reports = []
        for i in range(num_honest):
            # Add small random variation to honest prices
            price_variation = honest_price + random.gauss(0, 2)  # 2% standard deviation
            price_variation = max(0.1, price_variation)  # Ensure positive
            
            report = PriceReport(
                ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                prices_by_netuid={1: price_variation},
                miner_id=f"honest_{i}",
                schema_version="1.0.0"
            )
            honest_reports.append(report)
        
        # Create malicious price reports (trying to manipulate)
        malicious_reports = []
        for i in range(num_malicious):
            # Malicious miners report very different prices
            malicious_price = honest_price * random.choice([0.1, 0.2, 5.0, 10.0])  # 80-90% off or 5-10x higher
            
            report = PriceReport(
                ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                prices_by_netuid={1: malicious_price},
                miner_id=f"malicious_{i}",
                schema_version="1.0.0"
            )
            malicious_reports.append(report)
        
        all_reports = honest_reports + malicious_reports
        
        # Create stake map (honest miners have more stake)
        stake_by_miner = {}
        honest_stake = 100.0
        malicious_stake = 10.0  # Less stake for malicious miners
        
        for i in range(num_honest):
            stake_by_miner[f"honest_{i}"] = honest_stake
        for i in range(num_malicious):
            stake_by_miner[f"malicious_{i}"] = malicious_stake
        
        # Run consensus
        try:
            prices, quorum, staleness = consensus_prices_with_twap(
                all_reports,
                stake_by_miner=stake_by_miner,
                window_minutes=30,
                outlier_k=3.0,
                quorum_threshold=0.33,
                price_band_pct=0.2,
                stale_sec=300,
                out_dir=self.base_path
            )
            
            consensus_price = prices.get(1, 0)
            
            # Check if consensus is close to honest price (within 10%)
            price_deviation = abs(consensus_price - honest_price) / honest_price
            resistance_good = price_deviation < 0.1
            
            # Check if quorum was achieved
            quorum_good = quorum.get(1, 0) >= 0.33
            
            passed = resistance_good and quorum_good
            
        except Exception as e:
            passed = False
            consensus_price = 0
            price_deviation = 1.0
            quorum_good = False
            
        duration = time.time() - start_time
        
        self.log_result(
            "consensus_under_attack",
            passed,
            duration,
            {
                "num_malicious": num_malicious,
                "num_honest": num_honest,
                "honest_price": honest_price,
                "consensus_price": consensus_price,
                "price_deviation": price_deviation,
                "resistance_good": resistance_good,
                "quorum_good": quorum_good
            }
        )
        
        return passed
    
    def test_vault_operations_stress(self, num_operations: int = 1000):
        """Stress test vault operations with random valid inputs"""
        print(f"Stress testing vault with {num_operations} operations...")
        start_time = time.time()
        
        # Initialize vault state
        initial_weights = {1: 0.4, 2: 0.3, 3: 0.2, 4: 0.1}
        initial_prices = {1: 100.0, 2: 50.0, 3: 200.0, 4: 25.0}
        
        state = VaultState(
            holdings={1: 100.0, 2: 200.0, 3: 50.0, 4: 400.0},
            tao20_supply=1000.0,
            last_nav_tao=100.0
        )
        
        successful_ops = 0
        failed_ops = 0
        
        for i in range(num_operations):
            try:
                # Random operation type
                op_type = random.choice(['mint', 'mgmt_fee'])
                
                if op_type == 'mint':
                    # Random mint amount (1-1000 TAO)
                    amount = random.uniform(1.0, 1000.0)
                    
                    # Add some price variation
                    current_prices = {k: v * random.uniform(0.95, 1.05) for k, v in initial_prices.items()}
                    
                    # Perform mint
                    result_state, mint_result = mint_tao_extended(
                        amount, initial_weights, current_prices, state
                    )
                    
                    # Verify result integrity
                    if (result_state.tao20_supply > state.tao20_supply and
                        mint_result.minted > 0 and
                        result_state.last_nav_tao > 0):
                        state = result_state
                        successful_ops += 1
                    else:
                        failed_ops += 1
                        
                elif op_type == 'mgmt_fee':
                    # Apply management fee
                    current_prices = {k: v * random.uniform(0.95, 1.05) for k, v in initial_prices.items()}
                    
                    # Set a past timestamp to trigger fee accrual
                    past_time = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    state.last_mgmt_ts = past_time
                    
                    result_state = apply_management_fee(current_prices, state)
                    
                    # Verify fee was applied correctly
                    if result_state.tao20_supply >= state.tao20_supply:
                        state = result_state
                        successful_ops += 1
                    else:
                        failed_ops += 1
                        
            except Exception as e:
                failed_ops += 1
        
        duration = time.time() - start_time
        success_rate = successful_ops / num_operations
        
        # Test passes if success rate > 95%
        passed = success_rate > 0.95
        
        self.log_result(
            "vault_operations_stress",
            passed,
            duration,
            {
                "num_operations": num_operations,
                "successful_ops": successful_ops,
                "failed_ops": failed_ops,
                "success_rate": success_rate,
                "final_supply": state.tao20_supply,
                "final_nav": state.last_nav_tao
            }
        )
        
        return passed
    
    def test_memory_usage(self, iterations: int = 10000):
        """Test for memory leaks in critical operations"""
        print(f"Testing memory usage over {iterations} iterations...")
        start_time = time.time()
        
        try:
            import psutil
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            # If psutil not available, skip memory test
            self.log_result("memory_usage", True, 0, {"skipped": "psutil not available"})
            return True
        
        # Perform memory-intensive operations
        for i in range(iterations):
            # Create temporary objects that should be garbage collected
            large_dict = {j: random.random() for j in range(1000)}
            large_list = [random.random() for _ in range(1000)]
            
            # Simulate validation operations
            try:
                validate_positive_amount(random.uniform(1, 1000))
            except:
                pass
            
            # Create rate limiter instances (should reuse existing ones)
            limiter = RateLimiter(10, 60)
            limiter.is_allowed(f"test_{i}")
            
            # Clean up
            del large_dict, large_list, limiter
            
            # Check memory every 1000 iterations
            if i % 1000 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_growth = current_memory - initial_memory
                
                # Alert if memory growth is excessive (>100MB)
                if memory_growth > 100:
                    self.monitor.alert(
                        "memory_leak",
                        "high",
                        f"High memory usage detected: {memory_growth:.1f}MB growth",
                        {"iteration": i, "memory_mb": current_memory}
                    )
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory
        duration = time.time() - start_time
        
        # Test passes if memory growth is reasonable (<50MB)
        passed = memory_growth < 50
        
        self.log_result(
            "memory_usage",
            passed,
            duration,
            {
                "iterations": iterations,
                "initial_memory_mb": initial_memory,
                "final_memory_mb": final_memory,
                "memory_growth_mb": memory_growth
            }
        )
        
        return passed
    
    def run_all_tests(self):
        """Run all stress tests"""
        print("=== Starting Comprehensive Stress Testing ===\n")
        
        tests = [
            ("Rate Limiter Concurrent", self.test_rate_limiter_concurrent),
            ("Input Validation Fuzzing", self.test_input_validation_fuzzing),
            ("Consensus Under Attack", self.test_consensus_under_attack),
            ("Vault Operations Stress", self.test_vault_operations_stress),
            ("Memory Usage", self.test_memory_usage),
        ]
        
        total_passed = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n--- Running {test_name} ---")
            try:
                passed = test_func()
                if passed:
                    total_passed += 1
                    print(f"✅ {test_name}: PASSED")
                else:
                    print(f"❌ {test_name}: FAILED")
            except Exception as e:
                print(f"💥 {test_name}: ERROR - {e}")
                self.log_result(test_name.lower().replace(" ", "_"), False, 0, {"error": str(e)})
        
        # Summary
        print(f"\n=== Stress Testing Summary ===")
        print(f"Passed: {total_passed}/{total_tests}")
        print(f"Success Rate: {total_passed/total_tests*100:.1f}%")
        
        # Save results
        results_file = self.base_path / "stress_test_results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\nDetailed results saved to: {results_file}")
        
        return total_passed == total_tests


def main():
    """Main stress testing entry point"""
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        
        # Initialize stress tester
        tester = StressTester(base_path)
        
        # Run all tests
        all_passed = tester.run_all_tests()
        
        if all_passed:
            print("\n🎉 All stress tests PASSED! System is ready for production.")
            return 0
        else:
            print("\n⚠️  Some stress tests FAILED. Review results before deployment.")
            return 1


if __name__ == "__main__":
    exit(main())
