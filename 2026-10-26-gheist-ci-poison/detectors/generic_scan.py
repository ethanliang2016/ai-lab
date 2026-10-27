#!/usr/bin/env python3
"""M5: 通用 workflow 静态规则扫描器
不依赖 Gheist IoC，只问一个问题：这个 workflow 是否在把 secrets 弄出 GitHub 的信任边界？
文本 + 轻结构混合分析（避免 PyYAML 把 on: 解析成 True 的坑）。

规则：
R1  run 块内出现 toJSON(secrets) 或 ${{ secrets.* }} 展开进 shell
R2  run 块内同时出现编码命令(base32/base64/xxd/od) 与 env/printenv/secrets
R3  run 块内出现外联原语(curl/wget/nc/ncat/Invoke-WebRequest)
R4  environment 字段取自 matrix（环境级密钥批量展开）
R5  uses: 引用非知名 org 或 actions/* 下的陌生名字（typosquat）
R6  pull_request_target 触发 + 检出 PR head + env 注入 secrets
R7  env/secrets 落盘 + 同 job 内 upload-artifact
R8  run 块内出现长 base64 团块(>=40字符，疑似藏地址)
"""
import json
import re
import sys
from pathlib import Path

ENCODING_CMDS = re.compile(r"\b(base32|base64|xxd|od\s|openssl\s+enc)\b")
EXFIL_CMDS = re.compile(r"\b(curl|wget|nc|ncat|Invoke-WebRequest|Invoke-RestMethod)\b")
SECRETS_REF = re.compile(r"toJSON\(secrets\)|\$\{\{\s*secrets\.")
ENV_DUMP = re.compile(r"\b(env|printenv|set)\b")
LONG_B64 = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")

KNOWN_ORGS = {
    "actions", "github", "docker", "azure", "aws-actions",
    "google-github-actions", "pypa", "codecov", "mozilla",
    "hashicorp", "ruby", "gradle", "microsoft",
}
KNOWN_ACTIONS_REPOS = {
    "checkout", "setup-python", "setup-node", "setup-go", "setup-java",
    "upload-artifact", "download-artifact", "cache", "github-script",
    "stale", "labeler", "dependency-review-action", "delete-artifact",
    "attest-build-provenance", "upload-pages-artifact", "deploy-pages",
    "configure-pages", "create-github-app-token",
}


def extract_run_blocks(text: str):
    """抽出所有 run 块的文本（多行 | 与单行两种形态）。"""
    blocks = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\s*)-?\s*run:\s*(\|.*|>.*)?$", line)
        if m:
            indent = len(m.group(1))
            if m.group(2):
                body = []
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                        break
                    body.append(nxt)
                    i += 1
                blocks.append("\n".join(body))
                continue
            blocks.append(line)
        else:
            m2 = re.match(r"^(\s*)-?\s*run:\s+(.+)$", line)
            if m2:
                blocks.append(m2.group(2))
        i += 1
    return blocks


def scan_file(path: Path) -> list:
    hits = []
    text = path.read_text(encoding="utf-8", errors="replace")
    run_blocks = extract_run_blocks(text)
    joined_runs = "\n".join(run_blocks)

    for idx, block in enumerate(run_blocks):
        if SECRETS_REF.search(block):
            hits.append(f"R1 run块#{idx+1}: secrets context 展开进 shell")
        if ENCODING_CMDS.search(block) and (ENV_DUMP.search(block) or SECRETS_REF.search(block)):
            hits.append(f"R2 run块#{idx+1}: 编码命令与 env/secrets 同块出现")
        if EXFIL_CMDS.search(block):
            hits.append(f"R3 run块#{idx+1}: 外联原语")
        if LONG_B64.search(block):
            hits.append(f"R8 run块#{idx+1}: 长 base64 团块")

    if re.search(r"environment:\s*\$\{\{\s*matrix\.", text):
        hits.append("R4: environment 取自 matrix，环境级密钥批量展开")

    for m in re.finditer(r"uses:\s*([^\s@]+)@", text):
        repo = m.group(1)
        org = repo.split("/")[0]
        name = repo.split("/")[1] if "/" in repo else ""
        if org == "actions" and name not in KNOWN_ACTIONS_REPOS:
            hits.append(f"R5: actions/{name} 不在已知官方清单（疑似 typosquat）")
        elif org not in KNOWN_ORGS and not repo.startswith("./"):
            hits.append(f"R5: 引用非常见 org '{org}' 的 action")

    if "pull_request_target" in text:
        checks_out_head = re.search(r"ref:\s*\$\{\{\s*github\.event\.pull_request\.head", text)
        has_secrets_env = re.search(r"env:[\s\S]{0,200}\$\{\{\s*secrets\.", text)
        if checks_out_head and has_secrets_env:
            hits.append("R6: pull_request_target + 检出 PR head + secrets 注入")

    if "upload-artifact" in text and re.search(r"(env\s*\|[^>]*>|toJSON\(secrets\))[^|]*>", joined_runs):
        hits.append("R7: env/secrets 落盘 + 同 job upload-artifact")

    return hits


def scan(scenario: dict, applied_repo: Path) -> dict:
    hits = []
    for change in scenario["changes"]:
        p = applied_repo / change["path"]
        if p.exists() and ".github/workflows/" in change["path"].replace("\\", "/"):
            for h in scan_file(p):
                hits.append(f"{change['path']}: {h}")
    return {"detector": "M5-generic", "detected": bool(hits), "hits": hits}


if __name__ == "__main__":
    scenario = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    applied_repo = Path(sys.argv[2])
    result = scan(scenario, applied_repo)
    print(json.dumps(result, ensure_ascii=False, indent=2))
