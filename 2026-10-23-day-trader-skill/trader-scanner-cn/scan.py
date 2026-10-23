#!/usr/bin/env python3
"""A-share Chart Scanner for trader-scanner-cn. 东方财富直连,纯 Python + requests.

接口与上游 trader-scanner 对齐:
    python3 scan.py universe                      # 拉全市场 5000+ 只 -> trader/universe-cn.txt
    python3 scan.py daily                        # 盘前:20 日 close breakout -> trader/watchlist.json
    python3 scan.py daily --symbols 688836,600519
    python3 scan.py orb                          # 盘中:开盘后 15 分钟 breakout
    python3 scan.py orb --at 10:15               # 截钟
    python3 scan.py orb --symbols 688836         # 小范围验证(全市场分钟线拉太慢)
    python3 scan.py orb --offline fixtures.json --now "2026-10-23 10:15"

数据源:push2.eastmoney.com / push2his.eastmoney.com(国内直连 200 OK)
    universe  -> clist/get, fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23(深A主+创业+沪A主+科创)
    daily     -> kline/get, klt=101(日线), fqt=1(前复权)
    orb       -> kline/get, klt=1(1分钟线,拼 5 分钟)
"""
import argparse, json, os, re, sys, time, gzip, random
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRADER = os.path.join(ROOT, "trader")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
EM_CLIST = "https://push2.eastmoney.com/api/qt/clist/get"
EM_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

# A-share 板块代码:fs 字段
# m:0=深市主板 t:6=深主;t:80=创业板
# m:1=沪市主板 t:2=沪主;t:23=科创板
FS_ALL = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"


# ─── universe ──────────────────────────────────────────────────────────────────

def universe(out_path):
    """拉全市场 5000+ 只 A 股,过滤 ST/退市/空壳,按成交额排序。"""
    items = []
    for pn in range(1, 8):  # 7 页 × 1000 = 7000 上限够覆盖
        r = requests.get(EM_CLIST, params={
            "pn": pn, "pz": 1000, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2", "invt": "2", "fid": "f6",
            "fs": FS_ALL,
            "fields": "f12,f14,f2,f3,f5,f6,f15,f16,f17,f18"
        }, headers=HEADERS, timeout=15)
        batch = r.json().get("data", {}).get("diff", [])
        if not batch:
            break
        items.extend(batch)
        print(f"  page {pn}: +{len(batch)} = {len(items)}")
        time.sleep(0.2)

    # 过滤 ST / 退市 / 空壳
    kept = []
    for it in items:
        name = it.get("f14", "")
        code = it.get("f12", "")
        if "ST" in name or "退" in name or "*" in name:
            continue
        if not code or not code.isdigit() or len(code) != 6:
            continue
        price = it.get("f2")
        if not price or price <= 0:
            continue
        kept.append((code, name))

    out = os.path.join(TRADER, out_path)
    with open(out, "w", encoding="utf-8") as f:
        for code, name in kept:
            f.write(f"{code}|{name}\n")
    print(f"universe: {len(kept)} stocks -> {out}")
    return kept


def _secid(code):
    """600/601/603/688 -> m:1(沪),000/001/002/300 -> m:0(深)。"""
    return f"1.{code}" if code.startswith(("60", "68", "90")) else f"0.{code}"


def _klines(code, klt="101", beg="20260901", end=None):
    """拉 K 线,返回 [(date, open, close, high, low), ...]"""
    if end is None:
        end = time.strftime("%Y%m%d")
    r = requests.get(EM_KLINE, params={
        "secid": _secid(code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": klt, "fqt": "1", "beg": beg, "end": end
    }, headers=HEADERS, timeout=15)
    klines = (r.json().get("data") or {}).get("klines", [])
    out = []
    for k in klines:
        p = k.split(",")
        out.append((p[0], float(p[1]), float(p[2]), float(p[3]), float(p[4])))
    return out


# ─── daily scan ───────────────────────────────────────────────────────────────

def daily(out_path, watchlist_path=None, symbols=None, min_price=5, min_volume=10000, limit=200):
    """盘前扫描:20 日 close breakout。"""
    # 拉候选池
    if symbols:
        pool = [(s, "") for s in symbols.split(",")]
    else:
        pool = [(l.split("|")[0], l.split("|")[1]) for l in open(watchlist_path or os.path.join(TRADER, "universe-cn.txt"), encoding="utf-8") if l.strip()]

    hits = []
    for i, (code, name) in enumerate(pool[:limit * 3]):  # 多拉点再过滤
        try:
            kl = _klines(code, klt="101", beg=(time.strftime("%Y%m%d", time.localtime(time.time() - 120 * 86400))))
            if len(kl) < 22:
                continue
            last = kl[-1]
            _, open_, close, high, low = last
            if close < min_price:
                continue
            # breakout_20d: last close > 20 个 close 前的每个 close
            closes_prev20 = [k[2] for k in kl[-21:-1]]
            if close > max(closes_prev20):
                hits.append({"symbol": code, "name": name, "close": close, "setup": "breakout_20d",
                             "date": last[0], "high": high, "low": low})
            time.sleep(0.15)
        except Exception as e:
            if i < 5:
                print(f"  {code} err: {e}")
            continue
        if i % 100 == 0 and i > 0:
            print(f"  scanned {i}/{len(pool)}")

    hits.sort(key=lambda x: x["close"], reverse=True)
    hits = hits[:limit]

    out = os.path.join(TRADER, out_path)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"mode": "daily", "as_of": time.strftime("%Y-%m-%d %H:%M"),
                   "scanned": min(i + 1, len(pool)), "hits": hits}, f, indent=2, ensure_ascii=False)

    print(f"daily: {len(hits)} hits, top 5 by close:")
    for h in hits[:5]:
        print(f"  {h['symbol']} {h['name']:<8} close={h['close']:.2f} setup={h['setup']}")
    return hits


# ─── orb scan ─────────────────────────────────────────────────────────────────

def orb(out_path, symbols=None, at=None, now_str=None, offline=None, min_price=5, or_minutes=15, max_confirm=50):
    """开盘后区间 breakout。A 股开盘 9:30,区间=前 15 分钟的 5 根 1 分钟 bar 聚合。"""
    import datetime as dt

    now_dt = dt.datetime.strptime(now_str or time.strftime("%Y-%m-%d %H:%M"), "%Y-%m-%d %H:%M")

    if offline:
        kl_all = json.load(gzip.open(offline)) if offline.endswith(".gz") else json.load(open(offline))
    elif symbols:
        kl_all = {}
        for s in symbols.split(","):
            kl_all[s.strip()] = _klines(s.strip(), klt="1", beg=now_dt.strftime("%Y%m%d"), end=now_dt.strftime("%Y%m%d"))
            time.sleep(0.2)
    else:
        print("orb: 需要 --symbols 或 --offline(全市场分钟线拉太慢,不做)")
        return

    hits = []
    usable = 0
    candidates = 0

    for code, klines in kl_all.items():
        # 聚合 1 分钟 bar 到 5 分钟
        bars = _aggregate_5m(klines, now_dt)
        if not bars:
            continue
        usable += 1
        if len(bars) < or_minutes // 5 + 2:
            continue
        # 区间 high = 前 or_minutes/5 根 bar 的最高 high
        range_bars = bars[: or_minutes // 5]
        rh = max(b["high"] for b in range_bars)
        # 找第一根 close > rh 的 bar
        for b in bars[or_minutes // 5 :]:
            if b["close"] > rh:
                if candidates < max_confirm:
                    hits.append({"symbol": code, "time": b["time"],
                                 "close": b["close"], "range_high": rh,
                                 "range_low": min(b["low"] for b in range_bars),
                                 "over_pct": round((b["close"] - rh) / rh * 100, 2)})
                    candidates += 1
                break

    out = os.path.join(TRADER, out_path)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"mode": "orb", "as_of": now_str or time.strftime("%Y-%m-%d %H:%M"),
                   "or_minutes": or_minutes, "usable": usable, "hits": hits},
                  f, indent=2, ensure_ascii=False)

    print(f"orb: {usable} usable, {len(hits)} hits, top 5:")
    for h in hits[:5]:
        print(f"  {h['symbol']} {h['time']} ${h['close']:.2f} range {h['range_low']:.2f}-{h['range_high']:.2f} +{h['over_pct']}%")
    return hits


def _aggregate_5m(klines, now_dt):
    """把 1 分钟 K 线聚合为 5 分钟,只保留 <= now_dt 的完整 bar。"""
    bars = []
    bucket = None
    for date_s, open_, close, high, low in klines:
        try:
            d, t = date_s.split(" ")
            bar_dt = dt.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if bar_dt > now_dt:
            break
        # A 股上午 9:30-11:30 下午 13:00-15:00,跳过午休
        hh = bar_dt.hour
        mm = bar_dt.minute
        if (hh == 11 and mm >= 30) or (hh == 12) or (hh == 13 and mm == 0):
            # 11:30 之后到 13:00 之前跳,13:00 第一根归下午
            if hh == 13 and mm == 0:
                pass
            else:
                continue
        # 5 分钟桶:bar_dt 向下取整到 5
        floor_min = (mm // 5) * 5
        floor_dt = bar_dt.replace(minute=floor_min, second=0)
        if bucket is None or bucket["time"] != floor_dt:
            if bucket:
                bars.append(bucket)
            bucket = {"time": floor_dt, "open": open_, "close": close, "high": high, "low": low}
        else:
            bucket["close"] = close
            bucket["high"] = max(bucket["high"], high)
            bucket["low"] = min(bucket["low"], low)
    if bucket:
        bars.append(bucket)
    return bars


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["universe", "daily", "orb"])
    ap.add_argument("--symbols", default=None)
    ap.add_argument("--watchlist", default=None)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--min-price", type=float, default=5)
    ap.add_argument("--min-volume", type=int, default=10000)
    ap.add_argument("--now", default=None)
    ap.add_argument("--at", default=None)
    ap.add_argument("--or-minutes", type=int, default=15)
    ap.add_argument("--max-confirm", type=int, default=50)
    ap.add_argument("--offline", default=None)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    os.makedirs(TRADER, exist_ok=True)

    if args.mode == "universe":
        universe("universe-cn.txt")
    elif args.mode == "daily":
        hits = daily("watchlist.json", args.watchlist, args.symbols, args.min_price, args.min_volume, args.limit)
        if not args.no_write:
            with open(os.path.join(TRADER, "watchlist.json"), "w", encoding="utf-8") as f:
                json.dump({"mode": "daily", "hits": hits}, f, indent=2, ensure_ascii=False)
    elif args.mode == "orb":
        hits = orb("watchlist.json", args.symbols, args.at, args.now, args.offline,
                   args.min_price, args.or_minutes, args.max_confirm)
        if not args.no_write:
            with open(os.path.join(TRADER, "watchlist.json"), "w", encoding="utf-8") as f:
                json.dump({"mode": "orb", "hits": hits}, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
