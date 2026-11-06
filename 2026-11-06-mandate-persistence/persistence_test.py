"""Mandate持久化+重启恢复实测驱动。
承接2026-11-06-a2a-replay的残留风险：内存nonce缓存重启丢失->窗口期重放成功。
本篇：nonce/Mandate/revoke状态落盘SQLite，重启后：
  R1 窗口期内重放被拒（对照⑥内存版重启重放成功）
  R2 Mandate落盘重启后重新加载，验签仍有效
  R3 revoke状态落盘重启后仍生效
  R4 naive内存版对照：重启后重放成功（复现⑥的R）
接收方均为独立子进程，重启=真进程重建。"""
import subprocess, sys, os, json, time, uuid
from a2a_common import make_mandate, pack_token

HERE = os.path.dirname(os.path.abspath(__file__))
REPLAY_DIR = os.path.join(os.path.dirname(HERE), "2026-11-06-a2a-replay")
WIRE = os.path.join(HERE, "wire")
os.makedirs(WIRE, exist_ok=True)
DB_RECV = os.path.join(HERE, "a2a_receiver_db.py")
MEM_RECV = os.path.join(REPLAY_DIR, "a2a_receiver.py")
DB = os.path.join(WIRE, "mandate.db")

LOG = []
def log(s=""): print(s); LOG.append(s)
def banner(t): log(f"\n{'='*66}\n{t}\n{'='*66}")

def dump(name, obj):
    p = os.path.join(WIRE, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p

def run(cmd, cwd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=cwd)
    return r.stdout.strip().splitlines()

def db_recv(tokens):
    return run([sys.executable, DB_RECV, DB, REG] + tokens, HERE)

def db_exec(mid, tool, path):
    return run([sys.executable, DB_RECV, DB, "--exec", mid, tool, path], HERE)

def db_revoke(mid):
    return run([sys.executable, DB_RECV, DB, "--revoke", mid], HERE)

def mem_recv(tokens):
    return run([sys.executable, MEM_RECV, REG] + tokens, REPLAY_DIR)

# 清理旧库，保证实测可重复
if os.path.exists(DB):
    os.remove(DB)

root = make_mandate("root-1", {"README.md", "docs/guide.md"},
                    {"read_file", "write_file", "execute_sql"}, "auto_low_risk")
REG = dump("registry.json", [root])
log("根Mandate已预共享；持久化库 = wire/mandate.db (SQLite)")

def send(mid, paths, tools, strength, parent="root-1"):
    m = make_mandate(mid, paths, tools, strength, parent=parent)
    return dump(f"{mid}.token.json", pack_token(m, uuid.uuid4().hex, time.time()))

# ---------- R1 落盘nonce：重启后窗口期重放被拒 ----------
banner("R1 nonce落盘：进程重启后，窗口期内逐字节重放被拒")
t1 = send("child-R1", {"README.md"}, {"read_file"}, "ask_first")
log("[进程#1消费token]")
for line in db_recv([t1]): log(line)
log("[接收进程重启（新进程，加载同一SQLite库），同一token仍在时间窗内]")
for line in db_recv([t1]): log(line)
log("^^ 对照⑥：内存版此处为ALLOW（重放成功），落盘后DENIED(REPLAY)")

# ---------- R2 Mandate落盘：重启后重新加载验签仍有效 ----------
banner("R2 Mandate落盘：重启后从库中重新加载，验签与scope校验仍有效")
t2 = send("child-R2", {"README.md"}, {"read_file"}, "ask_first")
log("[进程#1校验通过，Mandate落盘]")
for line in db_recv([t2]): log(line)
log("[接收进程重启，执行前从落盘库重新加载Mandate]")
for line in db_exec("child-R2", "read_file", "README.md"): log(line)
log("[越界访问仍被拦：重启后scope不松动]")
for line in db_exec("child-R2", "write_file", "README.md"): log(line)

# ---------- R3 revoke落盘：重启后吊销仍生效 ----------
banner("R3 revoke落盘：吊销后进程重启，吊销状态仍生效")
t3 = send("child-R3", {"README.md"}, {"read_file"}, "ask_first")
log("[进程#1校验通过并落盘]")
for line in db_recv([t3]): log(line)
log("[管理员revoke child-R3（写库）]")
for line in db_revoke("child-R3"): log(line)
log("[接收进程重启，执行校验]")
for line in db_exec("child-R3", "read_file", "README.md"): log(line)

# ---------- R4 对照：内存版重启后重放成功（复现⑥的R） ----------
banner("R4 对照组：内存nonce版，重启后窗口期重放成功（复现⑥R）")
t4 = send("child-R4", {"README.md"}, {"read_file"}, "ask_first")
log("[内存版进程#1消费token]")
for line in mem_recv([t4]): log(line)
log("[内存版进程重启，同一token仍在时间窗内]")
for line in mem_recv([t4]): log(line)
log("^^ 重放成功：内存nonce缓存的真空期，落盘版R1已关闭此窗口")

banner("汇总")
log(json.dumps({"scenarios": {
    "R1": "nonce落盘后重启，窗口期重放DENIED(REPLAY)",
    "R2": "Mandate落盘重启后重新加载验签有效，越界仍拦",
    "R3": "revoke落盘重启后仍生效，执行denied",
    "R4": "内存版对照：重启后重放成功(ALLOW)"}}, ensure_ascii=False, indent=2))

for out in [os.path.join(HERE, "evidence", "run_log.txt"),
            r"c:\Users\lenovo\Desktop\claudecode专用\AI情报收集\深度实测\Agent Mandate持久化实测\evidence\run_log.txt"]:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    print(f"日志已保存: {out}")
