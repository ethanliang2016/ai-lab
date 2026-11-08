# craft-anything实测 · CSDN发布物料

## 标题（三选一，推荐第一个）

1. craft-anything实测：321个工具的逆向工程Agent，默认把自己锁在"洁净室"里
2. 321工具17引擎实测：这个逆向Agent默认不读目标内部，--deep才放行
3. 拿notepad.exe实测craft-anything：clean-room硬拦截、证据账本、MCP自测全内建

## 摘要（发布页"编辑摘要"栏）

> Storytold开源的craft-anything（v0.4.0）实测：commands列出321个工具、17个toolset，与官方宣称精确一致。默认clean-room模式把"读目标内部"的工具全部硬拦截，triage notepad.exe第一次直接被拒；--deep后完整识别PE/MSVC Rich header/符号剥离，还主动声明启发式提示可被伪造。附国内网络部署三连坑（无Windows包/deb截断/镜像卡死）与最终可复现路径。

## 标签

```
人工智能  Agent  逆向工程  安全  MCP  Rust  craft-anything
```

## 专栏登记

- 专栏：agent安全与评测
- 本篇序号：第⑧篇（专栏⑮位置，以实际登记为准）
- 关联：⑥A2A跨进程Mandate防重放、⑦Mandate持久化重启恢复（文末已留系列链接位，⑥⑦发布后回填URL）

## 发布前清单

- [ ] CSDN稿全文粘贴，代码块语言标注（powershell/json/无标注文本）
- [ ] 插入截图：①doctor输出 ②toolset表 ③triage的--deep结果JSON ④report.html渲染图（evidence\report.html，3212字节）
- [ ] 摘要/标签填入
- [ ] ⑥⑦已发布则回填文末系列链接；未发布保持"待发布补链接"
- [ ] 登记专栏清单（序号/标题/URL/日期）
- [ ] ai-lab仓库推送本次实测目录

## 封面建议

尺寸1536x864。构图：左侧终端窗口显示`craft-anything-cli commands`滚动321行工具名，右侧一扇半开的门，门上挂牌"clean-room"，门缝透出PE文件十六进制光。冷色调（深蓝+青），标题字：craft-anything 实测。

## 证据文件清单（随稿存档）

| 文件 | 内容 |
| --- | --- |
| evidence\run_log.txt | T0~T5全量实测日志（version/doctor/capabilities/commands/triage×2/report×2） |
| evidence\report.html | triage后生成的HTML调查报告（3212字节，evidence_records=1） |
| cargo-fetch.log | 773行依赖下载记录 |
| cargo-build.log | 编译全日志（13m20s，零error） |
