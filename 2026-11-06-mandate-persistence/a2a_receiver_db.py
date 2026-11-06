"""A2A接收方进程（持久化版）：nonce缓存/Mandate/revoke状态全部落盘SQLite。
用法:
  校验模式  python a2a_receiver_db.py <db> <registry.json> <token.json> [...]
  revoke   python a2a_receiver_db.py <db> --revoke <mid>
  执行模式  python a2a_receiver_db.py <db> --exec <mid> <tool> <path>
与2026-11-06-a2a-replay的内存版差异：进程重启后nonce/revoke/Mandate不丢失。"""
import sys, json, time, sqlite3, os
from a2a_common import (verify_token_sig, verify_mandate, attenuation_ok,
                        verify_crl, WINDOW, sign, mandate_payload)

def db_init(db):
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS nonces(nonce TEXT PRIMARY KEY, consumed_at REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS mandates(mid TEXT PRIMARY KEY, body TEXT, revoked INTEGER DEFAULT 0)")
    con.commit()
    return con

def save_mandate(con, m):
    con.execute("INSERT OR REPLACE INTO mandates(mid, body, revoked) VALUES(?,?,?)",
                (m["mandate_id"], json.dumps(m, ensure_ascii=False), 0))
    con.commit()

def check(con, tok, registry, crl):
    mid = tok["mandate"].get("mandate_id", "?")
    if crl is not None:
        if not verify_crl(crl):
            return f"DENIED {mid}: CRL_INVALID_SIG"
        if mid in crl["revoked_ids"] or tok["mandate"].get("parent_id") in crl["revoked_ids"]:
            return f"DENIED {mid}: REVOKED_BY_CRL"
    if not verify_token_sig(tok):
        return f"DENIED {mid}: INVALID_SIG"
    drift = int(time.time() - tok["ts"])
    if abs(drift) > WINDOW:
        return f"DENIED {mid}: EXPIRED (时间偏差{drift}s超出±{WINDOW}s窗口)"
    # nonce落盘：INSERT冲突即重放
    try:
        con.execute("INSERT INTO nonces(nonce, consumed_at) VALUES(?,?)", (tok["nonce"], time.time()))
    except sqlite3.IntegrityError:
        con.rollback()
        return f"DENIED {mid}: REPLAY (nonce已消费[落盘])"
    m = tok["mandate"]
    if not verify_mandate(m):
        con.rollback()
        return f"DENIED {mid}: MANDATE_SIG_INVALID"
    pid = m.get("parent_id")
    if pid:
        parent = registry.get(pid)
        if parent is None or parent["revoked"] or not verify_mandate(parent):
            con.rollback()
            return f"DENIED {mid}: PARENT_INVALID"
        ok, why = attenuation_ok(m, parent)
        if not ok:
            con.rollback()
            return f"DENIED {mid}: ESCALATION ({why})"
    con.commit()
    save_mandate(con, m)  # 校验通过的Mandate落盘，供重启后执行校验
    return f"ALLOW {mid}: 验签+时间窗+nonce[落盘]+attenuation全部通过"

def main():
    db = sys.argv[1]
    con = db_init(db)
    # revoke子命令
    if sys.argv[2] == "--revoke":
        mid = sys.argv[3]
        cur = con.execute("UPDATE mandates SET revoked=1 WHERE mid=?", (mid,))
        con.commit()
        print(f"REVOKED {mid}: 影响行数={cur.rowcount} (已落盘)")
        return
    # exec子命令：从落盘库加载Mandate做执行前校验
    if sys.argv[2] == "--exec":
        mid, tool, path = sys.argv[3], sys.argv[4], sys.argv[5]
        row = con.execute("SELECT body, revoked FROM mandates WHERE mid=?", (mid,)).fetchone()
        if row is None:
            print(f"denied: {mid} not found in db"); return
        m, revoked = json.loads(row[0]), row[1]
        if revoked:
            print(f"denied: {mid} revoked[落盘]"); return
        if not verify_mandate(m):
            print(f"denied: {mid} signature invalid after reload"); return
        if tool not in m["allowed_tools"]:
            print(f"denied: tool '{tool}' not in {sorted(m['allowed_tools'])}"); return
        if path not in m["allowed_paths"]:
            print(f"denied: path '{path}' outside scope"); return
        print(f"ALLOW: {mid} 重启后从落盘库重新加载，验签有效，执行 {tool}({path})")
        return
    # 校验模式
    registry_file, token_files = sys.argv[2], sys.argv[3:]
    crl = None
    if "--crl" in sys.argv:
        crl = json.load(open(sys.argv[sys.argv.index("--crl") + 1], encoding="utf-8"))
        token_files = [t for t in token_files if not t.endswith("crl_real.json")]
    registry = {m["mandate_id"]: m for m in json.load(open(registry_file, encoding="utf-8"))}
    for tf in token_files:
        tok = json.load(open(tf, encoding="utf-8"))
        print(check(con, tok, registry, crl))

if __name__ == "__main__":
    main()
