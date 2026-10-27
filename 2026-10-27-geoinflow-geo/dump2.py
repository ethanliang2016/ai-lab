# dump2.py — claudebot findings + 盲区 + referrer 指标
import json, io, sys, time, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open("results/api_results.json", encoding="utf-8"))
an = d["analysis"]["body"]

print("== claudebot/gptbot 全部 findings ==")
for f in an["findings"]:
    if f["botId"] in ("gptbot", "claudebot"):
        facts = f.get("facts") or {}
        print(f"  {f['botId']:<10} {facts.get('reason','')} ev={facts.get('evidence')}")

print("\n== 盲区 ==")
crawled = sorted({p["path"] for p in an["pages"]})
CATALOG = ["/", "/pricing", "/docs/quickstart", "/docs/api", "/docs/faq",
    "/blog/geo-guide", "/blog/crawler-101", "/blog/ai-search-trends", "/blog/case-study-1", "/blog/case-study-2",
    "/products/analytics", "/products/geo-weight", "/about", "/contact", "/whitepaper.pdf",
    "/blog/hot-page", "/blog/old-post-2019", "/docs/changelog", "/pricing/enterprise", "/landing/ai-campaign"]
blind = [u for u in CATALOG if u not in crawled]
extra = [u for u in crawled if u not in CATALOG]
print(f"  爬取路径数(去重)={len(crawled)} 盲区({len(blind)}): {blind}")
print(f"  目录外路径({len(extra)}): {extra}")

# Umami 标准 metrics referrer
BASE = "http://127.0.0.1:3002"
WID = "72ea879b-bff8-4e6a-a896-d2cf99955850"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
with urllib.request.urlopen(r, data=json.dumps({"username": "admin", "password": "liekan"}).encode(), timeout=30) as resp:
    token = json.loads(resp.read())["token"]
now = int(time.time() * 1000)
day0 = 1793049600000
r = urllib.request.Request(f"{BASE}/api/websites/{WID}/metrics?startAt={day0}&endAt={now}&type=referrer")
r.add_header("Authorization", f"Bearer {token}")
with urllib.request.urlopen(r, timeout=30) as resp:
    print("\n== metrics referrer ==")
    print(json.dumps(json.loads(resp.read()), ensure_ascii=False)[:700])
