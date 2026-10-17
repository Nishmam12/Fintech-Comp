"""Local signing of an ERC-20 transfer. The key is held in a wrapper that never reveals it in repr/str."""
from __future__ import annotations

from eth_account import Account
from eth_utils import keccak, to_checksum_address

ANCHOR_GAS_LIMIT = 30_000  # 21000 base + 41 calldata bytes x 16 = 21656 worst case; fixed so signing needs no network
GAS_LIMIT = 100_000  # ERC-20 transfer is ~65k worst case; fixed so signing needs no network
_TRANSFER_SELECTOR = bytes.fromhex("a9059cbb")


def transfer_data(to: str, amount: int) -> bytes:
    return _TRANSFER_SELECTOR + bytes.fromhex(to_checksum_address(to)[2:]).rjust(32, b"\0") + amount.to_bytes(32, "big")


class Signer:
    def __init__(self, private_key: str):
        self._acct = Account.from_key(private_key)

    @property
    def address(self) -> str:
        return self._acct.address

    def __repr__(self) -> str:
        return f"Signer({self.address})"

    __str__ = __repr__

    def sign_transfer(self, *, chain_id: int, nonce: int, token: str, to: str, amount: int,
                      max_fee: int, priority_fee: int) -> tuple[bytes, str]:
        """Returns (raw_tx, tx_hash). Pure and offline."""
        signed = self._acct.sign_transaction({
            "type": 2, "chainId": chain_id, "nonce": nonce, "to": to_checksum_address(token), "value": 0,
            "gas": GAS_LIMIT, "maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority_fee,
            "data": transfer_data(to, amount),
        })
        raw = bytes(signed.raw_transaction)
        return raw, "0x" + keccak(raw).hex()

    def sign_anchor(self, *, chain_id: int, nonce: int, data: bytes, max_fee: int, priority_fee: int) -> tuple[bytes, str]:
        """0-value self-transfer carrying `data` (BK-401). Pure and offline."""
        signed = self._acct.sign_transaction({
            "type": 2, "chainId": chain_id, "nonce": nonce, "to": self.address, "value": 0,
            "gas": ANCHOR_GAS_LIMIT, "maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority_fee, "data": data,
        })
        raw = bytes(signed.raw_transaction)
        return raw, "0x" + keccak(raw).hex()
