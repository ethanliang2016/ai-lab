# Agent 团队化基建三件套实测物料

> CSDN 深度实测文章配套物料：《Agent 团队化基建三件套实测：harp + reason-network + Omnara》
> 实测日期 2026-10-25 · Windows 11 + Docker Desktop 29.8.2 + Node 24.19.0

## 三件套定位

| 项目 | 角色 | 本次实测方式 |
|---|---|---|
| Omnara（3235★） | agent 运行时/托管 | 完整自托管部署 + 双 turn 人机闭环 |
| reason-network（1192★） | agent 间通信 | 单机双 session 消息闭环 + MCP 握手 |
| harp（602★） | 人看 agent 的面板 | 源码架构分析（macOS only，Windows 无法运行） |

## 目录

```
2026-10-25-agent-team-stack/
├── agent.yaml              # Omnara 实测用的 agent 配置（代码审查助手，11 行）
├── omnara-reproduce.md     # Omnara 全链路复现步骤（compose → provider → launch → 人机闭环）
├── reason-network-notes.md # reason-network 实测记录
└── harp-analysis.md        # harp 源码架构分析要点
```

## 关键实测数据（Omnara）

- 全栈 10 容器一次起齐，migrate 退出码 0；api 启动即加载 **31,450 个 MCP server 注册表快照**
- 建 model provider 时服务端**实探 SiliconFlow /models 返回 68 个模型目录**（配置时验证凭据，而非运行时炸）
- Turn1 3.35s：模型识别 TOCTOU 竞态 + `ask_question` 结构化弹窗（1788 in / 270 out token）
- 挂起等人工回答 2m21s，`resolve` 后 **7.878ms** `tool_result` 进入时间线
- Turn2 6.47s 给出修复建议，`cache_read_input_tokens: 1536`（提示缓存跨挂起命中）
- worker 日志实证 durable execution：90s `runtime_lock` 租约 + `FenceExecutionRuntime` + `ClaimNextAgentWakeup`，单 turn 68 条命名 SQL

## 诚实披露

- harp 仅 macOS（README Install 节），本文档 harp 部分为源码静态分析
- reason-network relay 在新加坡，仅验证同机双 session，跨网络到达率未测
- Omnara 的 BYO machine / machine pool 未测，结论限于对话/审批/人机协同类 agent
