"""
轻量以太坊 JSON-RPC 客户端，只依赖 requests，不依赖 web3.py。
用于查询 GoodChain 上代币的 balanceOf / decimals / symbol。
"""
import requests


class EthClient:
    def __init__(self, rpc_url, timeout=15):
        self.rpc_url = rpc_url
        self.timeout = timeout
        self._id = 0

    def _rpc(self, method, params):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        resp = requests.post(self.rpc_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data["result"]

    def eth_call(self, to, data):
        return self._rpc("eth_call", [{"to": to, "data": data}, "latest"])

    @staticmethod
    def _pad_address(addr):
        return addr.lower().replace("0x", "").rjust(64, "0")

    def balance_of(self, token_address, holder_address):
        """返回代币原始最小单位数量（未除以decimals）"""
        selector = "70a08231"  # balanceOf(address)
        data = "0x" + selector + self._pad_address(holder_address)
        result = self.eth_call(token_address, data)
        return int(result, 16)

    def decimals(self, token_address, default=18):
        selector = "313ce567"  # decimals()
        try:
            result = self.eth_call(token_address, "0x" + selector)
            return int(result, 16)
        except Exception:
            return default

    def symbol(self, token_address):
        selector = "95d89b41"  # symbol()
        try:
            result = self.eth_call(token_address, "0x" + selector)
            hexstr = result[2:]
            if len(hexstr) <= 64:
                # 有些老合约把symbol编码成bytes32而非动态string
                raw = bytes.fromhex(hexstr)
                return raw.split(b"\x00")[0].decode("utf-8", errors="ignore").strip()
            length = int(hexstr[64:128], 16)
            strhex = hexstr[128:128 + length * 2]
            return bytes.fromhex(strhex).decode("utf-8", errors="ignore").strip("\x00")
        except Exception:
            return None
