// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Script.sol";
import {Vault} from "../src/Vault.sol";
import {TAO20} from "../src/TAO20.sol";
import {OracleAggregator} from "../src/OracleAggregator.sol";

contract InteractScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        
        // Get deployed contract addresses from environment or previous deployment
        address vaultAddr = vm.envAddress("VAULT_ADDRESS");
        address oracleAddr = vm.envAddress("ORACLE_ADDRESS");
        
        Vault vault = Vault(vaultAddr);
        OracleAggregator oracle = OracleAggregator(oracleAddr);
        TAO20 token = vault.token();
        
        vm.startBroadcast(deployerPrivateKey);
        
        console.log("=== Interacting with deployed contracts ===");
        console.log("Vault:", address(vault));
        console.log("Oracle:", address(oracle));
        console.log("Token:", address(token));
        
        // Set some oracle prices for testing
        console.log("\n--- Setting Oracle Prices ---");
        oracle.submit(1, 1.2e18); // Netuid 1: 1.2 TAO per unit
        oracle.submit(2, 0.8e18); // Netuid 2: 0.8 TAO per unit
        console.log("Prices submitted to oracle");
        
        // Check prices
        uint256 price1 = oracle.getPrice(1);
        uint256 price2 = oracle.getPrice(2);
        console.log("Price for netuid 1:", price1);
        console.log("Price for netuid 2:", price2);
        
        // Mint some tokens in-kind
        console.log("\n--- Minting TAO20 tokens ---");
        vault.setCompositionToleranceBps(10000); // Allow any composition for testing
        
        uint256[] memory netuids = new uint256[](2);
        uint256[] memory quantities = new uint256[](2);
        netuids[0] = 1; netuids[1] = 2;
        quantities[0] = 100e18; quantities[1] = 200e18; // 100 units of netuid 1, 200 units of netuid 2
        
        uint256 minted = vault.mintInKind(netuids, quantities, vm.addr(deployerPrivateKey));
        console.log("Minted TAO20 tokens:", minted);
        
        // Check balances
        uint256 balance = token.balanceOf(vm.addr(deployerPrivateKey));
        uint256 totalSupply = token.totalSupply();
        uint256 nav = vault.navTau18();
        
        console.log("\n--- Vault Status ---");
        console.log("Your TAO20 balance:", balance);
        console.log("Total TAO20 supply:", totalSupply);
        console.log("NAV per token (TAU):", nav);
        console.log("Holdings netuid 1:", vault.holdings(1));
        console.log("Holdings netuid 2:", vault.holdings(2));
        
        // Test management fee accrual
        console.log("\n--- Management Fee Test ---");
        uint256 mgmtFee = vault.accrueMgmtFee();
        console.log("Management fee accrued:", mgmtFee);
        
        vm.stopBroadcast();
        
        console.log("\n=== Interaction Complete ===");
    }
}
