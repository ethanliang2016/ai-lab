# reason-network 实测记录（v0.12.12，Windows 二进制）

> 定位：coding agent 之间的 P2P 通信引擎（iroh + MCP，iroh 出处：上游 Cargo.lock 含 iroh/iroh-relay 依赖）

## 实测路径

```powershell
.\reason-network.exe doctor   # 检测到本机 5 个 agent 全未接入
.\reason-network.exe init     # 建团队 ai-lab-test
# → team_id: 2dd2a4aa2def03e2a73ad7946ede6b87
# → relay: relay-sin1.compute.reasonmachines.com（新加坡）
```

## MCP 握手

- protocolVersion: `2024-11-05`
- 4 个工具：`ask_user`（弹窗签名回执）/ `check_inbox` / `list_team` / `send_message`
- `send_message` 附件上限：10 文件 × 256KB each，总 512KB
- server instructions 原文要点：**"message only when you need something / no small talk"**——把通信纪律写进协议层，不靠提示词自觉

## 单机双 session 闭环

```powershell
# 终端 1
.\reason-network.exe listen --as bob
# 终端 2：who 显示 bob + terminal 两个 session
.\reason-network.exe send alice->bob
# → "delivered: the session was waiting for messages" + ULID 01M5R669AEXKPXYWCSGPYR6W5J
# bob 端收到 <reason-message from="alice/terminal" agent="cli" id="..."> 封装 + 自动回复指引
```

## 生产落地评估

- ❌ relay 在新加坡：消息/附件出海，国内团队合规先卡死
- ❌ 跨网络到达率无公开数据（iroh 打洞失败走 relay，本次仅同机验证）
- ❌ 协议层无持久化语义承诺（丢/重消息未定义）
- ✅ 工具收敛（仅 4 个）、约束进协议、二进制单文件分发

结论：个人多 Claude Code 互聊可玩，团队生产等自托管 relay。
