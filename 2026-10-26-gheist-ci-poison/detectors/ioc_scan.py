#!/usr/bin/env python3
"""M4: Gheist IoC 规则扫描器
对照 Wiz 报告公布的 IoC 清单，检查一次变更（分支名 / commit message / 变更文件）是否命中。
命中任一指标即判定检出。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

# Wiz 报告 IoC（2026-10-25）
IOC_BRANCH = re.compile(r"^ci-sync-[0-9a-z]{6}$")
IOC_COMMIT_MSG = "ci: sync config"
IOC_WORKFLOW_PATH = ".github/workflows/sync-check.yml"
# Wiz 报告 IoC 原文标记（严格口径，不做宽松扩展）
IOC_CONTENT_MARKERS = [
    "toJSON(secrets) }}' | base32 -w 120",
    "gdmp-pivot",
    ".gdmp_pat",
    ".gdmp_patg",
    ".gdmp_sweep",
]
IOC_BLOB_SHAS = {
    "f3da2b8b357dcda02fd455d314be2a95007516a6",  # plain
    "d09535857a741bbb976bdc084a9a021713133291",  # timeout
    "1dc5af9cce950aad1eb1546ecce8565b117540c4",  # separator
    "c665b778b2d822453293003e7ca0bbb2cb08e39d",  # self-hosted job
}


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def scan(scenario: dict, applied_repo: Path) -> dict:
    hits = []

    if IOC_BRANCH.match(scenario["branch"]):
        hits.append(f"branch name matches ^ci-sync-[0-9a-z]{{6}}$: {scenario['branch']}")

    if scenario["commit_message"].strip() == IOC_COMMIT_MSG:
        hits.append(f"commit message is exactly '{IOC_COMMIT_MSG}'")

    only_paths = [c["path"] for c in scenario["changes"]]
    if only_paths == [IOC_WORKFLOW_PATH]:
        hits.append(f"only change is new file at {IOC_WORKFLOW_PATH}")

    for change in scenario["changes"]:
        content_path = applied_repo / change["path"]
        if not content_path.exists():
            continue
        raw = content_path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        for marker in IOC_CONTENT_MARKERS:
            if marker in text:
                hits.append(f"content marker '{marker}' in {change['path']}")
        sha = git_blob_sha(raw)
        if sha in IOC_BLOB_SHAS:
            hits.append(f"blob SHA {sha[:8]}... matches Wiz IoC list")

    return {"detector": "M4-ioc", "detected": bool(hits), "hits": hits}


if __name__ == "__main__":
    scenario = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    applied_repo = Path(sys.argv[2])
    result = scan(scenario, applied_repo)
    print(json.dumps(result, ensure_ascii=False, indent=2))
