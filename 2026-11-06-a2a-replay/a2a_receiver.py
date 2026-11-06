"""A2A接收方进程：独立进程校验跨进程传输来的Mandate token。
用法: python a2a_receiver.py <registry.json> <token.json> [token2.json ...] [--naive] [--crl crl.json]
判定顺序: CRL -> token签名 -> 时间窗口 -> nonce重放 -> mandate验签+父链+attenuation
--naive: 对照组，只验token签名，不查时间窗/nonce/attenuation
注意: nonce缓存只在进程内存——进程退出即丢失（本篇关键实测点）"""
import sys, json, time, os
from a2a_common import verify_token_sig, verify_mandate, attenuation_ok, verify_crl, WINDOW

NONCE_CACHE = set()  # 进程内存nonce缓存

def check(tok, registry, crl, naive):
    mid = tok["mandate"].get("mandate_id", "?")
    # 1. 全局吊销列表（签名校验，伪造的CRL直接拒收且拒绝采信）
    if crl is not None:
        if not verify_crl(crl):
            return f"DENIED {mid}: CRL_INVALID_SIG (吊销列表签名伪造，拒绝采信)"
        if mid in crl["revoked_ids"] or tok["mandate"].get("parent_id") in crl["revoked_ids"]:
            return f"DENIED {mid}: REVOKED_BY_CRL (全局吊销列表生效)"
    # 2. 传输层签名
    if not verify_token_sig(tok):
        return f"DENIED {mid}: INVALID_SIG (传输层签名不符)"
    if naive:
        return f"ALLOW {mid}: naive接收方放行（不查时间窗/nonce/attenuation）"
    # 3. 时间窗口
    drift = int(time.time() - tok["ts"])
    if abs(drift) > WINDOW:
        return f"DENIED {mid}: EXPIRED (时间偏差{drift}s超出±{WINDOW}s窗口)"
    # 4. nonce防重放
    if tok["nonce"] in NONCE_CACHE:
        return f"DENIED {mid}: REPLAY (nonce已消费)"
    # 5. mandate验签 + 父链 + attenuation
    m = tok["mandate"]
    if not verify_mandate(m):
        return f"DENIED {mid}: MANDATE_SIG_INVALID"
    pid = m.get("parent_id")
    if pid:
        parent = registry.get(pid)
        if parent is None or parent["revoked"] or not verify_mandate(parent):
            return f"DENIED {mid}: PARENT_INVALID (父Mandate不存在/已吊销/被篡改)"
        ok, why = attenuation_ok(m, parent)
        if not ok:
            return f"DENIED {mid}: ESCALATION ({why})"
    NONCE_CACHE.add(tok["nonce"])
    return f"ALLOW {mid}: 验签+时间窗+nonce+attenuation全部通过 (nonce已消费)"

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    naive = "--naive" in sys.argv
    crl = None
    if "--crl" in sys.argv:
        crl = json.load(open(sys.argv[sys.argv.index("--crl") + 1], encoding="utf-8"))
    registry_file, token_files = args[0], args[1:]
    registry = {m["mandate_id"]: m for m in json.load(open(registry_file, encoding="utf-8"))}
    for tf in token_files:
        tok = json.load(open(tf, encoding="utf-8"))
        print(check(tok, registry, crl, naive))

if __name__ == "__main__":
    main()
