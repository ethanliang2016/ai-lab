# harp 源码架构分析（macOS only，未实机运行）

> 定位：Warp 终端的非官方 fork（AGPL-3.0），把 tab bar 换成 agent 感知侧边栏
> 诚实披露：README Install 节仅 dmg + `script/macos/run`，Windows 无法运行，本文为源码静态分析

## 规模与改动面

- 80 个 crates（`warp_*` 前缀 24 个），大部分原样继承上游
- README 原文（L67-69）："Everything else is upstream Warp... They talk to Warp's servers exactly as upstream does; Harp adds no servers of its own. **Logging in through Harp is untested.**"

## 核心创新：agent 感知侧边栏

每个会话带状态标签：working / waiting for you / done / inactive / background——解决"人同时盯多个 agent 时注意力怎么分配"的问题。

## 值得抄的两个设计

### limit-rings（额度环）

- 侧边栏底部画供应商额度双环（5 小时窗 + 周额度）
- Claude Code 额度只在 status line 出现 → harp 注入 statusLine 命令落盘再读
- **开放 JSON 契约**（docs/limit-rings.md）：任何外部工具可写入该文件，harp 每 30 秒重读；超 15 分钟标记 stale（虚线环）；用量 ≥80% 加粗
- 用文件做进程间契约：土，但零耦合、易调试

### multi_agent_client 只有 5.8KB

HTTP/SSE + protobuf 的薄客户端——说明 **Warp 原版本来就有 multi-agent 通道，harp 的创新在 UI 层而非协议层**。评估其长期价值时这一点很关键：UI 层创新容易被上游直接吸收。

## 风险

- 非官方 fork 跟踪上游的成本真实存在
- 登录路径官方自承未测试
- Windows/Linux 无支持计划迹象
