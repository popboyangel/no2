"""
核心监控逻辑：查询 pair 地址持有的 CGC / WGDC 数量，计算比例 = CGC / WGDC。
用 symbol() 做匹配，避免 token0/token1 顺序搞反（之前已确认链上顺序与预期相反）。
"""
from eth_client import EthClient


def fetch_amounts_and_ratio(cfg):
    client = EthClient(cfg["rpc_url"])
    pair = cfg["pair_address"]
    token_a = cfg["token_a"]
    token_b = cfg["token_b"]

    sym_a = (client.symbol(token_a) or "").upper()
    sym_b = (client.symbol(token_b) or "").upper()

    dec_a = client.decimals(token_a)
    dec_b = client.decimals(token_b)

    bal_a = client.balance_of(token_a, pair) / (10 ** dec_a)
    bal_b = client.balance_of(token_b, pair) / (10 ** dec_b)

    amounts = {}
    if sym_a == "CGC":
        amounts["CGC"] = bal_a
    elif sym_a == "WGDC":
        amounts["WGDC"] = bal_a

    if sym_b == "CGC":
        amounts["CGC"] = bal_b
    elif sym_b == "WGDC":
        amounts["WGDC"] = bal_b

    # 万一 symbol() 读取失败（个别RPC节点不稳定），退回到已知的固定映射
    if "CGC" not in amounts or "WGDC" not in amounts:
        amounts["WGDC"] = bal_a
        amounts["CGC"] = bal_b

    cgc = amounts["CGC"]
    wgdc = amounts["WGDC"]
    ratio = (cgc / wgdc) if wgdc else None
    return cgc, wgdc, ratio
