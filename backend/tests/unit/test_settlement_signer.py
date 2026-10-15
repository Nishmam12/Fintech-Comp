"""Offline checks: signing, redaction, config guards. No DB, no network."""
import pytest
from eth_account import Account
from eth_utils import keccak

from budget_kernel.settlement.adapter import SettlementConfig, SettlementRefused, USDC_BASE_SEPOLIA
from budget_kernel.settlement.signer import Signer, transfer_data

KEY = "0x" + "11" * 32  # deterministic throwaway test key, never funded
TO = "0x000000000000000000000000000000000000dEaD"


def test_signed_transfer_is_deterministic_and_decodes():
    s = Signer(KEY)
    a = s.sign_transfer(chain_id=84532, nonce=7, token=USDC_BASE_SEPOLIA, to=TO, amount=250_000, max_fee=2 * 10**9, priority_fee=10**8)
    b = s.sign_transfer(chain_id=84532, nonce=7, token=USDC_BASE_SEPOLIA, to=TO, amount=250_000, max_fee=2 * 10**9, priority_fee=10**8)
    assert a == b and a[1] == "0x" + keccak(a[0]).hex()
    assert transfer_data(TO, 250_000)[:4].hex() == "a9059cbb" and int.from_bytes(transfer_data(TO, 250_000)[-32:], "big") == 250_000
    assert Account.recover_transaction(a[0]) == s.address


def test_key_never_in_repr():
    s = Signer(KEY)
    assert "1111" not in repr(s) + str(s) and s.address in repr(s)


@pytest.mark.parametrize("cid", [1, 8453, 11155111])
def test_mainnet_and_other_chains_refused(cid):
    with pytest.raises(SettlementRefused):
        SettlementConfig(recipients={}, chain_id=cid)
