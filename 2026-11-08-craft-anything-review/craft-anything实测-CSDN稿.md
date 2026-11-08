# craft-anything实测：321个工具的逆向工程Agent，默认把自己锁在"洁净室"里

> 结论先给：Storytold开源的craft-anything（v0.4.0，Rust）是我今年实测过工具量最大的Agent工作台——`commands`实测**321个工具、17个toolset，与官方宣称精确一致**。但比数量更值得注意的是它的默认姿态：**clean-room默认开启，凡是要"看目标内部"的工具一律拒绝执行**，必须显式`--deep`才放行。拿notepad.exe做first-look，clean-room下直接被拒（`reason:"clean_room"`）；`--deep`后完整识别PE/x86_64/MSVC Rich header/符号剥离，还主动声明"工具链提示来自可被伪造的标记"。证据账本、授权分级、MCP自测（协议2025-06-18）全是内建的。对做合规逆向和安全研究的人，这套默认设置比功能清单更值钱。

---

## 0. 这个项目是干什么的

craft-anything是Storytold开源的逆向工程Agent工作台（GitHub: storytold/craft-anything，Rust workspace，edition 2024）。一句话：**给编码Agent装上逆向工程的手和眼**——原生二进制、.NET、Java、Android、Apple、Electron、固件、pcap、数据库，都能作为"目标"打开、分析、写报告。

三种形态同一套引擎：

- egui桌面GUI（给人用）
- craft-anything-cli（本次实测对象，每个工具都是子命令）
- MCP server（`craft-anything-cli mcp`，挂进Claude Code/Codex等编码Agent）

前两篇（⑥A2A跨进程防重放、⑦Mandate持久化）测的是自研授权机制，这篇换个路子：拿一个真实开源Agent项目做全量实测，看它的安全设计做到了什么程度。评测视角不变：不看宣传，看运行时证据。

## 1. 部署实录：国内网络的三连坑与最终路径

先把部署账摊开，这部分对国内读者可能比功能更有用。

**坑1：Release没有Windows包。** v0.4.0的Release assets只有Linux（AppImage/deb/flatpak/pkg.tar.zst）、macOS、FreeBSD。Windows用户只有两条路：WSL，或者本地源码编译。

**坑2：deb下载反复截断。** 走Docker路线时，`craft.deb`（26.8MB）在沙箱里被长HTTP超时截断，下了4次分别是3.5/16.8/19.4/26.8MB，dpkg报"unexpected end of file in archive magic"。容器内curl同样HTTP/2流中断（curl: 18）。

**坑3：Docker源码构建卡镜像层。** 改多阶段Dockerfile（rust:1.97-bookworm内cargo build），基础镜像最后一个64.41MB的层拉到4.19MB后停滞20多分钟。

**最终路径（代理+本地编译，全程可复现）：**

```powershell
# 1. 开代理后装Rust（rustup-init.exe，12MB，13秒下完）
.\rustup-init.exe -y --default-toolchain stable --profile minimal --no-modify-path
# 2. 装VS Build Tools C++工作负载（MSVC链接器，cargo编译刚需）
.\vs_BuildTools.exe --quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended
# 3. 浅克隆v0.4.0（800文件）后编译CLI
cargo build --release -p craft-anything-cli
#    773个crate依赖，编译13分20秒，零错误
```

产物：`craft-anything-cli.exe`单文件36.5MB。中间还处理了一个插曲：rustup首次装stable工具链时组件下载重命名失败（os error 2），`rustup toolchain install stable --profile minimal --force`强制重装后恢复——代理环境下这类部分下载残留要清掉`.rustup\downloads\*.partial`。

## 2. T1 doctor：它认得你机器上每个Agent

`craft-anything-cli doctor`的输出是逐项结构化检查，三类内容：

**Agent注册探测**——它扫描出我机器上装了7个编码Agent，并各自给出接入命令：

```
registration:claude_code     info  Claude Code is installed but not connected.
registration:claude_desktop  info  Claude Desktop is installed but not connected.
registration:codex           info  Codex is installed but not connected.
registration:vscode          info  VS Code is installed but not connected.
registration:opencode        info  OpenCode is installed but not connected.
registration:copilot_cli     info  GitHub Copilot CLI is installed but not connected.
registration:workbuddy       info  WorkBuddy is installed but not connected.
registration:dsh             info  DeepSeek harness (DSH) is set up by hand.
```

每条`remediation`都指向同一条命令：`craft-anything-cli setup --client <名字>`。同时还探测了`~/.claude/skills`、`~/.agents/skills`、`~/.workbuddy/skills`三个skill目录——它走的是"注册MCP+装skill"双通道接入路线。

**引擎分级**——18个外部引擎全部标注optional，本机只找到2个：

```
engine:chromium  ok    a Chromium-based browser: ...\chrome.exe
engine:java      ok    Java runtime: D:\Program Files\Java\jdk-21.0.11\bin\java.exe
engine:ghidra    info  Ghidra not found (optional; Deep mode: richer decompiled code).
engine:frida     info  Frida not found (optional; Tracing apps while they run).
...（jadx/apktool/gdb/lldb/mitmdump/binwalk/unblob/ilspy/tshark/objdump/rizin/rtl433/vineflower共14个同上）
```

注意设计：没有任何引擎是required。内置引擎（builtin）兜底全部基础能力，外部引擎只作"second opinion"（Ghidra加深反编译、binwalk给固件提取第二意见、objdump/rizin给反汇编第二意见）。**缺谁都能跑，有谁就看得更细。**

**MCP自测**——doctor顺手起了一个MCP握手：

```
mcp:self-test  ok  MCP server answered (protocol 2025-06-18, 30 tools listed).
```

协议版本2025-06-18（较新的MCP规范），默认暴露30个工具（Essentials集+已启用toolset），`--all-tools`才放全量321个。默认收敛攻击面，这个后面细说。

## 3. T2/T3：321个工具的家底与"默认不可用"清单

`capabilities`先给总账：

```json
{"analysis_mode":"clean-room","host":"windows-x86_64","tools":321,
 "engines":[...18个，found=true仅chromium/java...]}
```

`commands`输出全量清单，实测统计：

```
工具总数: 321
native 72 | core 35 | web 24 | adb 23 | project 20 | apple 16
android 13 | js 13 | app 12 | frida 9 | rebuild 9 | game 9
managed 8 | engines 7 | formats 7 | build 6 | java 6 | 其余23
```

官方口径"301 engine tools + AI/setup约20"，合计321——**实测数与官方宣称精确一致，没有水分**。

17个toolset逐一点名（clean-room默认模式下各集可用工具数）：

| toolset | 用途 | clean-room下可用 |
| --- | --- | --- |
| core | Essentials（目标/证据/会话管理） | 28/36 |
| native | 原生程序逆向 | **0/55** |
| apple | Apple应用 | 0/14 |
| formats | 文件格式解析 | 0/36 |
| managed | .NET应用 | 0/8 |
| android | Android应用 | 2/14 |
| java | Java程序 | 0/6 |
| adb | 连接手机 | 0/24 |
| browser | 网站分析（活浏览器） | 7/22 |
| javascript | Electron/JS | 0/11 |
| runtime | 运行中进程 | 5/14 |
| frida | Frida插桩 | 0/9 |
| application | 比较与重建 | 0/17 |
| database | 数据库 | 0/1 |
| projects | 项目管理 | 27/28 |
| setup | 引擎与设置 | 20/20 |
| build | 构建 | 6/6 |

这张表是全文最值钱的一行设计：**默认clean-room模式下，native/formats/managed/java这些"要读目标内部"的toolset可用数是0**。每个被禁的工具都带原因：

```json
{"available":false,"tool":"core_target_open",
 "reason":"This looks inside the original (its code, files or page source), which Clean room never does."}
```

能用的是：项目管理、证据账本、会话状态、浏览器外壳观察（不读页面源码）、设置——**不碰目标内部的活才让干**。

## 4. T4 triage实测：先被拒，再看穿notepad.exe

拿`C:\Windows\System32\notepad.exe`做first-look。

**第一次，默认模式，直接被拒：**

```json
{"error":{"category":"missing","code":"feature_missing",
 "details":{"reason":"clean_room","tool":"core_target_open"},
 "message":"This looks inside the original (i..."}}
```

triage的第一步是`core_target_open`——要打开目标内部，clean-room下禁止。这就是第3节那张0/55的表在运行时的真实行为：**不是配置建议，是执行时硬拦截**。

**第二次，`--deep`显式放行，完整first-look：**

```json
{"result":{
  "format":"pe","format_name":"PE (Windows)","kind":"executable",
  "architecture":"x86_64","bits":64,"operating_system":"Windows",
  "entry_point":"0x1400019c0",
  "stripped":true,"symbol_table_stripped":true,
  "libraries":["COMCTL32.dll","GDI32.dll","USER32.dll", ...31个导入DLL],
  "toolchain_hints":[{"category":"compiler","evidence":"Rich header",
     "id":"msvc","label":"Microsoft Visual C++ toolchain","strength":"strong"}],
  "plain_english":"notepad.exe is a program for Windows, built for x86_64 (64-bit). Its internal names were removed (stripped), so most functions will have generated names.",
  "recommended_toolsets":["core","native","formats"],
  "next_steps":[
     {"tool":"core_overview_show","why":"a one-page summary: sections, imports, counts"},
     {"tool":"native_functions_list","why":"every function we found"},
     {"tool":"native_strings_find","why":"find text the program shows or uses"},
     {"tool":"native_function_study","why":"a full dossier on one function"},
     {"tool":"core_feature_find","why":"follow a word you see in the app to the code behind it"},
     {"tool":"native_pe_resources_list","why":"icons, version information and the manifest"}]
 },
 "subject":{"kind":"pe","name":"notepad.exe",
   "sha256":"468ffe129c395abf6b21a09efdf261910a95fb98aa982ead73caa7b2b684577e"},
 "authority":"original-files","confidence":"observed",
 "limitations":[{"code":"heuristic_hints",
   "message":"toolchain and packer hints come from markers that can be faked or borrowed"}]}
```

一次triage给了六样东西，每样都站得住：

1. **格式与架构**：PE/x86_64/Windows，入口点0x1400019c0——正确
2. **导入表**：31个DLL全列出
3. **符号状态**：stripped=true，并预告"函数名将是生成的"——管理预期
4. **工具链指纹**：从Rich header认出MSVC，强度标strong
5. **limitations诚实声明**："工具链与壳提示来自可被伪造或借用的标记"——多少逆向工具把启发式结论当事实甩给你？它把不确定性写进结构里
6. **下一步导航**：6个推荐工具各带一句why，等于把分析师的工作流编排好了

## 5. 评测视角：这套安全设计到底好在哪

作为"agent安全与评测"专栏的一篇，光看功能不行，得拆它的安全架构。四层：

**第一层：clean-room by default。** 逆向工程有个老问题：看了人家的代码再写自己的，产出物算"派生作品"，版权就脏了。clean-room模式从机制上保证"不读原始内部"——不是承诺书，是工具调用层的硬拦截（T4第一次被拒就是证据）。对做合规逆向、兼容性工程、互操作开发的团队，这个默认值就是合规底线。顺带它还是一道注入防线：不读不可信二进制/网页的内部内容，prompt injection的攻击面就小一圈。

**第二层：授权三级阶梯。** `--clean-room`（默认，不看内部）→ `--deep`（可以看代码/文件/页面源码，但不能跑）→ `--allow-run`（才能执行代码、改动设备）。每一级都要显式伸手，且`--deep`与`--clean-room`互斥（CLI参数层`conflicts_with`强制）。这和前两篇测的Mandate attenuation（权限只能衰减不能放大）是同一个思想：默认最小权限，升权必须显式。

**第三层：证据账本（evidence ledger）。** 每次工具调用产出一条结构化证据记录：带唯一id（`ev_a816...`）、目标sha256绑定、authority（`original-files`）、confidence分级（`observed`观察到的事实 vs `heuristic`启发式推测）、limitations数组。调查过程中所有发现落在`.cany`项目目录里，`report`命令据此生成HTML报告（实测：triage后`evidence_records:1`，报告3212字节）。**证据与结论分离、置信度分级**——这正是第⑦篇"安全关键状态的权威性和持久性必须和授权本身同级"在取证侧的投影。

**第四层：MCP默认收敛。** 挂上编码Agent时默认只暴露30个工具（Essentials），321个全量要显式`--all-tools`。Agent能调用的工具数就是攻击面大小，默认给最小集是对的。

## 6. 不足与适用人群

不足也直说：

- **没有Windows官方包**，国内用户部署门槛实打实存在（本文第1节的三连坑）。Rust编译13分钟+VS Build Tools几个GB，不是开箱即用
- 16/18外部引擎本机未装时，高级能力（Ghidra反编译、Frida插桩、固件第二意见）都是纸面能力，要出活还得逐个装引擎
- clean-room默认虽好，但`--deep`一句参数就绕过——它是合规工具不是强制沙箱，防君子不防蓄意

适用人群：做逆向/安全研究/兼容性工程，且已经有Claude Code、Codex这类编码Agent在手的团队。它的价值不是替代Ghidra/IDA，而是**把逆向工作流编排成Agent可调用的321个带证据、带授权门、带诚实声明的工具**。

## 7. 系列下一篇预告

doctor显示本机Claude Code已装但未接入。下一篇跑`setup --client claude_code`完成接入，实测MCP挂进真实编码Agent后：30个默认工具长什么样、`core_action_approve`人工审批闸门在Agent调用链里怎么工作、以及把triage→functions_list→strings_find→report的完整逆向流交给Agent自动跑一遍。

---

*本系列其他实测：⑥A2A跨进程Mandate传输+防重放（9场景8拦截，揪出重启真空期）、⑦Mandate持久化+重启恢复（nonce落盘SQLite，主键冲突关掉重放窗口）。链接发布后补。*
