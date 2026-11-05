"""多Agent Mandate委派实测：转授权限只能缩不能放（attenuation）+ 级联收回"""
import hmac, hashlib, os, time, json
from dataclasses import dataclass
from typing import Optional

os.environ.setdefault("MANDATE_HMAC_KEY", "delegation-test-key")
_SECRET = os.environ["MANDATE_HMAC_KEY"].encode()

def _sign(payload: str) -> str:
    return hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()

# strength 的偏序：auto_low_risk > ask_first（转授只能降不能升）
STRENGTH_ORDER = {"ask_first": 0, "auto_low_risk": 1}

@dataclass(frozen=True)
class Mandate:
    mandate_id: str
    actor: str
    allowed_paths: frozenset
    allowed_tools: frozenset      # 本Mandate允许的工具集合
    strength: str
    rule_version: str
    issued_at: float
    parent_id: Optional[str] = None   # 委派链：父Mandate ID，根授权为None
    revoked: bool = False
    sig: str = ""

    def __post_init__(self):
        if not self.sig:
            object.__setattr__(self, "sig", _sign(self._payload()))

    def _payload(self) -> str:
        return (f"{self.mandate_id}|{self.actor}|{sorted(self.allowed_paths)}|"
                f"{sorted(self.allowed_tools)}|{self.strength}|{self.rule_version}|"
                f"{self.issued_at}|{self.parent_id}|{self.revoked}")

    def verify(self) -> bool:
        return hmac.compare_digest(self.sig, _sign(self._payload()))

class MandateStore:
    def __init__(self):
        self._store: dict[str, Mandate] = {}

    def issue_root(self, m: Mandate) -> None:
        if not m.verify():
            raise ValueError("signature invalid")
        self._store[m.mandate_id] = m

    def delegate(self, parent_id: str, child: Mandate, check_attenuation: bool = True) -> str:
        """委派：以parent为基础签发子Mandate。
        check_attenuation=False 即naive对照组：不校验子集关系，直接签发。"""
        parent = self._store.get(parent_id)
        if parent is None or parent.revoked or not parent.verify():
            return "REJECTED: parent mandate invalid"
        if not child.verify():
            return "REJECTED: child signature invalid"
        if check_attenuation:
            # 收敛性校验：子在每个维度都不得超出父
            if not child.allowed_paths <= parent.allowed_paths:
                extra = child.allowed_paths - parent.allowed_paths
                return f"REJECTED: paths escalation {sorted(extra)} not in parent"
            if not child.allowed_tools <= parent.allowed_tools:
                extra = child.allowed_tools - parent.allowed_tools
                return f"REJECTED: tools escalation {sorted(extra)} not in parent"
            if STRENGTH_ORDER[child.strength] > STRENGTH_ORDER[parent.strength]:
                return f"REJECTED: strength escalation {parent.strength} -> {child.strength}"
        self._store[child.mandate_id] = child
        return f"ISSUED: {child.mandate_id} (parent={parent_id})"

    def revoke(self, mandate_id: str) -> list[str]:
        """收回并级联：父revoke后所有子孙一并revoke。"""
        cascaded = []
        def _revoke(mid):
            old = self._store.get(mid)
            if old is None or old.revoked:
                return
            self._store[mid] = Mandate(
                mandate_id=old.mandate_id, actor=old.actor,
                allowed_paths=old.allowed_paths, allowed_tools=old.allowed_tools,
                strength=old.strength, rule_version=old.rule_version,
                issued_at=old.issued_at, parent_id=old.parent_id, revoked=True)
            cascaded.append(mid)
            for k, v in list(self._store.items()):
                if v.parent_id == mid:
                    _revoke(k)
        _revoke(mandate_id)
        return cascaded

    def effective_check(self, mandate_id: str, tool: str, path: str = None) -> tuple[str, str]:
        """执行前校验：本Mandate有效 + 整链祖先全部有效。"""
        m = self._store.get(mandate_id)
        if m is None:
            return "denied", "mandate not found"
        # 沿parent链向上，每一环都必须有效（验签+未revoke）
        chain = []
        cur = m
        while cur is not None:
            chain.append(cur.mandate_id)
            if cur.revoked:
                return "denied", f"chain broken: {cur.mandate_id} revoked"
            if not cur.verify():
                return "denied", f"chain broken: {cur.mandate_id} tampered"
            cur = self._store.get(cur.parent_id) if cur.parent_id else None
        if tool not in m.allowed_tools:
            return "denied", f"tool '{tool}' not in mandate tools {sorted(m.allowed_tools)}"
        if path is not None and path not in m.allowed_paths:
            return "denied", f"path '{path}' outside scope {sorted(m.allowed_paths)}"
        return "allow", f"chain {' -> '.join(reversed(chain))} valid"

# ========== 实测场景 ==========
LOG = []
def log(s=""): print(s); LOG.append(s)
def banner(t): log(f"\n{'='*62}\n{t}\n{'='*62}")

def mk(mid, paths, tools, strength, parent=None):
    return Mandate(mandate_id=mid, actor="router", allowed_paths=frozenset(paths),
                   allowed_tools=frozenset(tools), strength=strength,
                   rule_version="v1.0", issued_at=time.time(), parent_id=parent)

banner("初始授权：根Mandate（主Agent）")
store = MandateStore()
root = mk("root-1", {"README.md", "docs/guide.md"}, {"read_file", "write_file", "execute_sql"}, "auto_low_risk")
store.issue_root(root)
log(f"root-1: paths={sorted(root.allowed_paths)} tools={sorted(root.allowed_tools)} strength={root.strength}")

banner("D1 正常委派：转授子集给子Agent（只读README）")
child = mk("child-1", {"README.md"}, {"read_file"}, "ask_first", parent="root-1")
log(store.delegate("root-1", child))
log(f"子Agent执行 read_file(README.md): {store.effective_check('child-1', 'read_file', 'README.md')}")

banner("D2 越权委派：子Agent索要超出父级的路径（src/auth.py）")
evil_child = mk("child-2", {"README.md", "src/auth.py"}, {"read_file", "write_file"}, "auto_low_risk", parent="root-1")
log(store.delegate("root-1", evil_child))

banner("D2b 对照组：naive委派（不校验子集关系）")
naive_store = MandateStore()
naive_store.issue_root(root)
log(naive_store.delegate("root-1", evil_child, check_attenuation=False))
log(f"naive链上写src/auth.py: {naive_store.effective_check('child-2', 'write_file', 'src/auth.py')}  <-- 越权成功")

banner("D3 链上二级越权：孙Agent经child-1索要execute_sql（root有但child-1没有）")
grandchild = mk("grand-1", {"README.md"}, {"read_file", "execute_sql"}, "auto_low_risk", parent="child-1")
log(store.delegate("child-1", grandchild))
log("关键：孙的权限以上一级child-1为基准，不是以root为基准——链上每环各自收口")

banner("D4 篡改链上的父Mandate（object.__setattr__扩大child-1权限）")
m = store._store["child-1"]
object.__setattr__(m, "allowed_tools", frozenset({"read_file", "execute_sql"}))
log(f"篡改后 child-1.verify() = {m.verify()}")
log(f"子Agent再执行 read_file: {store.effective_check('child-1', 'read_file', 'README.md')}")
log("父环被篡改 -> 整链不可用，不是'子Agent获得扩大权限'")

banner("D5 级联收回：revoke根Mandate，子孙全部失效")
store2 = MandateStore()
root2 = mk("root-2", {"README.md", "docs/guide.md"}, {"read_file", "write_file"}, "auto_low_risk")
store2.issue_root(root2)
c2 = mk("child-3", {"README.md"}, {"read_file"}, "ask_first", parent="root-2")
store2.delegate("root-2", c2)
g2 = mk("grand-2", {"README.md"}, {"read_file"}, "ask_first", parent="child-3")
store2.delegate("child-3", g2)
log(f"revoke前三代链有效: {store2.effective_check('grand-2', 'read_file', 'README.md')}")
cascaded = store2.revoke("root-2")
log(f"revoke root-2，级联收回: {cascaded}")
log(f"revoke后孙Agent执行: {store2.effective_check('grand-2', 'read_file', 'README.md')}")

banner("汇总")
log(json.dumps({"scenarios": ["D1正常委派", "D2越权委派被拒", "D2b-naive对照越权成功",
                              "D3链上二级越权被拒", "D4篡改父环整链失效", "D5级联收回"]}, ensure_ascii=False))

out = r"c:\Users\lenovo\Desktop\claudecode专用\AI情报收集\深度实测\Agent委派授权实测\evidence\run_log.txt"
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(LOG))
print(f"\n日志已保存: {out}")
