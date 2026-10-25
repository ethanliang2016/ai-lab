# Omnara 自托管全链路复现步骤

> 基于 Omnara 仓库自带 compose 栈（9 镜像）。全程国内网络，Docker Hub 走国内 mirror。

## 1. 起栈（注意 override 暗坑）

```bash
# 仓库里的 compose.override.yaml 会自动加载，把 5 个 app 服务改成本地源码构建
# 用官方发布镜像必须显式指定 -f compose.yaml
docker compose -f compose.yaml --profile app up -d

# 验证：10 容器，migrate 一次性任务应 Exited (0)
docker compose -f compose.yaml --profile app ps -a
```

服务清单：api(8080) / worker / maintenance / migrations / web / gateway(8000) / valkey / postgres:18-alpine / rustfs:1.0.0。

## 2. 注册账号（console 邮件驱动）

```bash
# 浏览器打开 http://localhost:8000 → Sign up → 填邮箱
# 验证链接打在 api 日志里：
docker logs omnara-api-1 | findstr /i "verify-email"
# 浏览器打开该链接，设置密码（≥12 位）、姓名、组织名 → 自动创建组织 + Default 项目
```

## 3. 拿 PAT（RFC 8628 设备授权流）

```bash
# 3.1 申请设备码
curl http://localhost:8000/api/auth/device/code ^
  -H "Content-Type: application/x-www-form-urlencoded" ^
  --data-urlencode "client_id=omnara-cli" ^
  --data-urlencode "token_name=my-terminal"
# → 返回 device_code / user_code / verification_uri_complete

# 3.2 浏览器打开 verification_uri_complete，登录后点 Approve

# 3.3 轮询拿 token（批准后返回）
curl http://localhost:8000/api/auth/device/token ^
  -H "Content-Type: application/x-www-form-urlencoded" ^
  --data-urlencode "grant_type=urn:ietf:params:oauth:grant-type:device_code" ^
  --data-urlencode "device_code=<DEVICE_CODE>" ^
  --data-urlencode "client_id=omnara-cli"
# → access_token 即 omnara_pat_v1_... 格式的 PAT
```

## 4. 接入国产模型（SiliconFlow 示例）

四层资源治理：secret → model-provider-config → configured model → project grant。

```bash
# 4.1 凭据加密信封（org 级）
POST /api/v1/orgs/{org}/secrets
{"owner":{"kind":"org"},"name":"siliconflow-key",
 "material":{"kind":"generic","value":"<YOUR_SILICONFLOW_KEY>"}}
# → sec_...

# 4.2 建 provider（服务端会实探 /models 验证凭据，实测返回 68 模型目录）
POST /api/v1/orgs/{org}/model-provider-configs
{"name":"siliconflow","api_format":"openai-chat-completions",
 "base_url":"https://api.siliconflow.cn/v1","auth_kind":"bearer_token",
 "auth_options":{},"credential_secret_id":"sec_..."}
# → mpc_...

# 4.3 配置模型
POST /api/v1/orgs/{org}/model-provider-configs/mpc_.../models
{"name":"deepseek-v4-flash","provider_model_slug":"deepseek-ai/DeepSeek-V4-Flash",
 "context_window_tokens":128000,"supports_tools":true}
# → mdl_...

# 4.4 授权给项目
POST /api/v1/orgs/{org}/projects/{proj}/model-grants
{"configured_model_id":"mdl_..."}
```

## 5. launch agent（compile + launch 一次调用）

```bash
POST /api/v1/orgs/{org}/projects/{proj}/agents
Authorization: Bearer <YOUR_PAT>
{"config_source":{"source":"<agent.yaml 内容>","source_format":"yaml"},
 "name":"code-reviewer",
 "message":"审查这段代码：\ndef transfer(from_acct, to_acct, amount): ..."}
```

注意：编译器会自动给 config 补 `storage_list`/`storage_read`/`storage_search` 三个工具，这是文档明示的行为。

## 6. 观察事件流 + 人机闭环

```bash
# SSE 事件流（agent_input / model_output / tool_result / turn_end 全在这条流里）
curl -N "http://localhost:8000/api/v1/orgs/{org}/projects/{proj}/agents/{agt}/events/stream" ^
  -H "Authorization: Bearer <YOUR_PAT>" -H "Accept: text/event-stream"

# 查待处理交互（ask_question 弹窗）
GET .../agents/{agt}/interactions
# → int_...，state=open，questions 带 options（服务端自动补第 4 项 "Other"）

# 提交回答（option_indices 零基索引）
POST .../agents/{agt}/interactions/{int}/resolve
{"answers":[{"option_indices":[0]}]}
# 实测：resolve 返回后 7.878ms，tool_result 事件进时间线，agent 恢复执行
```

## 7. 看 durable execution 的证据

```bash
docker logs omnara-worker-1
# 关键日志（单次 worker.loop 实测摘录）：
#   runtime_lock.lease_expires_at = 获取时刻 +90s
#   SQL: AcquireExecutionRuntime / FenceExecutionRuntime /
#        ClaimNextAgentWakeup / OpenExecutionTurn / ResolveExecutionInput
#   http.subrequests: POST api.siliconflow.cn/chat/completions 200 (911ms)
#   单 turn 68 条命名 SQL，db.queries.error_count=0
```

## 停止

```bash
docker compose -f compose.yaml --profile app down
```
