# craft-anything实测稿 · 专家评审报告

评审对象：《craft-anything实测：321个工具的逆向工程Agent，默认把自己锁在"洁净室"里》
评审视角：Agent安全与逆向工程交叉领域从业者，未参与本文实测
评审日期：2026-11-08

## 一、事实核查（逐条对证据）

| 文中声明 | 证据位置 | 核查结论 |
| --- | --- | --- |
| 工具总数321、17 toolsets | evidence\run_log.txt T3/T2：`"tools":321`，commands数组计数=321，toolsets数组=17 | ✅ 属实，与官方"301 engine tools + ~20 AI/setup"口径吻合 |
| clean-room默认开启 | T2 capabilities：`"analysis_mode":"clean-room"` | ✅ 属实 |
| clean-room下native 0/55、core 28/36等 | T2 toolsets逐集统计（注：formats/adb两集因输出字段缺失未计入精确数，文中表述留了余地） | ✅ 基本属实 |
| triage默认被拒，reason=clean_room | T4：`"code":"feature_missing","details":{"reason":"clean_room"}` | ✅ 属实 |
| --deep后triage完整结果 | T4r：PE/x86_64/entry 0x1400019c0/31 DLL/stripped/MSVC Rich header/limitations | ✅ 属实，逐项在日志中 |
| doctor探测7个Agent+18引擎+2 found | T1：registration×8（含DSH）、engine×18、chromium/java=ok | ✅ 属实（"7个Agent+DSH手动"表述准确） |
| MCP自测协议2025-06-18、30工具 | T1：`mcp:self-test ok` | ✅ 属实 |
| 编译13m20s、773依赖、36.5MB | cargo-build.log `Finished in 13m 20s`；cargo-fetch.log 773行Downloaded；exe实测36.48MB | ✅ 属实 |
| 部署三连坑（无Windows包/deb截断/镜像卡死） | build.log、build-src.log、多次下载记录 | ✅ 属实 |

**事实层面无夸大、无虚构。所有关键数字可复核。**

## 二、技术判断评审

1. **"clean-room是执行时硬拦截而非配置建议"**——判断成立。依据：T4默认模式返回error而非warning，且capabilities中每个被禁工具带独立reason字段，说明拦截点在工具调度层。✅
2. **"授权三级阶梯clean-room/deep/allow-run"**——成立，但有一个细微补充：文中已正确指出`--deep`与`--clean-room`互斥由clap参数层强制。准确。✅
3. **"clean-room顺带防prompt injection"**——合理推论但属作者观点而非项目方声明。文中语气（"攻击面就小一圈"）未越界为事实声明。可接受。⚠️ 建议保留但已在措辞上标为推论，无需改。
4. **"--deep一句参数就绕过，防君子不防蓄意"**——评审认同此不足表述，避免了把clean-room吹成安全沙箱的常见错误。✅ 这是本文最体现评测纪律的一段。
5. **与⑥⑦篇的机制类比（attenuation/状态持久化）**——类比恰当，未强行拔高。

## 三、结构与表达

- 结论先给、部署坑前置（国内读者最痛的点）、证据代码块充分，符合系列风格 ✅
- 第3节toolset表是全文信息密度最高点，处理得当
- 标题"321个工具"+"洁净室"双钩子，数字可验证，不标题党

## 四、发现的问题（需作者处理）

1. **[轻微] 第3节表格中formats/adb两集clean-room可用数**：实测统计时这两集`available`字段解析为空，文中填了0/36、0/24。从T4证据看formats工具在clean-room下应确实不可用（core_archive_*均false），方向正确，但严格说这两格是推断非直读。建议：可接受（结论方向有T4佐证），或发布前补跑一次精确统计。
2. **[轻微] 第1节"773个crate依赖"**：fetch日志773行Downloaded含重复版本（如syn v2+v3），精确表述应为"约770个依赖包下载"，但数量级与表述无误导。可不改。
3. **[提示] report.html（3212字节）已生成但文中未附截图**：建议发布时在CSDN插入report.html渲染截图一张，增强"证据账本"一节说服力。非阻塞。

## 五、评审结论

**通过，可发布。** 事实全部可复核，安全设计分析到位且克制，不足部分写得诚实。评分：**A-**（扣分项：formats/adb两格统计为推断；缺report.html可视化截图）。

---
评审人：专栏外审（模拟） · 本报告随稿存档于 evidence\ 同级
