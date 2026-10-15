"""Chain access: a small interface, a JSON-RPC client over httpx, and an in-memory fake for tests."""
from __future__ import annotations

import httpx

_BENIGN = ("already known", "known transaction", "nonce too low", "already imported")


class ChainError(Exception):
    """Transport / RPC failure. Message is sanitized by construction (never contains request bodies)."""


class RpcChain:
    def __init__(self, url: str, chain_id: int, timeout: float = 15.0):
        self.url, self.chain_id, self._http = url, chain_id, httpx.Client(timeout=timeout)

    def _call(self, method: str, params: list):
        try:
            r = self._http.post(self.url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
            r.raise_for_status()
            body = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ChainError(f"{method} failed: {type(e).__name__}") from None
        if "error" in body:
            raise ChainError(f"{method}: {str(body['error'].get('message', 'rpc error'))[:200]}")
        return body["result"]

    def send_raw(self, raw: bytes) -> None:
        try:
            self._call("eth_sendRawTransaction", ["0x" + raw.hex()])
        except ChainError as e:
            if not any(m in str(e).lower() for m in _BENIGN):
                raise

    def get_receipt(self, tx_hash: str) -> dict | None:
        r = self._call("eth_getTransactionReceipt", [tx_hash])
        return None if r is None else {"status": int(r["status"], 16), "block": int(r["blockNumber"], 16)}

    def nonce(self, address: str, block: str = "pending") -> int:
        return int(self._call("eth_getTransactionCount", [address, block]), 16)

    def block_number(self) -> int:
        return int(self._call("eth_blockNumber", []), 16)

    def fees(self) -> tuple[int, int]:
        """(max_fee_per_gas, priority_fee) with 2x headroom on the base fee."""
        prio = int(self._call("eth_maxPriorityFeePerGas", []), 16)
        base = int(self._call("eth_getBlockByNumber", ["latest", False])["baseFeePerGas"], 16)
        return 2 * base + prio, prio
