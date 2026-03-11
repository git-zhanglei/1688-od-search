# AK 配置说明

AK（Access Key）是访问 1688 平台的身份凭证，前 32 位是 Secret，其余是 Key ID。

## 获取 AK

1. 下载 [**1688 AI版 APP**](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper)
2. 打开 APP 首页，点击「一键部署开店Claw，全自动化赚钱🦞」
3. 进入页面后复制 AK

## 配置 AK

### 推荐方式：对话中直接告知 Agent

```
我的AK是 xxx...xxx
```

Agent 会自动：
1. 调用 `cli.py configure xxx` 持久化保存
2. 在当前会话注入环境变量立即生效
3. 继续你的请求

### CLI 方式

```bash
python3 {baseDir}/cli.py configure YOUR_AK_HERE
```

配置成功后重启 Gateway：
```bash
openclaw gateway restart
```

## 配置写入机制

`configure` 命令优先通过 **Gateway REST API** 写入（安全，不破坏 JSON5 格式）。
Gateway 不可用时会尝试 fallback 直写 `~/.openclaw/openclaw.json`（仅当该文件是标准 JSON）。
若检测到非标准 JSON（例如 JSON5），会拒绝覆盖写入并提示先恢复 Gateway 可用性。

## 检查配置状态

```bash
python3 {baseDir}/cli.py check
```

输出 AK 状态、绑定店铺数量、数据目录可写状态。

## 安全提示

- AK 仅用于本地 API 调用，不上传服务器
- 建议定期轮换 AK（在 1688 AI版 APP 重新生成）
- 不要将 AK 提交到代码仓库
