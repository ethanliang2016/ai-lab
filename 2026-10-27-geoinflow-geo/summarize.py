# summarize.py — 从 api_results.json 提取六组对照结果
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

d = json.load(open("results/api_results.json", encoding="utf-8"))

# 1. 识别结果
rec = d["recognition"]["body"]
print("=== recognition keys:", list(rec.keys()))
print(json.dumps(rec, ensure_ascii=False)[:1200])

# 2. 分析主体结构
an = d["analysis"]["body"]
print("\n=== analysis keys:", list(an.keys()))
for k, v in an.items():
    if isinstance(v, list):
        print(f"  {k}: list[{len(v)}]", json.dumps(v[0], ensure_ascii=False)[:200] if v else "")
    elif isinstance(v, dict):
        print(f"  {k}: dict keys={list(v.keys())[:12]}")
    else:
        print(f"  {k}: {v}")
