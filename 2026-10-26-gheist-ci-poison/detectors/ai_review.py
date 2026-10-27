#!/usr/bin/env python3
"""M6: LLM 审查 PR diff（SiliconFlow / DeepSeek-V3）
把每个变体的 PR diff 交给 DeepSeek-V3 做安全审查，要求输出结构化结论。
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
RUNS = LAB / "runs"

API_URL = "https://api.siliconflow.cn/v1/chat/completions"
API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
MODEL = "deepseek-ai/DeepSeek-V3"

PROMPT = """你是 CI/CD 供应链安全审查员。下面是一个仓库的 PR diff（变更仅限 GitHub Actions workflow）。
请判断该变更是否存在窃取 secrets / 投毒风险，只输出 JSON：
{"verdict": "malicious" 或 "suspicious" 或 "clean", "reasons": ["..."], "hotspot_lines": ["..."]}

审查要点：secrets context 进入 shell、日志回传、编码绕过脱敏、外联地址、action 名称仿冒、pull_request_target 滥用、environment 批量展开、artifact 夹带。

PR diff 如下：
"""


def review(diff: str) -> dict:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT + diff[:12000]}],
        "temperature": 0,
        "max_tokens": 800,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    try:
        start = text.find("{")
        verdict = json.loads(text[start:text.rfind("}") + 1])
    except Exception:
        verdict = {"verdict": "parse_fail", "raw": text[:300]}
    verdict["_usage"] = usage
    return verdict


def main():
    if not API_KEY:
        print("SILICONFLOW_API_KEY not set", file=sys.stderr)
        sys.exit(2)
    out = {}
    for d in sorted(RUNS.iterdir()):
        f = d / "pr.diff"
        if not f.exists():
            continue
        diff = f.read_text(encoding="utf-8", errors="replace")
        v = review(diff)
        out[d.name] = v
        print(f"{d.name}: {v.get('verdict')} (in={v.get('_usage',{}).get('prompt_tokens')} out={v.get('_usage',{}).get('completion_tokens')})")
        time.sleep(1)
    (LAB / "results" / "ai_review.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
