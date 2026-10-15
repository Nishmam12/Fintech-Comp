"""In-memory chain for tests: deterministic, with crash/outage injection. Not for production use."""
from __future__ import annotations

from eth_utils import keccak

from .chain import ChainError


class FakeChain:
    chain_id = 84532

    def __init__(self, base_fee: int = 10**9):
        self.mempool: dict[str, bytes] = {}     # hash -> raw
        self.mined: dict[str, dict] = {}        # hash -> receipt
        self.sent: list[str] = []               # every send_raw call (hashes), for exactly-once assertions
        self.used_nonces: set[int] = set()
        self.height, self.base_fee, self.down = 100, base_fee, False
        self.nonce_override: int | None = None  # simulate a nonce consumed by some other tx

    def send_raw(self, raw: bytes) -> None:
        if self.down:
            raise ChainError("send failed: ConnectError")
        self.sent.append("0x" + keccak(raw).hex())
        self.mempool["0x" + keccak(raw).hex()] = raw

    def mine(self, status: int = 1, blocks: int = 1) -> None:
        for h in list(self.mempool):
            self.mined[h] = {"status": status, "block": self.height + 1}
            del self.mempool[h]
        self.height += blocks

    def get_receipt(self, tx_hash: str) -> dict | None:
        if self.down:
            raise ChainError("eth_getTransactionReceipt failed: ConnectError")
        return self.mined.get(tx_hash)

    def nonce(self, address: str, block: str = "pending") -> int:
        return self.nonce_override if self.nonce_override is not None else 0

    def block_number(self) -> int:
        return self.height

    def fees(self) -> tuple[int, int]:
        return 2 * self.base_fee + 10**8, 10**8
