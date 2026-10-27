# dump_finding.py — gptbot finding 全量 + analytics 摘要
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open("results/api_results.json", encoding="utf-8"))
an = d["analysis"]["body"]
for f in an["findings"]:
    if f["botId"] == "gptbot":
        print(json.dumps(f, ensure_ascii=False, indent=1)[:1800])
        break
print("\n=== analytics ===")
print(json.dumps(d["analytics"]["body"], ensure_ascii=False, indent=1)[:800])
