import time
from typing import Any

import requests


class RpcClient:
    def __init__(self, rpc_url: str, timeout: int = 45, retries: int = 6) -> None:
        self.rpc_url = rpc_url
        self.timeout = timeout
        self.retries = retries
        self._request_id = 1

    def call(self, method: str, params: list[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        self._request_id += 1
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = requests.post(self.rpc_url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                body = response.json()
                if "error" in body:
                    raise RuntimeError(body["error"])
                return body["result"]
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"RPC call failed: {method}: {last_error}")

    def get_logs(
        self,
        address: str | list[str] | None,
        topics: list[str | list[str] | None],
        from_block: int,
        to_block: int,
    ) -> list[dict[str, Any]]:
        params = [{
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "topics": topics,
        }]
        if address:
            params[0]["address"] = address
        return self.call("eth_getLogs", params)

    def get_block_by_number(self, block_number: int) -> dict[str, Any]:
        return self.call("eth_getBlockByNumber", [hex(block_number), False])
