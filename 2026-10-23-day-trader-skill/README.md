# day-trader-skill 实测物料 · A 股适配补丁

> CSDN 实测文章配套代码。改 1 行正则让上游 risk/check.py 支持 A 股 6 位数字 ticker，附带今日（2026-10-23）真实行情的风控验证快照。

## 快速上手

```bash
# 1. 安装依赖（零，纯 Python 标准库）
cd repo  # 上游仓库

# 2. 用改了正则的版本跑 A 股风控
python trader-risk/check.py \
  --orders trader/orders-688836.json \
  --now "2026-10-23 10:00" \
  --no-write
```

## 改动清单（全部相对上游 `Jakeschincariol/day-trader-skill`）

| 文件 | 改动 | 作用 |
|---|---|---|
| `trader-risk/check.py` L87 | `TICKER = re.compile(r"^([A-Z]{1,5}([.\-][A-Z]{1,2})?\|\d{6})$")` | 支持 A 股 6 位数字 ticker |
| `trader/config.60w.json` | A 股 60w 账户参数 | PASS 场景配置 |
| `trader/plan-688836.json` | 宇树科技 688836 交易计划 | 10-23 行情快照 |
| `trader/orders-688836.json` | 宇树科技 bracket order | risk/check.py 输入 |

## TICKER 正则 diff

```diff
- TICKER = re.compile(r"^[A-Z]{1,5}([.\-][A-Z]{1,2})?$")
+ TICKER = re.compile(r"^([A-Z]{1,5}([.\-][A-Z]{1,2})?|\d{6})$")
```

正则是"美市 1-5 位字母 **或** A 股 6 位数字"，两条路并存，不破坏美市支持。

## 今日 A 股风控结果（2026-10-23）

**原始小账户直接跑 688836，5 层 limit 同时 BLOCK：**
```
- size: $53,010 is over your $4,000 max order
- cash: needs $53,010 but only $5,000 cash
- position: 1060.2% of $5,000 account, over 75% cap
- loss: 100 shares x 52.46 risk a share = $5,246 at the stop, over your $50 max loss per trade
- daily loss: $5,246 over $150 daily limit
```

**调 60w 账户 config 后 PASS：**
```
PASS  #1 buy 688836 100 shares, entry
  max loss $5,246 (limit $6,000), reward:risk 1.00 (min 1)
1 passed, 0 blocked
```

**max_loss 降到 4000 后 BLOCK（仅此一层触发）：**
```
BLOCK #1 buy 688836 100 shares, entry
  max loss $5,246 (limit $4,000)
  - loss: 100 shares x 52.46 risk a share = $5,246 at the stop, over your $4,000 max loss per trade
Blocked orders do not go to the broker. Fix the order or your rules, then check again.
```

## SiliconFlow 接 Claude Code 配置

详见 `siliconflow-cc.example.json`。关键：**必须用 `ANTHROPIC_AUTH_TOKEN`**（发 `Authorization: Bearer` header），不能用 `ANTHROPIC_API_KEY`。

## 文章链接

（CSDN 发布后回填 article ID）

## 不包含

- 上游完整仓库代码（请自行 clone `Jakeschincariol/day-trader-skill`）
- test-settings.json（含真实 API key，已脱敏）
- .claude/skills/（本地运行时状态）
