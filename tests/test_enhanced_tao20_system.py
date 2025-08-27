#!/usr/bin/env python3
"""
Comprehensive tests for the Enhanced TAO20 System
Tests vault manager, API, and integration functionality
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import time

from subnet.vault.substrate_vault_manager import SubstrateVaultManager, DepositInfo, VaultState
from subnet.api.tao20_minting_api import TAO20MintingAPI


class TestSubstrateVaultManager:
    """Test the Substrate Vault Manager"""
    
    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"deposits": {}, "vault_state": {"total_deposits": {}, "total_tao20_minted": 0.0, "last_nav_update": 0.0, "current_nav": 0.0, "fees_accrued": 0.0}, "deposit_counter": 0}')
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        Path(temp_file).unlink(missing_ok=True)
    
    @pytest.fixture
    def vault_manager(self, temp_state_file):
        """Create a vault manager instance for testing"""
        with patch('subnet.vault.substrate_vault_manager.bt.subtensor'):
            manager = SubstrateVaultManager(
                vault_coldkey="test_vault_coldkey",
                vault_hotkey="test_vault_hotkey",
                state_file=temp_state_file
            )
            return manager
    
    def test_vault_manager_initialization(self, vault_manager):
        """Test vault manager initialization"""
        assert vault_manager.vault_coldkey == "test_vault_coldkey"
        assert vault_manager.vault_hotkey == "test_vault_hotkey"
        assert vault_manager.deposits == {}
        assert vault_manager.deposit_counter == 0
    
    def test_create_deposit_id(self, vault_manager):
        """Test deposit ID creation"""
        deposit_id = vault_manager.create_deposit_id("user123", 1, 10.0)
        
        assert deposit_id.startswith("deposit_")
        assert len(deposit_id) > 20  # Should be reasonably long
        
        # Test uniqueness
        deposit_id2 = vault_manager.create_deposit_id("user123", 1, 10.0)
        assert deposit_id != deposit_id2
    
    @pytest.mark.asyncio
    async def test_track_deposit(self, vault_manager):
        """Test deposit tracking"""
        with patch.object(vault_manager, 'get_current_nav', return_value=1.5):
            deposit_id = await vault_manager.track_deposit("user123", 1, 10.0)
            
            assert deposit_id in vault_manager.deposits
            deposit = vault_manager.deposits[deposit_id]
            
            assert deposit.user_address == "user123"
            assert deposit.netuid == 1
            assert deposit.amount == 10.0
            assert deposit.nav_at_deposit == 1.5
            assert deposit.status == "pending"
    
    @pytest.mark.asyncio
    async def test_verify_deposit_success(self, vault_manager):
        """Test successful deposit verification"""
        # First track a deposit
        with patch.object(vault_manager, 'get_current_nav', return_value=1.5):
            deposit_id = await vault_manager.track_deposit("user123", 1, 10.0)
        
        # Mock vault stake to be sufficient
        with patch.object(vault_manager, 'get_vault_stake', return_value=15.0):
            result = await vault_manager.verify_deposit("user123", deposit_id)
            
            assert result is True
            assert vault_manager.deposits[deposit_id].status == "confirmed"
    
    @pytest.mark.asyncio
    async def test_verify_deposit_insufficient_stake(self, vault_manager):
        """Test deposit verification with insufficient stake"""
        # First track a deposit
        with patch.object(vault_manager, 'get_current_nav', return_value=1.5):
            deposit_id = await vault_manager.track_deposit("user123", 1, 10.0)
        
        # Mock vault stake to be insufficient
        with patch.object(vault_manager, 'get_vault_stake', return_value=5.0):
            result = await vault_manager.verify_deposit("user123", deposit_id)
            
            assert result is False
            assert vault_manager.deposits[deposit_id].status == "pending"
    
    @pytest.mark.asyncio
    async def test_verify_deposit_wrong_user(self, vault_manager):
        """Test deposit verification with wrong user"""
        # First track a deposit
        with patch.object(vault_manager, 'get_current_nav', return_value=1.5):
            deposit_id = await vault_manager.track_deposit("user123", 1, 10.0)
        
        # Try to verify with wrong user
        result = await vault_manager.verify_deposit("wrong_user", deposit_id)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_calculate_tao20_amount(self, vault_manager):
        """Test TAO20 amount calculation"""
        # First track a deposit
        with patch.object(vault_manager, 'get_current_nav', return_value=1.5):
            deposit_id = await vault_manager.track_deposit("user123", 1, 10.0)
        
        tao20_amount = await vault_manager.calculate_tao20_amount(deposit_id)
        
        # 10.0 / 1.5 = 6.666...
        assert abs(tao20_amount - 6.666666666666667) < 0.001
        assert vault_manager.deposits[deposit_id].tao20_amount == tao20_amount
    
    @pytest.mark.asyncio
    async def test_mark_deposit_minted(self, vault_manager):
        """Test marking deposit as minted"""
        # First track a deposit
        with patch.object(vault_manager, 'get_current_nav', return_value=1.5):
            deposit_id = await vault_manager.track_deposit("user123", 1, 10.0)
        
        # Calculate TAO20 amount
        await vault_manager.calculate_tao20_amount(deposit_id)
        
        # Mark as minted
        await vault_manager.mark_deposit_minted(deposit_id, "tx_hash_123")
        
        deposit = vault_manager.deposits[deposit_id]
        assert deposit.status == "minted"
        assert deposit.transaction_hash == "tx_hash_123"
        assert vault_manager.vault_state.total_tao20_minted > 0
    
    @pytest.mark.asyncio
    async def test_mark_deposit_failed(self, vault_manager):
        """Test marking deposit as failed"""
        # First track a deposit
        with patch.object(vault_manager, 'get_current_nav', return_value=1.5):
            deposit_id = await vault_manager.track_deposit("user123", 1, 10.0)
        
        # Mark as failed
        await vault_manager.mark_deposit_failed(deposit_id, "Transaction failed")
        
        deposit = vault_manager.deposits[deposit_id]
        assert deposit.status == "failed"
        assert deposit.error_message == "Transaction failed"
    
    def test_get_deposit_status(self, vault_manager):
        """Test getting deposit status"""
        # Add a test deposit
        deposit_info = DepositInfo(
            deposit_id="test_deposit",
            user_address="user123",
            netuid=1,
            amount=10.0,
            timestamp=time.time(),
            nav_at_deposit=1.5,
            status="pending"
        )
        vault_manager.deposits["test_deposit"] = deposit_info
        
        status = vault_manager.get_deposit_status("test_deposit")
        assert status is not None
        assert status["deposit_id"] == "test_deposit"
        assert status["user_address"] == "user123"
    
    def test_get_user_deposits(self, vault_manager):
        """Test getting user deposits"""
        # Add test deposits
        deposit1 = DepositInfo(
            deposit_id="deposit1",
            user_address="user123",
            netuid=1,
            amount=10.0,
            timestamp=time.time(),
            nav_at_deposit=1.5,
            status="pending"
        )
        deposit2 = DepositInfo(
            deposit_id="deposit2",
            user_address="user123",
            netuid=2,
            amount=20.0,
            timestamp=time.time(),
            nav_at_deposit=1.5,
            status="confirmed"
        )
        deposit3 = DepositInfo(
            deposit_id="deposit3",
            user_address="other_user",
            netuid=1,
            amount=5.0,
            timestamp=time.time(),
            nav_at_deposit=1.5,
            status="pending"
        )
        
        vault_manager.deposits["deposit1"] = deposit1
        vault_manager.deposits["deposit2"] = deposit2
        vault_manager.deposits["deposit3"] = deposit3
        
        user_deposits = vault_manager.get_user_deposits("user123")
        assert len(user_deposits) == 2
        assert all(deposit["user_address"] == "user123" for deposit in user_deposits)
    
    def test_get_vault_summary(self, vault_manager):
        """Test getting vault summary"""
        # Add some deposits to vault state
        vault_manager.vault_state.total_deposits = {1: 10.0, 2: 20.0}
        vault_manager.vault_state.total_tao20_minted = 15.0
        vault_manager.vault_state.current_nav = 1.5
        
        summary = vault_manager.get_vault_summary()
        
        assert summary["total_deposits_value"] == 30.0
        assert summary["total_tao20_minted"] == 15.0
        assert summary["current_nav"] == 1.5
        assert summary["total_deposits_count"] == 0  # No deposits in deposits dict
    
    @pytest.mark.asyncio
    async def test_cleanup_old_deposits(self, vault_manager):
        """Test cleanup of old deposits"""
        # Add old completed deposits
        old_time = time.time() - (31 * 24 * 3600)  # 31 days ago
        
        deposit1 = DepositInfo(
            deposit_id="old_minted",
            user_address="user123",
            netuid=1,
            amount=10.0,
            timestamp=old_time,
            nav_at_deposit=1.5,
            status="minted"
        )
        deposit2 = DepositInfo(
            deposit_id="old_failed",
            user_address="user123",
            netuid=1,
            amount=10.0,
            timestamp=old_time,
            nav_at_deposit=1.5,
            status="failed"
        )
        deposit3 = DepositInfo(
            deposit_id="recent_pending",
            user_address="user123",
            netuid=1,
            amount=10.0,
            timestamp=time.time(),
            nav_at_deposit=1.5,
            status="pending"
        )
        
        vault_manager.deposits["old_minted"] = deposit1
        vault_manager.deposits["old_failed"] = deposit2
        vault_manager.deposits["recent_pending"] = deposit3
        
        # Clean up deposits older than 30 days
        await vault_manager.cleanup_old_deposits(30)
        
        # Old deposits should be removed, recent one should remain
        assert "old_minted" not in vault_manager.deposits
        assert "old_failed" not in vault_manager.deposits
        assert "recent_pending" in vault_manager.deposits
    
    @pytest.mark.asyncio
    async def test_validate_deposit_batch(self, vault_manager):
        """Test batch deposit validation"""
        # Add test deposits
        deposit1 = DepositInfo(
            deposit_id="confirmed1",
            user_address="user123",
            netuid=1,
            amount=10.0,
            timestamp=time.time(),
            nav_at_deposit=1.5,
            status="confirmed"
        )
        deposit2 = DepositInfo(
            deposit_id="pending1",
            user_address="user123",
            netuid=1,
            amount=10.0,
            timestamp=time.time(),
            nav_at_deposit=1.5,
            status="pending"
        )
        
        vault_manager.deposits["confirmed1"] = deposit1
        vault_manager.deposits["pending1"] = deposit2
        
        valid_deposits, invalid_deposits = await vault_manager.validate_deposit_batch([
            "confirmed1", "pending1", "nonexistent"
        ])
        
        assert valid_deposits == ["confirmed1"]
        assert "pending1" in invalid_deposits
        assert "nonexistent" in invalid_deposits


class TestTAO20MintingAPI:
    """Test the TAO20 Minting API"""
    
    @pytest.fixture
    def mock_api(self):
        """Create a mock API instance"""
        with patch('subnet.api.tao20_minting_api.SubstrateVaultManager'), \
             patch('subnet.api.tao20_minting_api.TAO20Miner'), \
             patch('subnet.api.tao20_minting_api.Web3'):
            
            api = TAO20MintingAPI(
                vault_coldkey="test_vault_coldkey",
                vault_hotkey="test_vault_hotkey",
                contract_address="0x1234567890123456789012345678901234567890",
                rpc_url="http://127.0.0.1:9944",
                miner_wallet_path="/path/to/wallet",
                miner_hotkey_path="/path/to/hotkey"
            )
            
            # Mock the contract
            api.contract = MagicMock()
            
            return api
    
    def test_create_deposit_message(self, mock_api):
        """Test deposit message creation"""
        deposit_info = {
            'amount': 10.0,
            'netuid': 1,
            'timestamp': 1234567890,
            'deposit_id': 'test_deposit_123'
        }
        
        message = mock_api._create_deposit_message(deposit_info)
        
        expected = (
            "I confirm I deposited 10.0 alpha tokens "
            "from subnet 1 to the TAO20 vault "
            "at timestamp 1234567890. "
            "Deposit ID: test_deposit_123"
        )
        
        assert message == expected
    
    def test_verify_signature_success(self, mock_api):
        """Test successful signature verification"""
        deposit_info = {
            'amount': 10.0,
            'netuid': 1,
            'timestamp': 1234567890,
            'deposit_id': 'test_deposit_123'
        }
        
        message = mock_api._create_deposit_message(deposit_info)
        
        with patch('subnet.api.tao20_minting_api.Account.recover_message') as mock_recover:
            mock_recover.return_value = "0x1234567890123456789012345678901234567890"
            
            result = mock_api.verify_signature(
                "0x1234567890123456789012345678901234567890",
                deposit_info,
                "signature_here",
                message
            )
            
            assert result is True
    
    def test_verify_signature_wrong_address(self, mock_api):
        """Test signature verification with wrong address"""
        deposit_info = {
            'amount': 10.0,
            'netuid': 1,
            'timestamp': 1234567890,
            'deposit_id': 'test_deposit_123'
        }
        
        message = mock_api._create_deposit_message(deposit_info)
        
        with patch('subnet.api.tao20_minting_api.Account.recover_message') as mock_recover:
            mock_recover.return_value = "0x9876543210987654321098765432109876543210"
            
            result = mock_api.verify_signature(
                "0x1234567890123456789012345678901234567890",
                deposit_info,
                "signature_here",
                message
            )
            
            assert result is False
    
    def test_verify_signature_wrong_message(self, mock_api):
        """Test signature verification with wrong message"""
        deposit_info = {
            'amount': 10.0,
            'netuid': 1,
            'timestamp': 1234567890,
            'deposit_id': 'test_deposit_123'
        }
        
        result = mock_api.verify_signature(
            "0x1234567890123456789012345678901234567890",
            deposit_info,
            "signature_here",
            "wrong message"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_process_mint_request_success(self, mock_api):
        """Test successful mint request processing"""
        deposit_info = {
            'deposit_id': 'test_deposit_123',
            'amount': 10.0,
            'netuid': 1,
            'timestamp': 1234567890,
            'nav_at_deposit': 1.5
        }
        
        message = mock_api._create_deposit_message(deposit_info)
        
        # Mock all the verification steps
        with patch.object(mock_api, 'verify_signature', return_value=True), \
             patch.object(mock_api.vault_manager, 'verify_deposit', return_value=True), \
             patch.object(mock_api.vault_manager, 'calculate_tao20_amount', return_value=6.666666666666667), \
             patch.object(mock_api, '_execute_mint', return_value=(True, "tx_hash_123")), \
             patch.object(mock_api.vault_manager, 'mark_deposit_minted'):
            
            result = await mock_api.process_mint_request(
                "0x1234567890123456789012345678901234567890",
                deposit_info,
                "signature_here",
                message
            )
            
            assert result['success'] is True
            assert result['deposit_id'] == 'test_deposit_123'
            assert result['tao20_amount'] == 6.666666666666667
            assert result['transaction_hash'] == "tx_hash_123"
    
    @pytest.mark.asyncio
    async def test_process_mint_request_invalid_signature(self, mock_api):
        """Test mint request with invalid signature"""
        deposit_info = {
            'deposit_id': 'test_deposit_123',
            'amount': 10.0,
            'netuid': 1,
            'timestamp': 1234567890,
            'nav_at_deposit': 1.5
        }
        
        message = mock_api._create_deposit_message(deposit_info)
        
        with patch.object(mock_api, 'verify_signature', return_value=False):
            result = await mock_api.process_mint_request(
                "0x1234567890123456789012345678901234567890",
                deposit_info,
                "signature_here",
                message
            )
            
            assert result['success'] is False
            assert result['error'] == 'Invalid signature'
    
    @pytest.mark.asyncio
    async def test_process_mint_request_deposit_not_found(self, mock_api):
        """Test mint request with deposit not found"""
        deposit_info = {
            'deposit_id': 'test_deposit_123',
            'amount': 10.0,
            'netuid': 1,
            'timestamp': 1234567890,
            'nav_at_deposit': 1.5
        }
        
        message = mock_api._create_deposit_message(deposit_info)
        
        with patch.object(mock_api, 'verify_signature', return_value=True), \
             patch.object(mock_api.vault_manager, 'verify_deposit', return_value=False):
            
            result = await mock_api.process_mint_request(
                "0x1234567890123456789012345678901234567890",
                deposit_info,
                "signature_here",
                message
            )
            
            assert result['success'] is False
            assert result['error'] == 'Deposit not found or insufficient'
    
    @pytest.mark.asyncio
    async def test_process_mint_request_blockchain_failure(self, mock_api):
        """Test mint request with blockchain failure"""
        deposit_info = {
            'deposit_id': 'test_deposit_123',
            'amount': 10.0,
            'netuid': 1,
            'timestamp': 1234567890,
            'nav_at_deposit': 1.5
        }
        
        message = mock_api._create_deposit_message(deposit_info)
        
        with patch.object(mock_api, 'verify_signature', return_value=True), \
             patch.object(mock_api.vault_manager, 'verify_deposit', return_value=True), \
             patch.object(mock_api.vault_manager, 'calculate_tao20_amount', return_value=6.666666666666667), \
             patch.object(mock_api, '_execute_mint', return_value=(False, None)), \
             patch.object(mock_api.vault_manager, 'mark_deposit_failed'):
            
            result = await mock_api.process_mint_request(
                "0x1234567890123456789012345678901234567890",
                deposit_info,
                "signature_here",
                message
            )
            
            assert result['success'] is False
            assert result['error'] == 'Blockchain transaction failed'


class TestIntegration:
    """Integration tests for the complete system"""
    
    @pytest.mark.asyncio
    async def test_complete_minting_flow(self):
        """Test the complete minting flow end-to-end"""
        # This would test the complete flow from deposit tracking to minting
        # In a real test, you would need to mock the blockchain interactions
        pass
    
    @pytest.mark.asyncio
    async def test_batch_minting(self):
        """Test batch minting functionality"""
        # This would test processing multiple mint requests
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
