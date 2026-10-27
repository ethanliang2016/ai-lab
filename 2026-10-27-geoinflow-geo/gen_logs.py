# gen_logs.py — 生成 GEOInflow 实测物料：合成 Nginx combined 日志 + 内容清单 CSV + AI 引荐事件清单
# 全部 IP 为测试/文档用途；官方范围 IP 取自厂商公开 JSON（2026-10-27 拉取）
import json, random, datetime, csv, io

DATE = "27/Oct/2026"
random.seed(42)

# ---- 站点内容清单（20 个 URL）----
CATALOG = [
    "/", "/pricing", "/docs/quickstart", "/docs/api", "/docs/faq",
    "/blog/geo-guide", "/blog/crawler-101", "/blog/ai-search-trends", "/blog/case-study-1", "/blog/case-study-2",
    "/products/analytics", "/products/geo-weight", "/about", "/contact", "/whitepaper.pdf",
    "/blog/hot-page", "/blog/old-post-2019", "/docs/changelog", "/pricing/enterprise", "/landing/ai-campaign",
]
# 实际被爬的 12 个（盲区应为 8 个）
CRAWLED = ["/", "/pricing", "/docs/quickstart", "/docs/api", "/docs/faq",
           "/blog/geo-guide", "/blog/crawler-101", "/blog/ai-search-trends", "/blog/case-study-1",
           "/products/analytics", "/blog/hot-page", "/landing/ai-campaign"]

# ---- A 组：官方 UA（应识别出对应身份）----
AI_BOTS = {
    "GPTBot":            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot",
    "OAI-SearchBot":     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.3; +https://openai.com/searchbot",
    "ChatGPT-User":      "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
    "ClaudeBot":         "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ClaudeBot/1.0; +https://www.anthropic.com/claude-bot",
    "Claude-SearchBot":  "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-SearchBot/1.0; +https://www.anthropic.com/claude-searchbot",
    "Claude-User":       "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-User/1.0; +https://www.anthropic.com/claude-user",
    "PerplexityBot":     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "Perplexity-User":   "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
    "Amazonbot":         "Mozilla/5.0 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)",
    "Amzn-User":         "Mozilla/5.0 (compatible; Amzn-User/0.1; +https://developer.amazon.com/support/amazonbot)",
    "MistralAI-User":    "Mozilla/5.0 (compatible; MistralAI-User/1.0; +https://mistral.ai/bots)",
    "KimiBot":           "Mozilla/5.0 (compatible; KimiBot/1.0; +https://www.kimi.ai/policies/kimibot)",
    "Kimi-SearchBot":    "Mozilla/5.0 (compatible; Kimi-SearchBot/1.0; +https://www.kimi.ai/policies/kimi-searchbot)",
    "Kimi-User":         "Mozilla/5.0 (compatible; Kimi-User/1.0; +https://www.kimi.ai/policies/kimi-user)",
    "HySpider":          "Mozilla/5.0 (compatible; HySpider/1.0; +https://hy.tencent.com/policy/hyspider)",
    "Meta-ExternalAgent":"Mozilla/5.0 (compatible; Meta-ExternalAgent/1.1; +https://developers.facebook.com/docs/sharing/webmasters/crawler)",
    "Meta-ExternalFetcher":"meta-externalfetcher/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)",
    "Bytespider":        "Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)",
    "DuckAssistBot":     "Mozilla/5.0 (compatible; DuckAssistBot/1.2; +https://duckduckgo.com/duckassistbot)",
    "AI2Bot":            "Mozilla/5.0 (compatible; AI2Bot; +https://www.allenai.org/crawler)",
}
TRAD_BOTS = {
    "Googlebot":   "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Applebot":    "Mozilla/5.0 (compatible; Applebot/0.1; +http://www.apple.com/go/applebot)",
    "bingbot":     "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Baiduspider": "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
}
OTHER_BOTS = {
    "CCBot":      "CCBot/2.0 (https://commoncrawl.org/faq/)",
    "AhrefsBot":  "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
    "SemrushBot": "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)",
}
# ---- B 组：核验对照（官方范围 IP vs 伪装 IP）----
VERIFIED_PAIRS = [
    ("GPTBot",   AI_BOTS["GPTBot"],   "132.196.86.10"),   # openai.com/gptbot.json 官方 /24
    ("ClaudeBot",AI_BOTS["ClaudeBot"],"216.73.216.10"),   # claude.com/crawling/bots.json 官方 /22
]
SPOOFED = [
    ("GPTBot",   AI_BOTS["GPTBot"],   "8.8.8.8"),          # 官方 UA + 非官方 IP → 应判未通过
    ("ClaudeBot",AI_BOTS["ClaudeBot"],"1.1.1.1"),
    ("PerplexityBot", AI_BOTS["PerplexityBot"], "9.9.9.9"),
]
# ---- C 组：未知爬虫（应保持未知，不得臆造身份）----
UNKNOWN_BOTS = [
    "Mozilla/5.0 (compatible; GPTB0t/1.0; +https://evil.example)",   # 零替 O
    "FakeGPTBot/9.9",
    "TotallyUnknownBot/1.0 (+http://unknown.example)",
]
# ---- D 组：正常浏览器（日志侧非爬虫）----
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def rnd_pub_ip():
    return f"{random.choice([45,61,103,149,185,203])}.{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(1,254)}"

lines = []
def add(ip, ua, path, status=200, method="GET", hh=8, mm=0, size=None):
    size = size if size is not None else random.randint(500, 48000)
    ts = f"{DATE}:{hh:02d}:{mm:02d}:{random.randint(0,59):02d} +0800"
    lines.append(f'{ip} - - [{ts}] "{method} {path} HTTP/1.1" {status} {size} "-" "{ua}"')

hh = 0
# A 组：每个 AI 身份爬 2~3 页（PerplexityBot 重复抓 hot-page 5 次测“重复请求”）
for name, ua in AI_BOTS.items():
    for i, p in enumerate(random.sample(CRAWLED, 2)):
        add(rnd_pub_ip(), ua, p, hh=hh % 12, mm=(i * 17) % 60)
    hh += 1
for k in range(5):
    add(rnd_pub_ip(), AI_BOTS["PerplexityBot"], "/blog/hot-page", hh=3, mm=k * 7)
# 错误与特殊方法
add(rnd_pub_ip(), AI_BOTS["GPTBot"], "/blog/typo-page", status=404, hh=6)
add(rnd_pub_ip(), AI_BOTS["ClaudeBot"], "/docs/api", status=500, hh=7)
add(rnd_pub_ip(), AI_BOTS["OAI-SearchBot"], "/pricing", method="HEAD", hh=7, size=0)
add(rnd_pub_ip(), AI_BOTS["Bytespider"], "/home", status=301, size=0)
# 传统与其他用途
for name, ua in {**TRAD_BOTS, **OTHER_BOTS}.items():
    add(rnd_pub_ip(), ua, random.choice(CRAWLED), hh=9)
# B 组
for name, ua, ip in VERIFIED_PAIRS:
    add(ip, ua, "/blog/geo-guide", hh=10)
for name, ua, ip in SPOOFED:
    add(ip, ua, "/pricing", hh=10, mm=30)
# C 组
for ua in UNKNOWN_BOTS:
    add(rnd_pub_ip(), ua, "/", hh=11)
# D 组：浏览器直接访问（无 referer，日志侧）
for p in ["/", "/pricing", "/blog/geo-guide"]:
    add(rnd_pub_ip(), BROWSER_UA, p, hh=11)

lines.sort(key=lambda l: l[l.index("[") + 1:l.index("]")])
with open("access.log", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

# ---- 内容清单 CSV ----
buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["url", "title", "type", "wordCount", "publishedAt"])
for i, p in enumerate(CATALOG):
    w.writerow([p, f"Page {p}", "博客" if p.startswith("/blog") else "页面", random.randint(300, 4000), "2026-10-01"])
with open("catalog.csv", "w", encoding="utf-8", newline="") as f:
    f.write(buf.getvalue())

# ---- E 组：AI 引荐事件（浏览器采集口径，referer 主机识别）----
REFERRERS = [
    ("ChatGPT",     "https://chatgpt.com/share/abc"),
    ("ChatGPT旧域", "https://chat.openai.com/"),
    ("Perplexity",  "https://perplexity.ai/search?q=x"),
    ("Claude",      "https://claude.ai/chat/xyz"),
    ("Gemini",      "https://gemini.google.com/app/123"),
    ("Copilot",     "https://copilot.microsoft.com/chats/1"),
    ("豆包",        "https://doubao.com/chat/2"),
    ("Kimi",        "https://kimi.com/chat/3"),
    ("DeepSeek",    "https://chat.deepseek.com/"),
    ("文心一言",    "https://yiyan.baidu.com/"),
    ("对照-传统",   "https://www.google.com/search?q=x"),
    ("对照-传统",   "https://www.baidu.com/s?wd=x"),
    ("对照-未识别", "https://t.co/abc"),
    ("对照-未识别", "https://example.org/"),
]
with open("events.json", "w", encoding="utf-8") as f:
    json.dump([{"label": l, "referrer": r, "url": random.choice(CRAWLED)} for l, r in REFERRERS], f, ensure_ascii=False, indent=1)

print(f"access.log: {len(lines)} 行 | 已知 AI 身份 {len(AI_BOTS)} | 传统 {len(TRAD_BOTS)} | 其他 {len(OTHER_BOTS)}")
print(f"核验对照: 官方IP {len(VERIFIED_PAIRS)} / 伪装IP {len(SPOOFED)} | 未知 {len(UNKNOWN_BOTS)} | 浏览器 3")
print(f"catalog.csv: {len(CATALOG)} URL (盲区应为 {len(set(CATALOG)-set(CRAWLED))}) | events.json: {len(REFERRERS)}")
