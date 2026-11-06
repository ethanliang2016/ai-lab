"""A2A跨进程Mandate传输公共组件：Mandate序列化/签名、传输token打包与校验"""
import hmac, hashlib, json, time, os

SECRET = os.environ.get("MANDATE_HMAC_KEY", "a2a-test-key").encode()
WINDOW = 300  # 传输token有效期窗口 ±300s

STRENGTH_ORDER = {"ask_first": 0, "auto_low_risk": 1}

def sign(payload: str) -> str:
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()

def mandate_payload(m: dict) -> str:
    return (f"{m['mandate_id']}|{m['actor']}|{sorted(m['allowed_paths'])}|"
            f"{sorted(m['allowed_tools'])}|{m['strength']}|{m['rule_version']}|"
            f"{m['issued_at']}|{m['parent_id']}|{m['revoked']}")

def make_mandate(mid, paths, tools, strength, parent=None, revoked=False, issued_at=None):
    m = {"mandate_id": mid, "actor": "router", "allowed_paths": sorted(paths),
         "allowed_tools": sorted(tools), "strength": strength, "rule_version": "v1.0",
         "issued_at": issued_at if issued_at is not None else time.time(),
         "parent_id": parent, "revoked": revoked}
    m["sig"] = sign(mandate_payload(m))
    return m

def verify_mandate(m) -> bool:
    return hmac.compare_digest(m.get("sig", ""), sign(mandate_payload(m)))

def pack_token(mandate: dict, nonce: str, ts: float) -> dict:
    """传输token = mandate + nonce + 时间戳，整体再签一层（防传输篡改）"""
    tok = {"mandate": mandate, "nonce": nonce, "ts": ts}
    tok["sig"] = sign(json.dumps({"mandate": mandate, "nonce": nonce, "ts": ts}, sort_keys=True))
    return tok

def verify_token_sig(tok) -> bool:
    expect = sign(json.dumps({"mandate": tok["mandate"], "nonce": tok["nonce"], "ts": tok["ts"]}, sort_keys=True))
    return hmac.compare_digest(tok.get("sig", ""), expect)

def attenuation_ok(child, parent):
    """收敛性校验：子的scope/tools/strength不得超出父"""
    if not set(child["allowed_paths"]) <= set(parent["allowed_paths"]):
        extra = sorted(set(child["allowed_paths"]) - set(parent["allowed_paths"]))
        return False, f"paths escalation {extra} not in parent"
    if not set(child["allowed_tools"]) <= set(parent["allowed_tools"]):
        extra = sorted(set(child["allowed_tools"]) - set(parent["allowed_tools"]))
        return False, f"tools escalation {extra} not in parent"
    if STRENGTH_ORDER[child["strength"]] > STRENGTH_ORDER[parent["strength"]]:
        return False, f"strength escalation {parent['strength']} -> {child['strength']}"
    return True, ""

def make_crl(revoked_ids) -> dict:
    """全局吊销列表（CRL）：本身带签名，中间人无法伪造"""
    crl = {"revoked_ids": sorted(revoked_ids)}
    crl["sig"] = sign("|".join(crl["revoked_ids"]))
    return crl

def verify_crl(crl) -> bool:
    return hmac.compare_digest(crl.get("sig", ""), sign("|".join(sorted(crl["revoked_ids"]))))
