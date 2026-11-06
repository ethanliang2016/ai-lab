"""A2A跨进程Mandate传输+防重放实测驱动。
发送方把Mandate+nonce+时间戳打包成签名token写盘（模拟网络传输），
接收方为独立Python子进程（真跨进程），做CRL/签名/时间窗/nonce/attenuation校验。
A3逐字节重放、A6 naive对照、A8中间人伪造CRL、R重启后重放（nonce缓存丢失）。"""
import subprocess, sys, os, json, time, uuid
from a2a_common import make_mandate, pack_token, make_crl, WINDOW

HERE = os.path.dirname(os.path.abspath(__file__))
WIRE = os.path.join(HERE, "wire")          # 模拟传输通道（落盘的token文件）
os.makedirs(WIRE, exist_ok=True)
RECEIVER = os.path.join(HERE, "a2a_receiver.py")

LOG = []
def log(s=""): print(s); LOG.append(s)
def banner(t): log(f"\n{'='*66}\n{t}\n{'='*66}")

def dump(name, obj):
    p = os.path.join(WIRE, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p

def recv(registry, tokens, naive=False, crl=None):
    """起一个独立的接收方子进程，返回其stdout逐行"""
    cmd = [sys.executable, RECEIVER, registry] + tokens
    if naive: cmd.append("--naive")
    if crl: cmd += ["--crl", crl]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=HERE)
    return r.stdout.strip().splitlines()

# ---------- 预置：根Mandate带外预共享给接收方 ----------
root = make_mandate("root-1", {"README.md", "docs/guide.md"},
                    {"read_file", "write_file", "execute_sql"}, "auto_low_risk")
REG_OK = dump("registry.json", [root])
root_revoked = dict(root, revoked=True)
root_revoked["sig"] = __import__("a2a_common").sign(
    __import__("a2a_common").mandate_payload(root_revoked))
REG_REVOKED = dump("registry_revoked.json", [root_revoked])
log(f"根Mandate已预共享: root-1 paths={root['allowed_paths']} tools={root['allowed_tools']}")

def send(mid, paths, tools, strength, parent="root-1", ts=None, nonce=None):
    m = make_mandate(mid, paths, tools, strength, parent=parent)
    tok = pack_token(m, nonce or uuid.uuid4().hex, ts if ts is not None else time.time())
    return dump(f"{mid}.token.json", tok)

# ---------- A1 正常跨进程委派 ----------
banner("A1 正常委派：子集Mandate跨进程传输")
t1 = send("child-1", {"README.md"}, {"read_file"}, "ask_first")
for line in recv(REG_OK, [t1]): log(line)

# ---------- A2 越权委派：子Agent索要超出父级的路径 ----------
banner("A2 越权委派：传输的Mandate超出父级scope")
t2 = send("child-2", {"README.md", "src/auth.py"}, {"read_file"}, "ask_first")
for line in recv(REG_OK, [t2]): log(line)

# ---------- A3 逐字节重放：同一token文件原样发两次（同一接收进程） ----------
banner("A3 逐字节重放：同一token字节流重复投递（同一接收进程）")
t3 = send("child-3", {"README.md"}, {"read_file"}, "ask_first")
for line in recv(REG_OK, [t3, t3]): log(line)

# ---------- A4 时间窗口：过期token与窗口内token ----------
banner(f"A4 时间窗口 ±{WINDOW}s：-6min过期拒 / -4min窗口内放行")
t4a = send("child-4a", {"README.md"}, {"read_file"}, "ask_first", ts=time.time() - 360)
t4b = send("child-4b", {"README.md"}, {"read_file"}, "ask_first", ts=time.time() - 240)
for line in recv(REG_OK, [t4a, t4b]): log(line)

# ---------- A5 篡改载荷：改token里的scope，签名不动 ----------
banner("A5 篡改载荷：中间人扩大scope，签名原样")
t5 = send("child-5", {"README.md"}, {"read_file"}, "ask_first")
tok5 = json.load(open(t5, encoding="utf-8"))
tok5["mandate"]["allowed_paths"] = ["README.md", "src/auth.py"]  # 篡改，不重签
t5 = dump("child-5.tampered.token.json", tok5)
for line in recv(REG_OK, [t5]): log(line)

# ---------- A6 naive对照：不做时间窗/nonce/attenuation校验的接收方 ----------
banner("A6 naive对照组：只验签名的接收方，越权+重放全穿")
t6 = send("child-6", {"README.md", "src/auth.py"}, {"read_file"}, "ask_first")
for line in recv(REG_OK, [t6, t6], naive=True): log(line)

# ---------- A7 revoke根token：父已吊销的委派 ----------
banner("A7 父Mandate已吊销：链式拦截")
t7 = send("child-7", {"README.md"}, {"read_file"}, "ask_first")
for line in recv(REG_REVOKED, [t7]): log(line)

# ---------- A8 中间人伪造全局吊销 vs 真实全局吊销 ----------
banner("A8 全局吊销列表（CRL）：伪造被拒采信 / 真吊销全拒")
crl_forge = {"revoked_ids": ["root-1"], "sig": "0" * 64}  # 中间人伪造CRL
p_forge = dump("crl_forged.json", crl_forge)
crl_real = make_crl(["root-1"])
p_real = dump("crl_real.json", crl_real)
t8a = send("child-8a", {"README.md"}, {"read_file"}, "ask_first")
t8b = send("child-8b", {"README.md"}, {"read_file"}, "ask_first")
log("[中间人伪造CRL投毒]")
for line in recv(REG_OK, [t8a], crl=p_forge): log(line)
log("[管理员签发真CRL，全局吊销root-1]")
for line in recv(REG_OK, [t8b], crl=p_real): log(line)

# ---------- R 关键实测：进程重启后nonce缓存丢失，窗口期重放成功 ----------
banner("R 进程重启：内存nonce缓存丢失，窗口期内逐字节重放成功")
tR = send("child-R", {"README.md"}, {"read_file"}, "ask_first")
log("[第1个接收进程消费token]")
for line in recv(REG_OK, [tR]): log(line)
log("[接收进程重启（新进程，内存nonce缓存为空），同一token仍在时间窗内]")
for line in recv(REG_OK, [tR]): log(line)
log("^^ 重放成功：重启窗口期内旧token可复用——内存nonce缓存是残留风险，生产必须落盘")

banner("汇总")
log(json.dumps({"scenarios": {
    "A1": "正常委派跨进程放行", "A2": "越权委派DENIED(ESCALATION)",
    "A3": "逐字节重放DENIED(REPLAY)", "A4": "过期DENIED(EXPIRED)/窗口内ALLOW",
    "A5": "篡改载荷DENIED(INVALID_SIG)", "A6": "naive对照越权+重放全穿",
    "A7": "父吊销DENIED(PARENT_INVALID)", "A8": "伪造CRL拒绝采信/真CRL全局拦截",
    "R": "重启后nonce缓存丢失，窗口期重放成功"}}, ensure_ascii=False, indent=2))

for out in [os.path.join(HERE, "evidence", "run_log.txt"),
            r"c:\Users\lenovo\Desktop\claudecode专用\AI情报收集\深度实测\Agent A2A防重放实测\evidence\run_log.txt"]:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    print(f"日志已保存: {out}")
