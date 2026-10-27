# verdict.py — 六组对照最终判定
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

d = json.load(open("results/api_results.json", encoding="utf-8"))
an = d["analysis"]["body"]

# ---- A组：识别身份 ----
print("== A组 识别到的 bot（请求统计）==")
for b in an["bots"]:
    print(f"  {b['name']:<22} req={b['requests']:<3} 2xx={b['status2xx']} 4xx={b['status4xx']} 5xx={b['status5xx']}")

# ---- B组：身份核验 findings ----
print("\n== B/C组 identity findings（核验/未知）==")
for f in an["findings"]:
    if f["type"] == "identity":
        print(f"  {f['botId']:<20} grade={f['grade']:<8} conf={f['confidence']:<10} state={f['state']}")
        # 打印 detail 摘要
        for k in ("message", "reason", "detail", "evidence"):
            if k in f:
                print(f"      {k}: {str(f[k])[:160]}")

# ---- bot 类型分布 ----
kinds = {}
for b in an["directory"]:
    kinds.setdefault(b["kind"], []).append(b["id"])
print("\n== directory 身份类型分布 ==")
for k, v in kinds.items():
    print(f"  {k}: {len(v)}")

# ---- E组：平台归因 ----
print("\n== E组 platforms（非 unknown 状态）==")
for p in an["platforms"]:
    if p.get("state") != "unknown":
        print(f"  {p['platformId']:<16} state={p['state']} visits={p.get('visits')}")

# ---- 盲区 ----
crawled_paths = sorted({p["path"] for p in an["pages"]})
CATALOG = ["/", "/pricing", "/docs/quickstart", "/docs/api", "/docs/faq",
    "/blog/geo-guide", "/blog/crawler-101", "/blog/ai-search-trends", "/blog/case-study-1", "/blog/case-study-2",
    "/products/analytics", "/products/geo-weight", "/about", "/contact", "/whitepaper.pdf",
    "/blog/hot-page", "/blog/old-post-2019", "/docs/changelog", "/pricing/enterprise", "/landing/ai-campaign"]
blind = [u for u in CATALOG if u not in crawled_paths]
print(f"\n== 盲区：目录 {len(CATALOG)} URL，bot 实际爬 {len(crawled_paths)}，未覆盖 {len(blind)} ==")
print("  ", blind)

# ---- findings 类型分布 ----
types = {}
for f in an["findings"]:
    types.setdefault(f["type"], 0)
    types[f["type"]] += 1
print("\n== findings 类型分布 ==", types)

# 非 identity 的 findings 抽样
print("\n== 非 identity findings 抽样 ==")
for f in an["findings"]:
    if f["type"] != "identity":
        msg = next((f.get(k) for k in ("message", "reason", "detail") if k in f), json.dumps({k: v for k, v in f.items() if k not in ('key', 'botId', 'type', 'pathGroup', 'grade', 'confidence', 'state')}, ensure_ascii=False)[:120])
        print(f"  [{f['type']}] {f['botId']:<18} {f['grade']:<7} {str(msg)[:150]}")
        if sum(1 for _ in [0]) and list(x for x in an["findings"] if x["type"] != "identity").index(f) > 8:
            break
