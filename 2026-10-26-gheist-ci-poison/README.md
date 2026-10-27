# Gheist CI 投毒审计实测 · 配套代码

> 对应文章：《我在自己的仓库里种了个毒 workflow：CI 供应链攻击实测，用检出率说话》（agent 安全与评测专栏第 6 篇）
> 合规：全部密钥为假值，仓库仅本地，V5 外联地址为 `.invalid` 保留域名。请勿将任何载荷用于真实仓库。

## 目录

- `repo/`：基准仓库（3 个正常 workflow，未投毒）
- `attacks/v1~v8/`：8 个毒 workflow 变体，各含 `scenario.json`（分支名 / commit message / 变更文件）
- `detectors/`：检出器
  - `run_matrix.py`：矩阵编排器（M2 actionlint + M3 zizmor + M4 IoC + M5 通用规则 + 阴性对照）
  - `ioc_scan.py`：M4，严格按 Wiz IoC（分支正则 / commit msg / 路径 / 完整标记串 / 4 个 blob SHA）
  - `generic_scan.py`：M5，8 条通用语义规则（secrets 进 shell、编码+env 同块、外联原语、environment 矩阵、typosquat、pull_request_target、artifact 夹带、长 base64 团块）
  - `ai_review.py`：M6，DeepSeek-V3 审 PR diff（需 `SILICONFLOW_API_KEY`）
  - `mask.py`：GitHub 日志逐字脱敏模拟（E2）
  - `punct_check.py`：中文稿标点检查（写作辅助，与实验无关）
- `runs/`：各变体 PR diff、检出器原始输出、act 执行日志（`v1-act.log`）、假密钥（`secrets.fake`）
- `results/`：`matrix.json`、`ai_review.json`

## 复现

```bash
pip install pillow  # 仅封面处理需要；检出器仅标准库
# 工具：act 0.2.89 / actionlint 1.7.12 / zizmor 1.31.1（GitHub release 二进制，放 ~/.local/bin）
python detectors/run_matrix.py        # 重跑 8 变体 × 4 自动手段 + 阴性对照
python detectors/mask.py              # E2 脱敏绕过模拟

# E1/E3 act 实跑（需 Docker）：
cd runs/v1-applied
act push -W .github/workflows/sync-check.yml \
  -P ubuntu-latest=node:20-bookworm-slim \
  --secret-file ../secrets.fake
```

## 实测结论速览

| 手段 | 检出 | 备注 |
|---|---|---|
| actionlint | 0/8 | 语法工具，不碰安全 |
| zizmor（High 阈值） | 语义真阳性 1/8 | 密钥外泄信号（overprovisioned-secrets）仅 Medium，干净仓库自带 4 条 High unpinned-uses 噪声 |
| 严格 IoC | 2/8 | 改文件名即失效，仅适用回溯狩猎 |
| 通用语义规则 | 8/8 | 后见之明偏差：规则为看完手法后编写 |
| DeepSeek-V3 审 diff | 8/8 | 7 malicious + 1 suspicious，良性对照 clean，n=8 小样本 |
